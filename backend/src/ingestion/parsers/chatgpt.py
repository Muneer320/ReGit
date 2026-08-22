"""ChatGPT export adapter (`conversations.json`, ingestion-spec.md).

Export = array of conversations; each has a `mapping` of msg-id -> node with
`{parent, children, message:{author:{role}, content:{parts[], content_type}}}`.
Linearized via chat_common. Volatile fields (node ids, timestamps, key order)
are excluded from identity; re-exporting the same conversation dedups to the
same blob.
"""
from __future__ import annotations

import json

from .base import ParsedUnit, ParseError, compact_json
from .chat_common import build_payload, chatgpt_messages


def parse_chatgpt(filename: str, data: bytes) -> list[ParsedUnit]:
    """Parse a ChatGPT export; returns one ParsedUnit per conversation."""
    try:
        raw = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ParseError(f"ChatGPT export is not valid JSON: {exc}") from exc

    if isinstance(raw, dict):
        # Some exports wrap the array under a key (e.g. "conversations").
        raw = raw.get("conversations") or raw.get("result") or raw.get("messages")
    if not isinstance(raw, list):
        raise ParseError("ChatGPT export must be an array of conversations")

    units: list[ParsedUnit] = []
    for i, conv in enumerate(raw):
        if not isinstance(conv, dict):
            continue
        mapping = conv.get("mapping") or {}
        if not mapping:
            raise ParseError(f"conversation #{i} has no mapping")
        try:
            messages = chatgpt_messages(mapping)
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        if not messages:
            raise ParseError(f"conversation #{i} linearized to zero messages")
        source = "chatgpt"
        payload = build_payload(source, messages)
        unit = ParsedUnit(
            kind="chat",
            title=(conv.get("title") or f"ChatGPT conversation {i + 1}")[:120],
            payload=payload,
            storage_bytes=compact_json(payload),
            kind_tag="chat",
            warnings=[],
        )
        units.append(unit)
    return units