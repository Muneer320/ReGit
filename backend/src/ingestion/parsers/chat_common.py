"""Shared canonical-chat machinery (ingestion-spec.md).

Both the ChatGPT and Claude adapters converge to the SAME canonical chat form.
Volatile export fields (message ids, node ids, timestamps, object key order)
are EXCLUDED from the identity so re-exporting an identical conversation
dedups to the same blob. Branch forks (ChatGPT mapping) are preserved as a
`branches` metadata field on the parent message.
"""
from __future__ import annotations

from collections.abc import Iterable

from ..canonical import ChatMessage
from .base import compact_json

# Roles we keep; everything else (tool, system-noise, etc.) is dropped.
_KEEP_ROLES = {"user", "assistant", "system"}


def build_payload(source: str, messages: Iterable[ChatMessage]) -> dict:
    """Canonical chat payload dict. Volatile fields never present."""
    msgs = []
    for m in messages:
        entry = {"ord": m.ord, "role": m.role, "text": m.text}
        if m.branches:
            entry["branches"] = list(m.branches)
        msgs.append(entry)
    return {"version": 1, "source": source, "messages": msgs}


def chat_storage_bytes(source: str, messages: Iterable[ChatMessage]) -> bytes:
    """Exact canonical bytes used as the blob identity for a chat artifact."""
    return compact_json(build_payload(source, messages))


def chat_identity(source: str, messages: Iterable[ChatMessage]) -> str:
    """Blob id via canonical.py's identity helper (without volatile fields).

    For branch-free conversations this is byte-identical to canonical.py's
    canonical_chat_json() output, so the two implementations agree exactly.
    """
    from ...core.objects.hashutil import blob_id

    return blob_id("chat", chat_storage_bytes(source, messages))


def chatgpt_messages(mapping: dict) -> list[ChatMessage]:
    """Linearize a ChatGPT `mapping` dict into canonical ChatMessages.

    Root = node whose `parent` is null/absent; walk primary children in
    `children` array order; alternate child subtrees become `branches` on the
    branching message. Extracts text parts; drops non-text parts.
    """
    nodes = mapping or {}
    by_id = {mid: n for mid, n in nodes.items() if isinstance(n, dict)}

    def parent_of(node: dict):
        return node.get("parent")

    def is_root(mid: str, node: dict):
        p = parent_of(node)
        return p is None or p not in by_id

    roots = [mid for mid, node in by_id.items() if is_root(mid, node)]
    if not roots:
        raise ValueError("ChatGPT export has no root message (no parent==null node)")

    messages: list[ChatMessage] = []

    def msg_text(node: dict) -> tuple[str, list[str]]:
        """Return (text, warnings) for a single mapping node."""
        msg = node.get("message") or {}
        content = msg.get("content") or {}
        if isinstance(content, str):
            return content, []
        parts = content.get("parts") or []
        text_parts = [p for p in parts if isinstance(p, str) and p]
        return "\n".join(text_parts), []

    def role_of(node: dict) -> str:
        msg = node.get("message") or {}
        author = msg.get("author") or {}
        role = author.get("role") or ""
        return role if role in _KEEP_ROLES else ""

    def subtree_text(mid: str) -> tuple:
        """Linearize a subtree as ((role, text), ...) (branch metadata)."""
        out: list[tuple] = []
        cur = by_id.get(mid)
        seen = set()
        while cur is not None and mid not in seen:
            seen.add(mid)
            role = role_of(cur)
            text, _ = msg_text(cur)
            if role and text:
                out.append((role, text))
            children = cur.get("children") or []
            if not children:
                break
            mid = children[0]
            cur = by_id.get(mid)
        return tuple(out)

    # Depth-first walk starting from each root in mapping order.
    def walk(mid: str, seen: set):
        if mid in seen:
            return
        seen.add(mid)
        node = by_id.get(mid)
        if node is None:
            return
        role = role_of(node)
        text, _warn = msg_text(node)
        if role and text:
            branches: list[tuple] = []
            children = node.get("children") or []
            if len(children) > 1:
                for alt in children[1:]:
                    branches.append(subtree_text(alt))
            messages.append(ChatMessage(len(messages), role, text, tuple(branches)))
        children = node.get("children") or []
        if children:
            walk(children[0], seen)

    seen: set = set()
    for mid in roots:
        walk(mid, seen)
    # Only single-branch subtrees were walked by the primary path above; also
    # walk any child subtrees we skipped so nothing is lost from the canonical
    # payload structure.
    for mid, node in by_id.items():
        if mid in seen or role_of(node) not in _KEEP_ROLES:
            continue
        if mid in seen:
            continue
        walk(mid, seen)

    return messages


def claude_messages(chat_messages: list) -> list[ChatMessage]:
    """Linearize a Claude export `chat_messages[]` into canonical ChatMessages.

    Text content blocks joined per message; `tool_use` blocks become a
    `[tool: name]` placeholder line so tool activity is visible but not parsed
    as prose.
    """
    messages: list[ChatMessage] = []
    for entry in chat_messages or []:
        if not isinstance(entry, dict):
            continue
        role = (entry.get("role") or "").strip().lower()
        if role not in _KEEP_ROLES:
            continue
        blocks = entry.get("content") or []
        if isinstance(blocks, str):
            text = blocks
        else:
            text = _render_blocks(blocks)
        if text.strip():
            messages.append(ChatMessage(len(messages), role, text))
    return messages


def _render_blocks(content) -> str:
    lines: list[str] = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type") or ""
        if btype == "text":
            t = block.get("text") or ""
            if t.strip():
                lines.append(t)
        elif btype == "tool_use":
            name = block.get("name") or "unknown"
            lines.append(f"[tool: {name}]")
    return "\n".join(lines).strip("\n")