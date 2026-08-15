import importlib.util
import json
import pathlib
import sys
import unittest

import torch

# ComfyUI selects a CUDA device while importing comfy.sample unless its normal
# command-line CPU switch is present. The node logic under test is CPU-only.
sys.argv = [sys.argv[0], "--cpu"]
import comfy.options
comfy.options.enable_args_parsing()
import comfy.sample


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "custom_nodes"
    / "ComfyUI-Gateway-Batch"
    / "__init__.py"
)
SPEC = importlib.util.spec_from_file_location("gateway_stochastic_sampler", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeNodeOutput:
    def __init__(self, *values):
        self.result = values


class GatewayMultiSeedStochasticSamplerTests(unittest.TestCase):
    def test_samples_members_independently_and_merges_node_output(self):
        calls = []
        original_sampler = MODULE.SamplerCustomAdvanced

        class FakeSamplerCustomAdvanced:
            def sample(self, noise, guider, sampler, sigmas, latent_image):
                calls.append({"seed": noise.seed, "latent": latent_image})
                generated = noise.generate_noise(latent_image)
                return FakeNodeOutput(
                    {"samples": generated, "marker": "sampled"},
                    {"samples": generated, "marker": "denoised"},
                )

        MODULE.SamplerCustomAdvanced = FakeSamplerCustomAdvanced
        try:
            latent = {
                "samples": torch.zeros((2, 4, 8, 8), dtype=torch.float32),
                "noise_mask": torch.ones((2, 1, 8, 8), dtype=torch.float32),
                "batch_index": [8, 9],
            }
            seeds = [123456789, 987654321]
            output, denoised = MODULE.GatewayMultiSeedStochasticSampler().sample(
                json.dumps(seeds), object(), object(), object(), latent
            )
        finally:
            MODULE.SamplerCustomAdvanced = original_sampler

        expected = torch.cat(
            [
                comfy.sample.prepare_noise(latent["samples"][index:index + 1], seed)
                for index, seed in enumerate(seeds)
            ],
            dim=0,
        )
        self.assertEqual([call["seed"] for call in calls], seeds)
        self.assertEqual([call["latent"]["samples"].shape[0] for call in calls], [1, 1])
        self.assertEqual([call["latent"]["noise_mask"].shape[0] for call in calls], [1, 1])
        self.assertEqual([call["latent"]["batch_index"] for call in calls], [[8], [9]])
        self.assertTrue(torch.equal(output["samples"], expected))
        self.assertTrue(torch.equal(denoised["samples"], expected))

    def test_rejects_a_seed_count_that_does_not_match_the_latent_batch(self):
        latent = {"samples": torch.zeros((2, 4, 8, 8), dtype=torch.float32)}
        with self.assertRaisesRegex(ValueError, "does not match"):
            MODULE.GatewayMultiSeedStochasticSampler().sample(
                "[1]", object(), object(), object(), latent
            )


if __name__ == "__main__":
    unittest.main()
