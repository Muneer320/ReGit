"""Claude export adapter (JSONL / zip-of-JSONL, ingestion-spec.md).

Each line is a conversation with `chat_messages[]`:
  {role, content:[{type:"text",text},{type:"tool_use",...}], timestamp}.
Only `type=="text"` blocks are joined per message; `tool_use` becomes a
`[tool: name]` placeholder line. This is a SEPARATE schema from ChatGPT's —
separate adapter, separate fixtures, both converge to the same canonical chat
form.
"""
from __future__ import annotations

import io
import json
import zipfile

from .base import ParsedUnit, ParseError, compact_json
from .chat_common import build_payload, claude_messages


def _parse_stream(text: str, filename: str) -> list[ParsedUnit]:
    units: list[ParsedUnit] = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            conv = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Claude export JSONL line {i + 1} invalid: {exc}") from exc
        chat_messages = conv.get("chat_messages") or []
        messages = claude_messages(chat_messages)
        if not messages:
            continue
        source = "claude"
        payload = build_payload(source, messages)
        title = (conv.get("name") or conv.get("title") or f"Claude conversation {i + 1}")[:120]
        units.append(
            ParsedUnit(
                kind="chat",
                title=title,
                payload=payload,
                storage_bytes=compact_json(payload),
                kind_tag="chat",
                warnings=[],
            )
        )
    return units


def _from_jsonl(data: bytes, filename: str) -> list[ParsedUnit]:
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return _parse_stream(data.decode(enc), filename)
        except UnicodeDecodeError:
            continue
    return _parse_stream(data.decode("utf-8", errors="replace"), filename)


def parse_claude(filename: str, data: bytes) -> list[ParsedUnit]:
    """Accept either a plain .jsonl file or a .zip containing .jsonl files."""
    if data[:2] == b"PK" or filename.lower().endswith(".zip"):
        return _from_zip(data, filename)
    return _from_jsonl(data, filename)


def _from_zip(data: bytes, filename: str) -> list[ParsedUnit]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ParseError(f"Claude export zip is corrupt: {exc}") from exc
    names = [n for n in zf.namelist() if n.lower().endswith(".jsonl")]
    if not names:
        raise ParseError("Claude export zip contains no .jsonl files")
    units: list[ParsedUnit] = []
    for name in names:
        units.extend(_from_jsonl(zf.read(name), name))
    return units