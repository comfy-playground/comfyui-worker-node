# Minimal Model Setup

## Storage Configuration

Copy the example and set absolute host paths before starting the worker:

```sh
cp .env.example .env
```

`COMFYUI_MODEL_ROOT` is mounted once at `/app/ComfyUI/models`. It must contain
the standard ComfyUI subdirectories. `COMFYUI_DATA_ROOT` holds inputs, outputs,
and persistent manager state. Both variables can point at the same directory.

```text
COMFYUI_MODEL_ROOT/
  checkpoints/
  diffusion_models/
  text_encoders/
  vae/
  loras/
COMFYUI_DATA_ROOT/
  input/
  output/
  custom_nodes_data/
  lora_manager_data/
```

The worker starts without any weights, but it cannot generate an image until a
workflow's minimum base-model set is present. Start with one workflow family;
do not download every optional category up front.

## First Image: Choose One Family

### Option A: Animagine XL

For `animagine_default_v4.0_API.json`, download only this checkpoint first:

```text
checkpoints/animagine-xl-4.0.safetensors
```

This checkpoint workflow supplies its own VAE. It is the smallest bootstrap
path when the objective is simply to verify end-to-end generation.

The REED workflow is a separate checkpoint family and needs this additional
file only when that workflow is selected:

```text
checkpoints/reedXXXIllustrious_v150.safetensors
```

### Option B: Anima Base v1.0

For `anima_base_v1.0_lora_manager.json`, install this matched three-file base
set before submitting a request:

```text
diffusion_models/anima-base-v1.0.safetensors
text_encoders/qwen_3_06b_base.safetensors
vae/qwen_image_vae.safetensors
```

### Option C: Anima 2.9B

For the Anima 2.9B workflows, install the matched UNET and reuse the Qwen text
encoder and VAE from Option B:

```text
diffusion_models/anima29B_v10.safetensors
text_encoders/qwen_3_06b_base.safetensors
vae/qwen_image_vae.safetensors
```

## Download The Rest Later

### Moody Krea v7 FP8

The Krea 2 workflows use the following matched files. Keep this model
set on the 3090 worker until its quality and memory envelope are validated:

```text
diffusion_models/Moody-Krea-Mix-v7_00002__clean_fp8.safetensors
text_encoders/qwen3vl_4b_fp8_scaled.safetensors
vae/qwen_image_vae.safetensors
upscale_models/4x_foolhardy_Remacri.pth
```

Both templates use 12 steps, CFG 1, Euler / simple, and a batch size of one:

| Template | Generation size | Saved image size |
| --- | --- | --- |
| [moody_krea_v7_API.json](../moody_krea_v7_API.json) (default) | 768×1152 | 3072×4608 |
| [moody_krea_v7_fast_API.json](../moody_krea_v7_fast_API.json) (fast) | 768×1152 | 1536×2304 |

The default template decodes the generated latent and applies Remacri once at
its native 4x scale, with no final resize. The fast template uses the same
768×1152 generation base, applies Remacri 4x, then bicubic-resizes to 1536×2304
for a compact 2x final output. Remacri is required for these templates and stays
under the existing unified model-root mount; do not add a single-file mount.
Positive and negative prompt fields are empty for clients to populate. Node
IDs `5`, `6`, `13`, `14`, and `15` retain their existing roles; node `15` now
saves the upscaled image from node `17` (default) or the final resize at node `18`
(fast). Node `23` is a
`Lora Loader (LoraManager)` that passes its MODEL output to sampler `13` and
its CLIP output to encoders `5` and `6`. Reference-image support is deferred.

Fast retains the same generation detail and sampling cost as the default; its
smaller final PNG reduces save and transfer work. Remacri still processes the
same 4x intermediate image. Final PNG byte size depends on the image content;
1536×2304 is not a hard 4 MB file-size guarantee.

The LoRA stack lists eleven reviewed Krea 2 files, all with `active: false`.
Without a runtime LoRA selection, no LoRA weights are loaded. Named inactive
entries let the current AstrBot plugin discover the stack; an empty list is
not recognized by that plugin. It can activate these entries, adjust strengths,
or append selections discovered in its local inventory. Keep each `name` as a
complete relative catalog key such as `ecosystems/krea2/Pantyhose.safetensors`;
bare filenames may work on a direct worker but fail gateway validation.
Only activate installed Krea 2-compatible LoRAs. A `.steps.json` sidecar in the
plugin data directory can override the template's 12 steps and must be reviewed
separately when installing these templates.

Run the workflow contract checks without a container or GPU:

```sh
node --test tests/test_kr2_workflows.mjs
```

These categories are not required for the first base-model image:

| Category | Add it when | Destination |
| --- | --- | --- |
| LoRAs | A selected workflow or prompt needs a character, style, clothing, or enhancement LoRA. | `loras/` |
| ControlNet | You use pose, depth, line-art, or other conditioning workflows. | `controlnet/` |
| IP-Adapter and CLIP Vision | You use image-reference workflows. | `ipadapter/` and `clip_vision/` |
| Upscalers | You enable hires or post-generation upscaling. | `upscale_models/` |

Use LoRA Manager for LoRAs instead of manually scattering downloaded files.
Ensure `COMFYUI_MODEL_ROOT` is writable, set `CIVITAI_API_KEY` in `.env` when
the download requires authentication, restart the worker after changing the
environment, then submit the download from the LoRA Manager UI. Its queue,
history, partial transfer state, and downloaded files persist under the two
configured storage roots.

Disable or remove a workflow's LoRA entry until the manager reports the file as
available. A missing LoRA must not be treated as a missing base model.

## Before Adding A Model

Confirm the active workflow's loader filenames match the filenames on disk.
ComfyUI exposes discovered values through its node metadata, for example:

```sh
docker exec animagine-comfyui \
  curl -fsS http://127.0.0.1:8188/object_info/UNETLoader
```

Do not commit any model file, LoRA, token, input, output, or manager cache to
this repository.
