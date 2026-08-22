#!/usr/bin/env bash
# H0 setup: venv, deps, embedding model pre-download, gr init. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install --disable-pip-version-check -r requirements.txt
mkdir -p data/objects data/models
python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("all-MiniLM-L6-v2", cache_folder="data/models")
print("model cached")
PY
python -m backend.src.cli init
echo "setup complete"
