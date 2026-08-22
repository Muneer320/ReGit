"""gr CLI — init/commit/log/branch/checkout/diff/merge/verify/ingest.

Scaffold: init + verify skeleton real; the rest are H1+ stubs wired to the
ObjectStore. See versioning-spec.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .core.objects.store import ObjectStore

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def cmd_init(data_dir: str = "data") -> None:
    store = ObjectStore(data_dir)
    if SCHEMA_PATH.exists():
        store.db.executescript(SCHEMA_PATH.read_text())
        store.db.commit()
        print(f"gr init: schema applied to {data_dir}/meta.db")
    else:
        print(f"gr init: schema.sql not found at {SCHEMA_PATH} (H0 task)")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: gr init|commit|log|branch|checkout|diff|merge|verify|ingest ...")
        return 2
    cmd = argv[1]
    if cmd == "init":
        cmd_init()
        return 0
    if cmd == "verify":
        raise NotImplementedError("verify: H1 — recompute all hashes (versioning-spec.md)")
    raise NotImplementedError(f"gr {cmd}: see 12h-execution-plan.md milestones")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
