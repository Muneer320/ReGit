#!/usr/bin/env bash
# ReGit setup (uv-native): sync deps, pre-download embedding model, init store. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

# Dependencies come from pyproject.toml (uv.lock is the resolved lockfile).
uv sync

mkdir -p data/objects data/models

# Pre-download the embedding model so retrieval runs offline at demo time.
uv run python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("all-MiniLM-L6-v2", cache_folder="data/models")
print("model cached")
PY

uv run python -m backend.src.cli init
echo "setup complete"