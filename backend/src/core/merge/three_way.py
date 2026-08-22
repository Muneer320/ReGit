"""3-way prose merge — sentence-level, reuses align.py.

Owner: Muneer (H5). Implements ADR-05 / merge-spec.md, incl. the T1-T8
contracts. Decision table is the spec of record. Never silently discard
incompatible changes (invariant 6).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MergeConflictRec:
    sid: str
    base_text: str
    ours_text: str
    theirs_text: str


@dataclass
class MergeResult:
    merged_text: str
    conflicts: list[MergeConflictRec] = field(default_factory=list)
    state: str = "clean"  # "clean" | "conflicts"


def merge_prose(base: str, ours: str, theirs: str) -> MergeResult:
    """Per-sentence decision table (merge-spec.md):

    unchanged both -> keep; one side -> take it; both identical -> convergent;
    both differ -> conflict; delete-vs-modify -> conflict; both insert at same
    anchor -> keep both (ours then theirs), mark insert_conflict.
    """
    raise NotImplementedError("H5: implement per merge-spec.md decision table")
