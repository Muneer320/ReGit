#!/usr/bin/env python3
"""Rebuild the retrieval index from the object store (spec fallback).

retrieval-spec.md fallbacks: "Chroma broken -> rebuild from object store
(scripts/reindex.py)". The index is DERIVED data — wiping and rebuilding it
from the immutable commit DAG never touches objects/commits.

Usage: uv run python scripts/reindex.py [data_dir]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.src.core.objects.store import ObjectStore  # noqa: E402
from backend.src.retrieval.indexer import Indexer, get_vector_store  # noqa: E402


def main(argv: list[str]) -> int:
    data_dir = argv[1] if len(argv) > 1 else "data"
    store = ObjectStore(data_dir)
    try:
        vector = get_vector_store(store, data_dir=data_dir)
    except Exception as exc:  # vectors optional — degrade, do not abort
        print(f"warning: vectors unavailable ({exc}); FTS5-only index")
        vector = None
    outcomes = Indexer(store, vector).rebuild()
    n_del = sum(len(o.deleted_chunk_ids) for o in outcomes)
    n_up = sum(len(o.upserted_chunk_ids) for o in outcomes)
    n_vec_fail = sum(1 for o in outcomes if not o.vector_ok)
    print(f"reindex: {len(outcomes)} commits processed, "
          f"{n_up} chunks upserted, {n_del} deleted, {n_vec_fail} vector failures")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))