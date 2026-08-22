"""Prose alignment engine — THE shared primitive (diff + merge + reindex).

Owner: Muneer (H2). Implements ADR-04 / diff-spec.md.
Pipeline: paragraph split -> sentence split -> normalize+hash -> LCS align ->
classify (edited iff similarity >= 0.7). Deterministic; pytest asserts exact
JSON on fixtures. STUB: signatures + docstrings only.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Optional

from ...core.objects.hashutil import short_hash

EDITED_THRESHOLD = 0.7
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass(frozen=True)
class AlignOp:
    type: str              # "equal" | "edited" | "delete" | "insert"
    old_i: Optional[int]
    new_i: Optional[int]
    similarity: float = 1.0


def split_paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def split_sentences(paragraph: str) -> list[str]:
    return [s for s in _SENT_SPLIT.split(paragraph.strip()) if s.strip()]


def normalize(sentence: str) -> str:
    s = sentence.lower()
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def sentence_hash(sentence: str) -> str:
    return short_hash(normalize(sentence))


def align(old: list[str], new: list[str]) -> list[AlignOp]:
    """Own LCS over sentence-hash sequences. Deterministic.

    TODO(Muneer H2): implement Myers/LCS DP over [sentence_hash(s) for s in ...];
    for aligned pairs with differing hashes, similarity =
    difflib.SequenceMatcher(None, old[i], new[j]).ratio(); classify edited iff
    >= EDITED_THRESHOLD else delete+insert. No autojunk. See diff-spec.md.
    """
    raise NotImplementedError("H2: LCS alignment — see diff-spec.md")


def diff_prose(old_text: str, new_text: str) -> list[dict]:
    """Return ordered Change dicts per diff-spec.md (sid, status, texts)."""
    raise NotImplementedError("H2: build sids + map AlignOps to Change records")
