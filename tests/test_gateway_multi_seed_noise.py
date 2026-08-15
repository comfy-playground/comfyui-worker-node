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
SPEC = importlib.util.spec_from_file_location("gateway_multi_seed_noise", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GatewayMultiSeedNoiseTests(unittest.TestCase):
    def test_matches_independent_prepare_noise_calls(self):
        latent = {"samples": torch.zeros((3, 4, 8, 8), dtype=torch.float32)}
        seeds = [123456789, 987654321, 42]
        noise = MODULE.GatewayMultiSeedNoiseData(seeds).generate_noise(latent)
        expected = torch.cat(
            [
                comfy.sample.prepare_noise(latent["samples"][index:index + 1], seed)
                for index, seed in enumerate(seeds)
            ],
            dim=0,
        )
        self.assertTrue(torch.equal(noise, expected))

    def test_accepts_decimal_strings_without_losing_uint64_precision(self):
        parsed = MODULE._parse_seeds(json.dumps(["0", str(MODULE.MAX_SEED)]))
        self.assertEqual(parsed, [0, MODULE.MAX_SEED])

    def test_rejects_invalid_seed_values_and_batch_sizes(self):
        invalid = [
            "{}",
            "[]",
            "[true]",
            "[-1]",
            "[1.5]",
            json.dumps([str(MODULE.MAX_SEED + 1)]),
            json.dumps(list(range(MODULE.MAX_BATCH_SIZE + 1))),
        ]
        for raw_value in invalid:
            with self.subTest(raw_value=raw_value):
                with self.assertRaises(ValueError):
                    MODULE._parse_seeds(raw_value)

    def test_requires_one_seed_per_batch_member(self):
        latent = {"samples": torch.zeros((2, 4, 8, 8), dtype=torch.float32)}
        with self.assertRaisesRegex(ValueError, "does not match"):
            MODULE.GatewayMultiSeedNoiseData([1]).generate_noise(latent)


if __name__ == "__main__":
    unittest.main()
