# Agent Guide

## Scope

This repository builds a pinned ComfyUI worker image and stores API workflow
templates. It does not own gateway queueing, credentials, model downloads, or
generated outputs.

Read [README.md](README.md), [docs/model-setup.md](docs/model-setup.md),
[docs/architecture.md](docs/architecture.md), and [docs/operations.md](docs/operations.md)
before changing worker behavior.

## Files And Ownership

| Path | Responsibility |
| --- | --- |
| `Dockerfile` | Pinned core and custom-node image composition. |
| `docker-compose.yml` | Primary worker, GPU selection, networking, and startup configuration. |
| `compose.storage.yaml` | Primary worker model and persistent-data mounts. |
| `.env.example` | Storage-root and optional Civitai token template. |
| `docs/model-setup.md` | Minimum base-model sets and deferred download guidance. |
| `custom_nodes/ComfyUI-Gateway-Batch/` | Gateway-owned ComfyUI nodes only. |
| `patches/` | Pinned third-party source patches applied during build. |
| `*.json` | API workflow source, consumed by gateway clients. |
| `tests/` | Custom-node regressions that run inside the image. |

## Non-Negotiable Rules

- Do not unpin `COMFYUI_REF`, the LoRA Manager commit, or the Anima compatibility
  commit without a rebuilt-image and real-workflow test.
- Do not modify ComfyUI core inside a running container. Add a small custom node
  or a pinned patch instead.
- Do not commit weights, LoRAs, images, `input`, `output`, caches, `.env`, or
  any secret. Model directories are runtime mounts.
- Keep `COMFYUI_MODEL_ROOT` writable on the primary worker; LoRA Manager owns
  downloads under `models/loras`. Do not reintroduce one Compose volume per
  model category when a new category is needed.
- Public Compose defaults to NVIDIA device index `0`. Set
  `COMFYUI_GPU_DEVICE` in a local `.env` to choose another index or device
  identifier; do not use `all` for a worker that must retain one GPU.
- Preserve Anima Base v1.0 workflow IDs `5`, `6`, `13`, `14`, and `15`. The
  gateway relies on them to preserve positive prompt, negative prompt, sampler,
  decode, and image-output connectivity during batch conversion.
- Keep `GatewayMultiSeedStochasticSampler` at a maximum of four members unless
  a real VRAM and output-count test justifies a change.
- Treat `er_sde` batch as correctness-first, not vectorized acceleration. Each
  member must retain an independent seed/RNG stream.

## Required Validation

For a custom-node change:

```sh
docker run --rm \
  -v "$PWD:/repo:ro" \
  -w /app/ComfyUI \
  --entrypoint python \
  animagine-comfyui:latest \
  -m unittest discover -s /repo/tests -v
```

For any image-affecting change:

```sh
docker compose config
docker compose build comfyui
docker compose up -d --no-deps --force-recreate comfyui
docker exec animagine-comfyui curl -fsS http://127.0.0.1:8188/system_stats
docker exec animagine-comfyui \
  curl -fsS http://127.0.0.1:8188/object_info/GatewayMultiSeedStochasticSampler
```

For core, batch, or Anima changes, submit an actual batch-size-two Anima
`er_sde` request after the preceding checks. It must return exactly two output
files with different hashes. Capture a rollback tag before replacing either
worker container.

## Deployment Discipline

1. Build and prove the primary-worker image first.
2. Give that image a fixed release tag.
3. Update an additional worker's existing Compose `image:` reference only after
   primary-worker validation succeeds.
4. Recreate the additional worker with `--no-build --no-deps`.
5. Verify its capability endpoint and configured gateway reachability.

Do not delete images or named volumes during diagnosis. Preserve the pre-change
image under a rollback tag, and restore it if any startup, capability, or output
test fails.

## Git Hygiene

- Use `rg` to inspect workflows and source before editing.
- Keep Docker pins, plugin code, tests, and docs in the same review when they
  describe one behavior change.
- Run `git diff --check` and inspect `git status --short` before staging.
- `origin` is configured for the repository. Do not push unless the user asks.
