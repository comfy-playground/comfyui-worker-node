# ComfyUI Gateway Worker Image

Reproducible ComfyUI image and API workflow collection for the local image
gateway. The image runs the primary A3000M worker and can be retagged and
reused by the optional RTX 3090 worker without rebuilding.

This repository builds worker software only. Model weights, LoRAs, input,
output, and LoRA Manager state remain on mounted host storage.

## What This Repository Adds

| Area | Change | Reason |
| --- | --- | --- |
| ComfyUI core | Pinned to `6f7cd7fceaaf60d2669b554936394a7412c6fde5` | Avoid unreviewed core changes changing workflow behavior. |
| Gateway batch node | `ComfyUI-Gateway-Batch` custom node | Provides independent noise and stochastic sampling for gateway-created batches. |
| Anima 2.9B | Pinned `ComfyUI-Anima-2.9B` compatibility node | Supports the 40-block Anima 2.9B architecture. |
| LoRA Manager | Pinned commit plus `aria2` resume/queue patch | Preserves restored download state and queue history across restarts. |
| Runtime models | Diffusion-model and text-encoder mounts | Supports Anima `UNETLoader` and `CLIPLoader` workflows without baking weights into the image. |

Details are in [docs/architecture.md](docs/architecture.md) and
[docs/operations.md](docs/operations.md).

## Repository Layout

```text
Dockerfile                                      Reproducible ComfyUI image
docker-compose.yml                              Primary A3000M worker
custom_nodes/ComfyUI-Gateway-Batch/             Gateway-owned batch nodes
patches/comfyui-lora-manager-aria2-resume-queue.patch
tests/                                          CPU-only custom-node tests
*.json                                          ComfyUI API workflow templates
```

## Build And Run

Prerequisites:

- Docker Engine with NVIDIA Container Toolkit.
- The model directories referenced by `docker-compose.yml`.
- A `.env` file containing `CIVITAI_API_KEY` when LoRA Manager downloads are
  required. Do not commit this file.

Build and replace only the primary worker:

```sh
docker compose build comfyui
docker compose up -d --no-deps --force-recreate comfyui
docker compose ps
```

The primary service exposes ComfyUI at `http://127.0.0.1:18188`. Its Compose
file intentionally pins the A3000M GPU UUID; do not replace it with `all`.

## Validate A Build

Run the node tests against the built image. They use the CPU-only ComfyUI path
and do not require a GPU or model weights:

```sh
docker run --rm \
  -v "$PWD:/repo:ro" \
  -w /app/ComfyUI \
  --entrypoint python \
  animagine-comfyui:latest \
  -m unittest discover -s /repo/tests -v
```

Confirm that the worker registered the stochastic batch capability:

```sh
docker exec animagine-comfyui \
  curl -fsS http://127.0.0.1:8188/object_info/GatewayMultiSeedStochasticSampler
```

For a release that changes ComfyUI, the batch plugin, Anima compatibility, or
model loading, also submit a real Anima workflow through the gateway. A batch
size of two must complete with exactly two output files whose hashes differ.

## Workflow Templates

The API workflows cover Animagine XL, Anima Base v1.0, Anima 2.9B, LoRA Manager
variants, and a DeepSeek maid test case. API workflow JSON is source-controlled
because gateway clients submit it directly; it is not a UI export archive.

For the Anima Base v1.0 LoRA Manager workflow, these IDs are a contract with
the gateway batch adapter:

| Node ID | Contract |
| --- | --- |
| `5` | Positive prompt encoder |
| `6` | Negative prompt encoder |
| `13` | Sampler; becomes the batch sampler at request time when eligible |
| `14` | VAE decode |
| `15` | `SaveImage` output |

Do not renumber these nodes or change the positive, negative, or output links
without updating and testing the gateway adapter. See the workflow invariants
in [docs/architecture.md](docs/architecture.md).

## Image Reuse And Rollback

Release a verified local image with a fixed tag before deploying it elsewhere:

```sh
docker image tag animagine-comfyui:latest animagine-comfyui:gateway-batch-YYYYMMDD
```

The RTX 3090 worker is a separate Compose deployment on this host. It must use
the fixed release tag with `pull_policy: never`, not rebuild its own image.
The exact deployment and rollback procedure is in
[docs/operations.md](docs/operations.md).

Never delete the previous image before the replacement has passed startup,
capability, and real-workflow validation. Keep a dedicated rollback tag such
as `animagine-comfyui:pre-3090-batch-YYYYMMDD`.

## Contribution And GitHub Submission

Read [AGENTS.md](AGENTS.md) before editing Docker, workflow, or plugin files.
The pull-request checklist is in
[.github/pull_request_template.md](.github/pull_request_template.md).

This checkout currently has no configured Git remote. Add the intended GitHub
remote only after the repository owner chooses its URL and visibility; do not
infer or publish to a remote.
