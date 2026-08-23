#!/usr/bin/env python3
"""ReGit setup — cross-platform (Windows / macOS / Linux), uv-native.

Replaces scripts/setup.sh for machines without bash (e.g. Windows, where
`bash scripts/setup.sh` fails with WSL '/bin/bash' errors). Does the same
job, idempotently:
  1. uv sync          (deps from pyproject.toml / uv.lock)
  2. mkdir data/
  3. pre-download the MiniLM embedding model into data/models (offline demo)
  4. init the object store via the CLI

Usage (from the repo root):
    python scripts/setup.py          # or: py scripts/setup.py  (Windows)
    uv run python scripts/setup.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def need(cmd: str) -> None:
    if shutil.which(cmd) is None:
        print(
            f"\n  x '{cmd}' not found on PATH.\n"
            f"    Install it first, then re-run this script.\n"
            f"    uv install - Windows:  powershell -c "
            f"\"irm https://astral.sh/uv/install.ps1 | iex\"\n"
            f"               macOS/Linux: curl -LsSf "
            f"https://astral.sh/uv/install.sh | sh",
            flush=True,
        )
        sys.exit(1)


def main() -> int:
    print("ReGit setup (cross-platform, uv-native)")
    need("uv")

    # 1. deps
    run(["uv", "sync"])

    # 2. dirs
    (ROOT / "data" / "objects").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "models").mkdir(parents=True, exist_ok=True)

    # 3. embedding model (once) so retrieval is offline at demo time
    model_cache = ROOT / "data" / "models"
    cached = any(
        p.name.startswith("models--sentence-transformers--all-MiniLM")
        for p in model_cache.iterdir()
    ) if model_cache.exists() else False
    if cached:
        print("model already cached - skipping download")
    else:
        run(["uv", "run", "python", "-c",
             "from sentence_transformers import SentenceTransformer; "
             "SentenceTransformer('all-MiniLM-L6-v2', "
             f"cache_folder=r'{model_cache}'); print('model cached')"])

    # 4. init store (schema)
    run(["uv", "run", "python", "-m", "backend.src.cli", "init"])

    print("\nOK setup complete. Start the app:")
    print("    uv run uvicorn backend.src.api.main:app --port 8377")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())