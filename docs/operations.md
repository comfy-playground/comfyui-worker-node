# Operations Runbook

## Current Deployment Topology

| Worker | Compose file | GPU | HTTP endpoint | Image policy |
| --- | --- | --- | --- | --- |
| Primary | `docker-compose.yml` in this repository | A3000M UUID pinned in Compose | `127.0.0.1:18188` | Build locally from this repository. |
| Optional worker | `/opt/docker/comfyui-workers/3090/compose.yaml` | RTX 3090 UUID pinned in its Compose | `host.docker.internal:18201` from gateway | Reuse a verified fixed local tag; `pull_policy: never`. |

The 3090 manifest intentionally lives outside this repository because it has
worker-specific volumes, ports, and GPU ownership. Do not replace its named
volumes or GPU UUID when changing only the image.

## Primary Worker Release

Build the A3000M image and retain the previous image before replacing its
container:

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

## Deploy The Same Image To RTX 3090

Do not rebuild on the 3090 deployment. First ensure it is idle:

```sh
docker exec comfyui-gateway-worker-3090 \
  curl -fsS http://127.0.0.1:8188/queue
```

Tag the existing 3090 image for rollback, update only the `image:` field in
`/opt/docker/comfyui-workers/3090/compose.yaml` to the verified release tag,
then recreate the service without build or dependencies:

```sh
docker image tag <current-3090-image-id> animagine-comfyui:pre-3090-YYYYMMDD
docker compose -f /opt/docker/comfyui-workers/3090/compose.yaml \
  up -d --no-deps --force-recreate --no-build worker
```

Verify the 3090 service and the gateway path:

```sh
docker exec comfyui-gateway-worker-3090 \
  curl -fsS http://127.0.0.1:8188/object_info/GatewayMultiSeedStochasticSampler
docker exec comfyui-gateway-ts node -e \
  "fetch('http://host.docker.internal:18201/system_stats').then(r => { if (!r.ok) process.exit(1) })"
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

For the 3090 worker, change its Compose `image:` back to its saved rollback
tag and run:

```sh
docker compose -f /opt/docker/comfyui-workers/3090/compose.yaml \
  up -d --no-deps --force-recreate --no-build worker
```

Then repeat the `/system_stats` check before allowing new work.

## Release Evidence

Record these values in the pull request or release note:

- Candidate and rollback image tags and IDs.
- ComfyUI core, Anima compatibility, and LoRA Manager pinned commits.
- Unit test result.
- Batch-size-two prompt ID, elapsed time, output count, and distinct output
  hashes.
- A3000M and 3090 health and capability responses.

Never include `CIVITAI_API_KEY`, request bearer tokens, local model paths beyond
the documented mount roots, or generated image content in a pull request.
