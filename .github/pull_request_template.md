## Summary

- What worker, workflow, or custom-node behavior changed?
- Why is the change needed?

## Image And Compatibility

- [ ] `COMFYUI_REF` change is documented, or unchanged.
- [ ] LoRA Manager and Anima compatibility pins are documented, or unchanged.
- [ ] No model weights, outputs, cache, `.env`, or secrets are included.

## Validation

- [ ] `docker compose config` passed.
- [ ] Custom-node unit tests passed.
- [ ] Worker started and `/system_stats` passed.
- [ ] Required custom-node capability appeared in `/object_info`.
- [ ] If batch behavior changed, batch size two completed with two distinct output files.

## Deployment And Rollback

- Candidate image tag and ID:
- Primary rollback image tag and ID:
- RTX 3090 deployment image tag and ID, if deployed:
- RTX 3090 rollback image tag and ID, if deployed:
- Gateway reachability checked, if deployed:

## Documentation

- [ ] README, architecture, operations, and `AGENTS.md` reflect the change.
- [ ] Workflow node IDs and positive/negative/output links are unchanged, or the gateway contract update is documented.
