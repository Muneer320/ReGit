"""gr CLI — init | verify | seed | show.

A small, honest CLI. Research artifacts here are one real artifact (id) with
branches, exactly like the API. Most workflows are richer through the API/UI, so
the CLI is kept to commands that are genuinely useful offline in a demo:
  gr init          apply schema + create the store
  gr seed          ingest scripts/fixtures/merge/base.md as a demo artifact
  gr verify        recompute blob hashes and flag tampering
  gr show <id>     print an artifact's commits + branches
"""
from __future__ import annotations

import sys
from pathlib import Path

from .core.objects.hashutil import blob_id
from .core.objects.store import ObjectStore

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"
FIXTURES = Path(__file__).resolve().parents[2] / "scripts" / "fixtures" / "merge"


def _open(data_dir: str) -> ObjectStore:
    store = ObjectStore(data_dir)
    if SCHEMA_PATH.exists():
        store.db.executescript(SCHEMA_PATH.read_text())
        store.db.commit()
    return store


def cmd_init(data_dir: str = "data") -> None:
    _open(data_dir)
    print(f"gr init: schema applied to {data_dir}/meta.db")


def cmd_verify(data_dir: str = "data") -> None:
    store = _open(data_dir)
    bad = total = 0
    for (oid, kind, _size, path) in store.db.execute(
        "SELECT hash, kind, size, path FROM objects"):
        total += 1
        p = Path(path)
        try:
            data = __import__("zlib").decompress(p.read_bytes())
            if blob_id(kind, data) != oid:
                print(f"  tampered/desync: {oid} (kind={kind})")
                bad += 1
        except FileNotFoundError:
            print(f"  missing file: {oid} -> {path}")
            bad += 1
    print(f"gr verify: {total} object(s), {bad} tampered/missing")


def cmd_seed(data_dir: str = "data") -> None:
    store = _open(data_dir)
    art_id = "art_cli_demo"
    if store.db.execute("SELECT 1 FROM artifacts WHERE id=?", (art_id,)).fetchone():
        print("gr seed: artifact art_cli_demo already exists")
        return
    src_id = "src_cli"
    store.db.execute(
        "INSERT OR IGNORE INTO sources(id, type, original_filename, imported_at, uploader) "
        "VALUES (?,?,?,?,?)", (src_id, "markdown", "base.md", "now", "cli"))
    data = (FIXTURES / "base.md").read_bytes()
    store.db.execute(
        "INSERT OR IGNORE INTO artifacts(id, kind, title, source_id, created_at) "
        "VALUES (?,?,?,?,?)", (art_id, "md", "demo notes", src_id, "now"))
    store.db.commit()
    blob_oid = store.put_blob("md", data)
    cid = store.commit([], blob_oid, art_id, "root import", "cli", kind="md")
    print(f"gr seed: art_cli_demo  root={cid}")


def cmd_show(data_dir: str, artifact_id: str) -> None:
    store = _open(data_dir)
    row = store.db.execute(
        "SELECT id, kind, title FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
    if row is None:
        print(f"gr show: unknown artifact {artifact_id}")
        return
    print(f"artifact {row[0]}  ({row[1]})  {row[2]}")
    branches = store.db.execute(
        "SELECT name, head_commit_id FROM branches WHERE artifact_id=? ORDER BY name",
        (artifact_id,)).fetchall()
    for bname, head in branches:
        print(f"  branch {bname} -> {head[:12]}")
    print(f"gr show: {len(branches)} branch(es)")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("gr init|verify|seed|show <artifact_id>   (data dir: pass as 2nd arg)")
        return 2
    cmd = argv[1]
    # data dir: first arg that isn't the artifact id / looks like a path else "data".
    dd = "data"
    art = None
    for a in argv[2:]:
        if a.startswith("art_"):
            art = a
        elif a not in ("data",) and "/" in a or a.endswith("/"):
            dd = a
    try:
        if cmd == "init":
            cmd_init(dd)
        elif cmd == "verify":
            cmd_verify(dd)
        elif cmd == "seed":
            cmd_seed(dd)
        elif cmd == "show":
            cmd_show(dd, art or "art_cli_demo")
        else:
            print(f"gr: unknown command {cmd!r}")
            return 2
    except Exception as exc:  # noqa: BLE001
        print(f"gr {cmd}: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))