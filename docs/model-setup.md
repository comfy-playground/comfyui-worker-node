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
