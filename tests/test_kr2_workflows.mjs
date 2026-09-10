import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const load = filename => JSON.parse(readFileSync(new URL(`../${filename}`, import.meta.url), 'utf8'));
const variants = [
  ['moody_krea_v7_API.json', 768, 1152, 'Moody-Krea-v7', 4],
  ['moody_krea_v7_fast_API.json', 768, 1152, 'Moody-Krea-v7-fast', 2],
];
const loraFiles = [
  'Pantyhose.safetensors', 'glossy_pantyhose_Kera_2_epoch_17.safetensors',
  'neo_tangzhuang-KreaRaw-V2.safetensors', 'asia_cosplay_krea_2.safetensors',
  'CosplayKrea2_000003500.safetensors', 'Krea2_Coser_portrait_photography.safetensors',
  'krea2_JPwoman01_v01.safetensors', 'KoreanWoman_krea2_2_c1-st5000.safetensors',
  'Krea_2_Hayeon.safetensors', 'zy_2B_K2.safetensors', 'EtherialGothicKrea2Raw.safetensors',
];

for (const [filename, width, height, prefix, finalScale] of variants) {
  const compact = finalScale === 2;
  test(`${filename}: keeps the KR2 routing and client node contract`, () => {
    const graph = load(filename);
    assert.deepEqual(Object.keys(graph), [
      '1', '2', '3', '5', '6', '7', '13', '14', '15', '16', '17',
      ...(compact ? ['18'] : []), '23',
    ]);
    assert.equal(graph['1'].class_type, 'UNETLoader');
    assert.deepEqual(graph['1'].inputs, { unet_name: 'Moody-Krea-Mix-v7_00002__clean_fp8.safetensors', weight_dtype: 'default' });
    assert.equal(graph['2'].class_type, 'CLIPLoader');
    assert.deepEqual(graph['2'].inputs, { clip_name: 'qwen3vl_4b_fp8_scaled.safetensors', type: 'krea2', device: 'default' });
    assert.equal(graph['3'].class_type, 'VAELoader');
    assert.deepEqual(graph['3'].inputs, { vae_name: 'qwen_image_vae.safetensors' });
    assert.equal(graph['23'].class_type, 'Lora Loader (LoraManager)');
    assert.deepEqual(graph['23'].inputs, {
      model: ['1', 0], clip: ['2', 0], text: '',
      loras: { __value__: loraFiles.map(file => ({
        name: `ecosystems/krea2/${file}`, strength: '0.8', clipStrength: '0.8', active: false, expanded: false,
      })) },
    });
    for (const id of ['5', '6']) {
      assert.equal(graph[id].class_type, 'CLIPTextEncode');
      assert.deepEqual(graph[id].inputs, { text: '', clip: ['23', 1] });
    }
    assert.equal(graph['7'].class_type, 'EmptyLatentImage');
    assert.deepEqual(graph['7'].inputs, { width, height, batch_size: 1 });
    assert.equal(graph['13'].class_type, 'KSampler');
    assert.deepEqual(graph['13'].inputs, {
      seed: 0, steps: 12, cfg: 1, sampler_name: 'euler', scheduler: 'simple', denoise: 1,
      model: ['23', 0], positive: ['5', 0], negative: ['6', 0], latent_image: ['7', 0],
    });
  });

  test(`${filename}: saves one image at ${finalScale}x after a single Remacri pass`, () => {
    const graph = load(filename);
    assert.equal(graph['14'].class_type, 'VAEDecode');
    assert.deepEqual(graph['14'].inputs, { samples: ['13', 0], vae: ['3', 0] });
    assert.equal(graph['16'].class_type, 'UpscaleModelLoader');
    assert.deepEqual(graph['16'].inputs, { model_name: '4x_foolhardy_Remacri.pth' });
    assert.equal(graph['17'].class_type, 'ImageUpscaleWithModel');
    assert.deepEqual(graph['17'].inputs, { upscale_model: ['16', 0], image: ['14', 0] });
    assert.equal(graph['15'].class_type, 'SaveImage');
    assert.deepEqual(graph['15'].inputs, { filename_prefix: prefix, images: [compact ? '18' : '17', 0] });
    const types = Object.values(graph).map(node => node.class_type);
    assert.equal(types.filter(type => type === 'SaveImage').length, 1);
    assert.equal(types.filter(type => type === 'ImageUpscaleWithModel').length, 1);
    assert.equal(types.filter(type => type === 'ImageScale').length, compact ? 1 : 0);
    if (compact) {
      assert.equal(graph['18'].class_type, 'ImageScale');
      assert.deepEqual(graph['18'].inputs, {
        upscale_method: 'bicubic', width: 1536, height: 2304, crop: 'disabled', image: ['17', 0],
      });
      assert.equal(graph['18'].inputs.width, width * finalScale);
      assert.equal(graph['18'].inputs.height, height * finalScale);
    } else {
      assert.equal(graph['18'], undefined);
    }
    for (const [id, node] of Object.entries(graph)) {
      for (const [key, input] of Object.entries(node.inputs)) {
        if (!Array.isArray(input)) continue;
        assert.equal(input.length, 2);
        assert(graph[input[0]], `Dangling link to node ${input[0]}`);
        const expectedSlot = ['5', '6'].includes(id) && key === 'clip' ? 1 : 0;
        assert.equal(input[1], expectedSlot, `Wrong output slot at ${id}.${key}`);
      }
    }
  });
}

test('fast keeps the same generation and LoRA graph, changing only final resize and filename prefix', () => {
  const standard = load(variants[0][0]);
  const fast = load(variants[1][0]);
  delete fast['18'];
  fast['15'].inputs = structuredClone(standard['15'].inputs);
  assert.deepEqual(fast, standard);
});
