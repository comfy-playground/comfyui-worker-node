import json
import re

import torch

import comfy.sample
from comfy_extras.nodes_custom_sampler import SamplerCustomAdvanced


MAX_BATCH_SIZE = 16
MAX_STOCHASTIC_BATCH_SIZE = 4
MAX_SEED = 0xFFFFFFFFFFFFFFFF
_DECIMAL_SEED = re.compile(r"^(0|[1-9][0-9]*)$")


def _parse_seeds(raw_value, maximum=MAX_BATCH_SIZE):
    try:
        values = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("seeds must be a JSON array of unsigned integers") from exc

    if not isinstance(values, list):
        raise ValueError("seeds must be a JSON array")
    if not 1 <= len(values) <= maximum:
        raise ValueError(f"seeds must contain between 1 and {maximum} items")

    seeds = []
    for index, value in enumerate(values):
        if isinstance(value, bool):
            raise ValueError(f"seed at index {index} is not an unsigned integer")
        if isinstance(value, int):
            seed = value
        elif isinstance(value, str) and _DECIMAL_SEED.fullmatch(value):
            seed = int(value, 10)
        else:
            raise ValueError(f"seed at index {index} is not an unsigned integer")
        if seed < 0 or seed > MAX_SEED:
            raise ValueError(f"seed at index {index} is outside the uint64 range")
        seeds.append(seed)
    return seeds


class GatewayMultiSeedNoiseData:
    def __init__(self, seeds):
        self.seeds = tuple(seeds)
        self.seed = self.seeds[0]

    def generate_noise(self, input_latent):
        latent_image = input_latent["samples"]
        if latent_image.is_nested:
            raise ValueError("GatewayMultiSeedNoise does not support nested latent tensors")

        batch_size = latent_image.shape[0]
        if batch_size != len(self.seeds):
            raise ValueError(
                f"latent batch size {batch_size} does not match {len(self.seeds)} seeds"
            )

        noises = [
            comfy.sample.prepare_noise(latent_image[index:index + 1], seed)
            for index, seed in enumerate(self.seeds)
        ]
        return torch.cat(noises, dim=0)


def _member_latent(latent_image, member_index, batch_size):
    member = dict(latent_image)
    samples = latent_image["samples"]
    member["samples"] = samples[member_index:member_index + 1]

    noise_mask = latent_image.get("noise_mask")
    if torch.is_tensor(noise_mask) and noise_mask.ndim > 0 and noise_mask.shape[0] == batch_size:
        member["noise_mask"] = noise_mask[member_index:member_index + 1]

    batch_index = latent_image.get("batch_index")
    if isinstance(batch_index, (list, tuple)) and len(batch_index) == batch_size:
        member["batch_index"] = [batch_index[member_index]]
    return member


class GatewayMultiSeedNoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seeds": (
                    "STRING",
                    {
                        "default": '["0"]',
                        "multiline": False,
                        "tooltip": "JSON array of one uint64 seed per latent batch member.",
                    },
                )
            }
        }

    RETURN_TYPES = ("NOISE",)
    RETURN_NAMES = ("noise",)
    FUNCTION = "get_noise"
    CATEGORY = "gateway/sampling"
    DESCRIPTION = "Creates one independently seeded noise tensor per latent batch member."

    def get_noise(self, seeds):
        return (GatewayMultiSeedNoiseData(_parse_seeds(seeds)),)


class GatewayMultiSeedStochasticSampler:
    """Runs stochastic sampling with an independent RNG stream per member.

    The node keeps the same GUIDER/SAMPLER/SIGMAS/LATENT contract as
    SamplerCustomAdvanced. It invokes ComfyUI's implementation once per member
    so samplers such as er_sde cannot share a scalar Brownian/RNG seed. The
    merged latent is returned through output 0, leaving downstream workflow
    node IDs and connections unchanged.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seeds": (
                    "STRING",
                    {
                        "default": '["0"]',
                        "multiline": False,
                        "tooltip": "JSON array of one uint64 seed per latent batch member.",
                    },
                ),
                "guider": ("GUIDER",),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "latent_image": ("LATENT",),
            }
        }

    RETURN_TYPES = ("LATENT", "LATENT")
    RETURN_NAMES = ("output", "denoised_output")
    FUNCTION = "sample"
    CATEGORY = "sampling/custom_advanced"
    DESCRIPTION = "Runs stochastic sampling with independent per-member RNG streams."

    def sample(self, seeds, guider, sampler, sigmas, latent_image):
        parsed_seeds = _parse_seeds(seeds, MAX_STOCHASTIC_BATCH_SIZE)
        samples = latent_image.get("samples")
        if not torch.is_tensor(samples) or samples.ndim == 0:
            raise ValueError("latent_image.samples must be a tensor")
        if samples.shape[0] != len(parsed_seeds):
            raise ValueError(
                f"latent batch size {samples.shape[0]} does not match {len(parsed_seeds)} seeds"
            )

        sampler_node = SamplerCustomAdvanced()
        outputs = []
        denoised_outputs = []
        for member_index, seed in enumerate(parsed_seeds):
            member = _member_latent(latent_image, member_index, samples.shape[0])
            result = sampler_node.sample(
                GatewayMultiSeedNoiseData([seed]), guider, sampler, sigmas, member
            )
            # ComfyUI 0.30 wraps node results in io.NodeOutput. Older pinned
            # versions returned the output tuple directly.
            result = getattr(result, "result", result)
            if not isinstance(result, tuple) or len(result) < 1:
                raise RuntimeError("ComfyUI SamplerCustomAdvanced returned an invalid result")
            output = result[0]
            if not isinstance(output, dict) or not torch.is_tensor(output.get("samples")):
                raise RuntimeError("ComfyUI sampler returned an invalid latent output")
            outputs.append(output)
            if len(result) > 1 and isinstance(result[1], dict):
                denoised_outputs.append(result[1])

        merged = dict(outputs[0])
        merged["samples"] = torch.cat([output["samples"] for output in outputs], dim=0)
        if denoised_outputs:
            denoised = dict(denoised_outputs[0])
            denoised["samples"] = torch.cat(
                [output["samples"] for output in denoised_outputs], dim=0
            )
        else:
            denoised = merged
        return (merged, denoised)


NODE_CLASS_MAPPINGS = {
    "GatewayMultiSeedNoise": GatewayMultiSeedNoise,
    "GatewayMultiSeedStochasticSampler": GatewayMultiSeedStochasticSampler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GatewayMultiSeedNoise": "Gateway Multi-Seed Noise",
    "GatewayMultiSeedStochasticSampler": "Gateway Multi-Seed Stochastic Sampler",
}
