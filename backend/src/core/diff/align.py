"""Prose alignment engine — THE shared primitive (diff + merge + reindex).

Owner: Muneer (H2). Implements ADR-04 / diff-spec.md.
Pipeline: paragraph split -> sentence split -> normalize+hash -> LCS align ->
classify (edited iff similarity >= 0.7). Deterministic by contract: same
inputs -> byte-identical output (pytest asserts exact JSON on fixtures).
No LLM anywhere in this path, and no difflib autojunk.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from ...core.objects.hashutil import short_hash

EDITED_THRESHOLD = 0.7
# Deterministic sentence splitter: a [.!?] followed by whitespace and an
# uppercase letter/digit/quote-opening char splits. Crude with abbreviations
# ("e.g. this" does NOT split) — documented behavior, diff-spec.md.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass(frozen=True)
class AlignOp:
    type: str              # "equal" | "edited" | "delete" | "insert"
    old_i: int | None      # index into the OLD sentence list (None for insert)
    new_i: int | None      # index into the NEW sentence list (None for delete)
    similarity: float = 1.0


def split_paragraphs(text: str) -> list[str]:
    """Blank-line-delimited blocks, canonicalized (stripped, no dangling NL)."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def split_sentences(paragraph: str) -> list[str]:
    return [s for s in _SENT_SPLIT.split(paragraph.strip()) if s.strip()]


def normalize(sentence: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace (diff-spec.md)."""
    s = sentence.lower()
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def sentence_hash(sentence: str) -> str:
    """SHA1-16 of the normalized sentence (diff-spec.md)."""
    return short_hash(normalize(sentence))


def _lcs_backtrack(old_hashes: list[str], new_hashes: list[str]) -> list[AlignOp]:
    """Plain LCS DP + canonical backtrack over hash sequences.

    Deterministic tie-break: on equal DP cells we prefer a DELETE (up) over an
    INSERT (left), so the same inputs always yield the same alignment.
    O(n*m) time and memory — fine at demo scale; a Myers O(ND) variant is a
    size optimization, not a correctness one.
    """
    n, m = len(old_hashes), len(new_hashes)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        row, prev = dp[i], dp[i - 1]
        o = old_hashes[i - 1]
        for j in range(1, m + 1):
            if o == new_hashes[j - 1]:
                row[j] = prev[j - 1] + 1
            else:
                row[j] = prev[j] if prev[j] >= row[j - 1] else row[j - 1]
    ops: list[AlignOp] = []
    i, j = n, m
    while i > 0 and j > 0:
        if old_hashes[i - 1] == new_hashes[j - 1]:
            ops.append(AlignOp("equal", i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            ops.append(AlignOp("delete", i - 1, None))
            i -= 1
        else:
            ops.append(AlignOp("insert", None, j - 1))
            j -= 1
    while i > 0:
        ops.append(AlignOp("delete", i - 1, None))
        i -= 1
    while j > 0:
        ops.append(AlignOp("insert", None, j - 1))
        j -= 1
    ops.reverse()
    return ops


def _classify(ops: list[AlignOp], old: list[str], new: list[str],
              old_hashes: list[str], new_hashes: list[str]) -> list[AlignOp]:
    """Turn raw LCS ops into equal/edited/delete/insert with similarity.

    Equal-hash anchors pass through as "equal". Runs of deletes+inserts that
    sit in the same LCS gap are re-paired:

    1. If the delete run and insert run carry the SAME hash sequence (identical
       text moved within one gap), re-emit as "equal" pairs — diff_prose
       reports these as "moved" when the paragraph index changed.
    2. Otherwise, greedily pair each insert (in order) with the still-unused
       delete of highest difflib ratio (autojunk=False) on the RAW sentences;
       ratio >= EDITED_THRESHOLD -> "edited", else the leftovers stay
       "delete"/"insert".

    Emission order inside a gap: edited/deleted in old order first, then
    unmatched inserts in new order (deterministic; documented crudeness for
    interleaved insertions).
    """
    result: list[AlignOp] = []
    deletes: list[int] = []
    inserts: list[int] = []

    def flush() -> None:
        if not deletes and not inserts:
            return
        # 1) identical-content run -> equal pairs (diff_prose may mark moved)
        if (len(deletes) == len(inserts)
                and all(old_hashes[oi] == new_hashes[nj] for oi, nj in zip(deletes, inserts, strict=True))):
            for oi, nj in zip(deletes, inserts, strict=True):
                result.append(AlignOp("equal", oi, nj))
        else:
            # 2) greedy edit pairing by SequenceMatcher ratio on raw text
            used: set[int] = set()
            pairs: dict[int, tuple[int, float]] = {}
            for nj in inserts:
                best_oi, best_r = None, EDITED_THRESHOLD
                for oi in deletes:
                    if oi in used:
                        continue
                    r = difflib.SequenceMatcher(None, old[oi], new[nj], autojunk=False).ratio()
                    if r > best_r:  # strict > keeps the FIRST (lowest) old index on ties
                        best_oi, best_r = oi, r
                if best_oi is not None:
                    used.add(best_oi)
                    pairs[nj] = (best_oi, best_r)
            matched_new = set(pairs)
            for oi in deletes:
                partner = next((nj for nj, (o, _) in pairs.items() if o == oi), None)
                if partner is not None:
                    result.append(AlignOp("edited", oi, partner, pairs[partner][1]))
                else:
                    result.append(AlignOp("delete", oi, None))
            for nj in inserts:
                if nj not in matched_new:
                    result.append(AlignOp("insert", None, nj))
        deletes.clear()
        inserts.clear()

    for op in ops:
        if op.type == "equal":
            flush()
            result.append(op)
        elif op.type == "delete":
            deletes.append(op.old_i)  # type: ignore[arg-type]  (non-None by construction)
        else:
            inserts.append(op.new_i)  # type: ignore[arg-type]
    flush()
    return result


def align(old: list[str], new: list[str]) -> list[AlignOp]:
    """Own LCS alignment over sentence-hash sequences. Deterministic.

    Classification (diff-spec.md): equal hash -> "equal"; aligned pair with
    differing hashes and raw-text ratio >= 0.7 -> "edited"; otherwise the
    sentences surface as "delete" + "insert". No autojunk (SequenceMatcher is
    always called with autojunk=False); a gap-local identical run collapses
    back to "equal" pairs (reported as "moved" by diff_prose).
    """
    if not old and not new:
        return []
    old_hashes = [sentence_hash(s) for s in old]
    new_hashes = [sentence_hash(s) for s in new]
    return _classify(_lcs_backtrack(old_hashes, new_hashes), old, new,
                     old_hashes, new_hashes)


def _modal_offset(offsets: list[int]) -> int:
    """Dominant paragraph offset among equal pairs (see diff_prose).

    Deterministic tie-break: when counts tie, prefer the offset closest to 0
    (least motion), then the smallest. With no offsets (empty/wholly-changed
    documents) the modal offset is 0, so no pair is spuriously moved."""
    if not offsets:
        return 0
    counts: dict[int, int] = {}
    for o in offsets:
        counts[o] = counts.get(o, 0) + 1
    best_count = max(counts.values())
    if best_count > 1:
        candidates = [o for o, c in counts.items() if c == best_count]
        return min(candidates, key=lambda o: (abs(o), o))
    return 0


def _flatten(paras: list[str]) -> list[tuple[int, int, str]]:
    return [(pi, si, s)
            for pi, p in enumerate(paras)
            for si, s in enumerate(split_sentences(p))]


def diff_prose(old_text: str, new_text: str, artifact_id: str = "") -> list[dict]:
    """Ordered Change dicts per diff-spec.md.

    sid format is "para:sent" (relative to the artifact); when artifact_id is
    given the full data-model.md sid "artifact:para:sent" is emitted. sids
    refer to the FROM commit except for added sentences, which carry their
    TO-commit sid (diff-spec.md). Emits:
      unchanged | edited | moved  -> sid (old), old_text, new_text, similarity
      deleted                     -> sid (old), old_text
      added                       -> sid (new), new_text
    An equal-hash sentence whose paragraph changed position relative to the
    rest of the document (offset from the modal paragraph offset) is reported
    as "moved" (same sid, new position). A uniform index shift — e.g. a
    heading inserted at the top — is NOT a move. Deterministic: same inputs
    -> identical list (and identical JSON via json.dumps).
    """
    old_flat = _flatten(split_paragraphs(old_text))
    new_flat = _flatten(split_paragraphs(new_text))
    prefix = f"{artifact_id}:" if artifact_id else ""
    ops = align([s for _, _, s in old_flat], [s for _, _, s in new_flat])

    # Paragraph offset per equal pair, used to decide "moved". A uniform
    # offset across the whole alignment (e.g. a heading inserted at the top
    # shifts every paragraph index by +1) is NOT a move — the paragraph kept
    # its position relative to the document. A pair whose offset differs from
    # the modal offset genuinely changed position -> "moved".
    offsets = [new_flat[op.new_i][0] - old_flat[op.old_i][0]  # type: ignore[index]
               for op in ops if op.type == "equal"]
    modal = _modal_offset(offsets)

    changes: list[dict] = []
    for op in ops:
        if op.type == "equal":
            opi, osi, otext = old_flat[op.old_i]  # type: ignore[index]
            npi, _nsi, ntext = new_flat[op.new_i]  # type: ignore[index]
            moved = (npi - opi) != modal
            changes.append({
                "sid": f"{prefix}{opi}:{osi}",
                "status": "moved" if moved else "unchanged",
                "old_text": otext,
                "new_text": ntext,
                "similarity": 1.0,
            })
        elif op.type == "edited":
            opi, osi, otext = old_flat[op.old_i]  # type: ignore[index]
            _npi, _nsi, ntext = new_flat[op.new_i]  # type: ignore[index]
            changes.append({
                "sid": f"{prefix}{opi}:{osi}",
                "status": "edited",
                "old_text": otext,
                "new_text": ntext,
                "similarity": op.similarity,
            })
        elif op.type == "delete":
            opi, osi, otext = old_flat[op.old_i]  # type: ignore[index]
            changes.append({
                "sid": f"{prefix}{opi}:{osi}",
                "status": "deleted",
                "old_text": otext,
            })
        else:  # insert -> sid at the TO commit
            npi, nsi, ntext = new_flat[op.new_i]  # type: ignore[index]
            changes.append({
                "sid": f"{prefix}{npi}:{nsi}",
                "status": "added",
                "new_text": ntext,
            })
    return changes