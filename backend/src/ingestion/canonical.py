"""Canonical chat form + adapter contracts (ingestion-spec.md).

AI-owned adapters (md/chatgpt/claude/pdf/codebase) converge to these
canonical forms; identity hashes EXCLUDE volatile export fields.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..core.objects.hashutil import blob_id


@dataclass(frozen=True)
class ChatMessage:
    ord: int
    role: str            # user|assistant|system
    text: str
    branches: tuple = field(default_factory=tuple)  # alternate subtrees (chatgpt mapping forks)


def canonical_chat_json(messages: list[ChatMessage], source: str) -> bytes:
    payload = {
        "version": 1,
        "source": source,  # "chatgpt" | "claude"
        "messages": [
            {"ord": m.ord, "role": m.role, "text": m.text} for m in messages
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def chat_blob_id(messages: list[ChatMessage], source: str) -> str:
    """Two exports of the same conversation (different ids/timestamps) -> same id."""
    return blob_id("chat", canonical_chat_json(messages, source))
