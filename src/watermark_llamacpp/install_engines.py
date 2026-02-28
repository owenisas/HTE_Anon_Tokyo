from __future__ import annotations

import argparse
import shlex
import subprocess
import sys

SUPPORTED_ENGINES: dict[str, list[str]] = {
    "vllm": ["vllm>=0.6.0"],
    "sglang": ["sglang>=0.4.0"],
    "mlx-lm": ["mlx-lm>=0.20.0"],
    "llama-cpp-python": ["llama-cpp-python>=0.3.0"],
    "transformers": ["transformers>=4.45.0"],
}

ALIASES = {
    "mlx": "mlx-lm",
    "mlxlm": "mlx-lm",
    "llama.cpp": "llama-cpp-python",
    "llama-cpp": "llama-cpp-python",
    "llama_cpp": "llama-cpp-python",
    "llamacpp": "llama-cpp-python",
    "hf": "transformers",
}


def _normalize_engine_name(value: str) -> str:
    v = value.strip().lower()
    return ALIASES.get(v, v)


def resolve_engines(engines_csv: str | None) -> list[str]:
    if engines_csv is None or engines_csv.strip() == "" or engines_csv.strip().lower() == "all":
        return list(SUPPORTED_ENGINES.keys())

    resolved: list[str] = []
    seen: set[str] = set()
    for part in engines_csv.split(","):
        engine = _normalize_engine_name(part)
        if engine not in SUPPORTED_ENGINES:
            valid = ", ".join(SUPPORTED_ENGINES.keys())
            raise ValueError(f"unknown engine '{part.strip()}'; valid values: {valid}, all")
        if engine not in seen:
            resolved.append(engine)
            seen.add(engine)
    return resolved


def packages_for_engines(engines: list[str]) -> list[str]:
    packages: list[str] = []
    seen: set[str] = set()
    for engine in engines:
        for pkg in SUPPORTED_ENGINES[engine]:
            if pkg not in seen:
                packages.append(pkg)
                seen.add(pkg)
    return packages


def build_pip_install_command(
    *,
    python_executable: str,
    packages: list[str],
    upgrade: bool,
    extra_index_url: str | None,
    pre: bool,
) -> list[str]:
    cmd = [python_executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    if pre:
        cmd.append("--pre")
    if extra_index_url:
        cmd.extend(["--extra-index-url", extra_index_url])
    cmd.extend(packages)
    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fast installer for watermark integrations across inference SDKs"
    )
    parser.add_argument(
        "--engines",
        default="all",
        help="Comma-separated engines: vllm,sglang,mlx-lm,llama-cpp-python,transformers or 'all'",
    )
    parser.add_argument("--upgrade", action="store_true", help="Upgrade packages to newest versions")
    parser.add_argument(
        "--extra-index-url",
        default=None,
        help="Optional extra Python index (useful for CUDA wheels)",
    )
    parser.add_argument("--pre", action="store_true", help="Allow pre-release packages")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved pip command only")
    parser.add_argument("--list-engines", action="store_true", help="List supported engines and exit")
    args = parser.parse_args()

    if args.list_engines:
        for engine, pkgs in SUPPORTED_ENGINES.items():
            print(f"{engine}: {', '.join(pkgs)}")
        return

    try:
        engines = resolve_engines(args.engines)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    packages = packages_for_engines(engines)
    cmd = build_pip_install_command(
        python_executable=args.python,
        packages=packages,
        upgrade=args.upgrade,
        extra_index_url=args.extra_index_url,
        pre=args.pre,
    )

    print(f"Selected engines: {', '.join(engines)}")
    print(f"Resolved packages: {', '.join(packages)}")
    print("Command:", shlex.join(cmd))

    if args.dry_run:
        return

    subprocess.run(cmd, check=True)
    print("Installation completed.")


if __name__ == "__main__":
    main()
