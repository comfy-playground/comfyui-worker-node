# Architecture

## Responsibility Boundaries

This repository owns the ComfyUI worker image, worker-local custom nodes,
workflow templates, and image build pins. The TypeScript gateway owns queueing,
batch eligibility, per-worker capability discovery, graph transformation, and
result persistence.

The worker must stay independently usable through ComfyUI's HTTP API. The
gateway integration is additive; no ComfyUI core file is patched for gateway
behavior.

## Image Build

The Dockerfile starts from `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime` and
performs these ordered steps:

1. Install system packages, including `aria2`, `git`, `curl`, and build tools.
2. Clone and pin ComfyUI with `COMFYUI_REF`.
3. Install ComfyUI requirements.
4. Copy `custom_nodes/ComfyUI-Gateway-Batch` into the image.
5. Install ControlNet Auxiliary, IP-Adapter Plus, and the pinned LoRA Manager
   with the local aria2 resume patch.
6. Install the pinned Anima 2.9B compatibility node.

Changing a file copied before later Dockerfile layers invalidates those later
layers. A worker-image rebuild is therefore expected to reinstall custom-node
dependencies after a gateway-plugin change.

## Runtime Storage

The image contains code, not weights or user data. The primary Compose service
mounts these host-owned paths:

| Host purpose | Container path |
| --- | --- |
| Checkpoints | `/app/ComfyUI/models/checkpoints` |
| Diffusion models | `/app/ComfyUI/models/diffusion_models` |
| Text encoders | `/app/ComfyUI/models/text_encoders` |
| LoRAs | `/app/ComfyUI/models/loras` |
| VAE, ControlNet, IP-Adapter, CLIP Vision, upscalers | Matching `models/*` directories |
| Images | `/app/ComfyUI/input` and `/app/ComfyUI/output` |
| LoRA Manager state | `/root/.config/ComfyUI-LoRA-Manager` |

Do not add model weights, outputs, cache directories, or `.env` files to Git.

## Gateway Batch Nodes

`custom_nodes/ComfyUI-Gateway-Batch` contains two ComfyUI nodes.

### `GatewayMultiSeedNoise`

- Input: `seeds`, a JSON array of decimal unsigned 64-bit integers.
- Output: a `NOISE` object.
- Limit: 1 through 16 seeds.
- Behavior: calls `comfy.sample.prepare_noise` once for each batch member and
  concatenates the tensors. This prevents members from sharing an RNG stream.

### `GatewayMultiSeedStochasticSampler`

- Inputs: `seeds`, `GUIDER`, `SAMPLER`, `SIGMAS`, and `LATENT`.
- Outputs: sampled and denoised `LATENT` values, matching
  `SamplerCustomAdvanced`.
- Limit: 1 through 4 members.
- Behavior: slices the incoming latent, mask, and batch index per member;
  invokes `SamplerCustomAdvanced` once per seed; then concatenates the output
  latents in input order.

This is a correctness-first solution for stochastic samplers such as `er_sde`.
It preserves per-member Brownian/RNG state but is not GPU-vectorized sampling;
expect elapsed time close to individual jobs rather than Euler-style batch
throughput.

The plugin imports `SamplerCustomAdvanced` from
`comfy_extras.nodes_custom_sampler`. ComfyUI 0.30 returns `io.NodeOutput`,
while older pins may return the tuple directly. The plugin accepts both by
reading `.result` when present. A core upgrade must re-run both unit and live
workflow validation.

## Workflow Transformation Contract

The stored Anima Base v1.0 workflow remains a normal `KSampler` graph. When
the gateway proves that a batch is eligible, it creates a request-specific graph
that preserves the caller-visible workflow structure:

1. Node `13` keeps its ID but changes class to
   `GatewayMultiSeedStochasticSampler` for `er_sde` batches.
2. The original positive and negative conditioning sources, node IDs `5` and
   `6`, remain unchanged. A `CFGGuider` receives their existing links.
3. Node `15` remains the image-output node with the same `images` input link.
4. The batch sampler returns the merged latent to node `14`, which then emits
   one image per member through node `15`.

The worker plugin does not know about gateway queueing or workflow identity.
Do not place gateway-specific URLs, credentials, or scheduling policy in this
repository.

## Upgrade Rules

Before changing `COMFYUI_REF`, the PyTorch base image, Anima compatibility
commit, or the batch plugin:

1. Build a candidate image with a new tag.
2. Start it on the primary GPU while retaining a rollback tag.
3. Verify `/system_stats` and `/object_info/GatewayMultiSeedStochasticSampler`.
4. Run the unit test command from the README.
5. Run a real batch-size-two Anima `er_sde` request and verify two distinct
   output files.
6. Reuse the validated tag on the RTX 3090 worker only after step 5 succeeds.
