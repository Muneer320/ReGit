"""Codebase adapter (ingestion-spec.md) — git repo dir or zip walk.

Walks files (skipping .git, binaries, >1MB), producing per-file blobs plus a
tree. The canonical root for a codebase artifact is a TREE — file structure is
preserved, never flattened. Primary semantic language Python; other files use
a line-diff fallback at diff time. Per-file blob ids are content hashes, so a
tree hash is stable across identical inputs.
"""
from __future__ import annotations

import io
import zipfile

from ...core.objects.hashutil import blob_id, tree_id
from .base import CodeFile, ParsedUnit, ParseError, compact_json

MAX_FILE_BYTES = 1_000_000  # >1MB -> skipped with a warning
_KIND = "code-file"


def parse_codebase(filename: str, data: bytes) -> ParsedUnit:
    """data is either a tarball/zip, or (rarely) a plain list-of-paths json."""
    files_bytes: dict[str, bytes] = {}

    if data[:2] == b"PK" or filename.lower().endswith((".zip", ".tar", ".tgz")):
        files_bytes = _collect_zip(data)
    elif data[:1] == b"[":
        files_bytes = _collect_json_paths(data)
    else:
        raise ParseError(
            "codebase must be a .zip (or a JSON list of {'path','data'} maps)"
        )

    if not files_bytes:
        raise ParseError("codebase archive is empty (no text files found)")

    code_files: list[CodeFile] = []
    warnings: list[str] = []
    for path in sorted(files_bytes):
        raw = files_bytes[path]
        if _is_binary(raw):
            warnings.append(f"skipped binary file: {path}")
            continue
        if len(raw) > MAX_FILE_BYTES:
            warnings.append(f"skipped oversized file (>1MB): {path}")
            continue
        code_files.append(
            CodeFile(path=path, kind=_KIND, data=raw, blob_id=blob_id(_KIND, raw))
        )

    entries = [(f.path, f.blob_id, _KIND) for f in code_files]
    root_tree_id = tree_id(entries)
    tree_canon = compact_json(sorted(([p, b, _KIND] for p, b, _ in entries)))
    payload = {
        "version": 1,
        "files": [{"path": f.path, "kind": _KIND, "blob_id": f.blob_id} for f in code_files],
        "root_tree_id": root_tree_id,
    }
    return ParsedUnit(
        kind="codebase",
        title=filename or "codebase",
        payload=payload,
        storage_bytes=tree_canon,
        kind_tag="tree",
        warnings=warnings,
        files=code_files,
    )


def _collect_zip(data: bytes) -> dict[str, bytes]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ParseError(f"codebase zip is corrupt: {exc}") from exc
    out: dict[str, bytes] = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        path = info.filename.lstrip("./")
        if _skip_path(path):
            continue
        try:
            out[path] = zf.read(info)
        except (RuntimeError, KeyError) as exc:  # password / bad member
            raise ParseError(f"could not read archive member {info.filename}: {exc}") from exc
    return out


def _collect_json_paths(data: bytes) -> dict[str, bytes]:
    import json

    try:
        items = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ParseError(f"codebase path-list JSON invalid: {exc}") from exc
    out: dict[str, bytes] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        path = (item.get("path") or "").lstrip("./")
        if _skip_path(path):
            continue
        val = item.get("data") or item.get("content")
        out[path] = val.encode() if isinstance(val, str) else bytes(val or b"")
    return out


def _skip_path(path: str) -> bool:
    parts = set(path.split("/"))
    if ".git" in parts:
        return True
    if path.startswith(".git/"):
        return True
    return False


def _is_binary(raw: bytes) -> bool:
    return b"\x00" in raw[:8192]