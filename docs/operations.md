# Operations Runbook

## Current Deployment Topology

| Worker | Compose file | GPU | HTTP endpoint | Image policy |
| --- | --- | --- | --- | --- |
| Primary | `docker-compose.yml` plus `compose.storage.yaml` in this repository | `COMFYUI_GPU_DEVICE`, default `0` | `127.0.0.1:18188` | Build locally from this repository. |
| Additional worker | Deployment-specific Compose file outside this repository | Selected by that deployment | Configured worker endpoint | Reuse a verified fixed local tag; `pull_policy: never`. |

An additional-worker manifest stays outside this repository because it has
deployment-specific volumes, ports, GPU selection, and gateway configuration.
Do not replace its named volumes or device selection when changing only the
image.

Before building the primary worker, copy `.env.example` to `.env` and follow
[model-setup.md](model-setup.md). The primary Compose file imports its storage
extension automatically, so `docker compose` remains the normal command.
`COMFYUI_GPU_DEVICE=0` selects the first GPU; change it locally only when the
host needs a different device.

## Primary Worker Release

Build the primary-worker image and retain the previous image before replacing
its container:

```sh
docker image tag animagine-comfyui:latest animagine-comfyui:pre-release-YYYYMMDD
docker compose build comfyui
docker compose up -d --no-deps --force-recreate comfyui
docker inspect --format '{{.Image}} {{.State.Status}} {{.State.Health.Status}}' animagine-comfyui
```

Validate the running service from inside the container because local sandboxed
tools may not reach host-published ports:

```sh
docker exec animagine-comfyui curl -fsS http://127.0.0.1:8188/system_stats
docker exec animagine-comfyui \
  curl -fsS http://127.0.0.1:8188/object_info/GatewayMultiSeedStochasticSampler
```

After a successful real workflow test, create an immutable release tag for
reuse:

```sh
docker image tag animagine-comfyui:latest animagine-comfyui:gateway-batch-YYYYMMDD
```

## Deploy The Same Image To An Additional Worker

Do not rebuild on an additional-worker deployment. First ensure it is idle:

```sh
docker exec <secondary-container> \
  curl -fsS http://127.0.0.1:8188/queue
```

Tag the existing image for rollback, update only the `image:` field in the
additional worker's Compose file to the verified release tag, then recreate
the service without build or dependencies:

```sh
docker image tag <current-secondary-image-id> animagine-comfyui:pre-secondary-YYYYMMDD
docker compose -f <secondary-compose-file> \
  up -d --no-deps --force-recreate --no-build <secondary-service>
```

Verify the additional worker's service and its configured gateway path:

```sh
docker exec <secondary-container> \
  curl -fsS http://127.0.0.1:8188/object_info/GatewayMultiSeedStochasticSampler
```

## Rollback

If startup, capability discovery, gateway reachability, or real batch output
fails, restore only the affected worker. Do not delete the candidate image or
its persistent volumes.

For the primary worker:

```sh
docker image tag animagine-comfyui:pre-release-YYYYMMDD animagine-comfyui:latest
docker compose up -d --no-deps --force-recreate --no-build comfyui
```

For an additional worker, change its Compose `image:` back to its saved
rollback tag and run:

```sh
docker compose -f <secondary-compose-file> \
  up -d --no-deps --force-recreate --no-build <secondary-service>
```

Then repeat the `/system_stats` check before allowing new work.

## Release Evidence

Record these values in the pull request or release note:

- Candidate and rollback image tags and IDs.
- ComfyUI core, Anima compatibility, and LoRA Manager pinned commits.
- Unit test result.
- Batch-size-two prompt ID, elapsed time, output count, and distinct output
  hashes.
- Primary and additional-worker health and capability responses.

Never include `CIVITAI_API_KEY`, request bearer tokens, local model paths beyond
the documented mount roots, or generated image content in a pull request.
