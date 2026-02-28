from __future__ import annotations

import unittest

from watermark_llamacpp.install_engines import (
    build_pip_install_command,
    packages_for_engines,
    resolve_engines,
)


class InstallEnginesTests(unittest.TestCase):
    def test_resolve_all(self) -> None:
        engines = resolve_engines("all")
        self.assertIn("vllm", engines)
        self.assertIn("mlx-lm", engines)

    def test_resolve_aliases(self) -> None:
        engines = resolve_engines("mlx,llama.cpp,hf")
        self.assertEqual(engines, ["mlx-lm", "llama-cpp-python", "transformers"])

    def test_resolve_invalid(self) -> None:
        with self.assertRaises(ValueError):
            resolve_engines("does-not-exist")

    def test_package_resolution(self) -> None:
        pkgs = packages_for_engines(["vllm", "transformers"])
        self.assertTrue(any(pkg.startswith("vllm") for pkg in pkgs))
        self.assertTrue(any(pkg.startswith("transformers") for pkg in pkgs))

    def test_build_install_command(self) -> None:
        cmd = build_pip_install_command(
            python_executable="python3",
            packages=["vllm>=0.6.0"],
            upgrade=True,
            extra_index_url="https://example.com/simple",
            pre=True,
        )
        self.assertEqual(cmd[:4], ["python3", "-m", "pip", "install"])
        self.assertIn("--upgrade", cmd)
        self.assertIn("--pre", cmd)
        self.assertIn("--extra-index-url", cmd)
        self.assertIn("https://example.com/simple", cmd)


if __name__ == "__main__":
    unittest.main()
