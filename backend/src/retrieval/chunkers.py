"""Per-kind chunkers (ADR-11 table) — deterministic by contract.

| Type | Chunker | Size |
|---|---|---|
| Markdown/txt | heading-section split, sentence-merged | ≤600 chars, 10% overlap; id = section path |
| Chat | 1 message = 1 chunk, `role:` prefix | variable |
| PDF | page → paragraph blocks (sentence windows) | ≤800 chars |
| Code | tree-sitter function/class spans (line-scan fallback) | ≤120 lines |

Every chunker is a pure function of (payload/text, artifact_id, branch):
same inputs -> byte-identical chunks (ids, texts, sid sets). Chunk ids are
stable per (artifact, branch, position) so the delta indexer can recognize
unchanged chunks across commits and only churn what actually changed.

Sid conventions (data-model.md):
- prose      `artifact:para:sent`
- chat       `artifact:msg:{ord}:{role}`
- pdf        `artifact:p{page}:{pidx}:{sidx}`
- code       `artifact:{file_path}::{qualified_name}`
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..core.diff.align import split_paragraphs, split_sentences
from ..core.objects.hashutil import short_hash

MD_MAX_CHARS = 600
MD_OVERLAP = 0.10
PDF_MAX_CHARS = 800
CODE_MAX_LINES = 120

_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
# Top-level def/class only (indentation preserved so method defs are skipped).
_DEF_RE = re.compile(r"^(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)\b")

# tree-sitter node types we treat as chunkable units.
_DEF_NODE_TYPES = {"function_definition", "class_definition", "decorated_definition"}


@dataclass(frozen=True)
class Chunk:
    """One atomic retrieval unit + its provenance spine (sid coverage)."""

    chunk_id: str
    artifact_id: str
    branch: str
    kind: str
    text: str
    sids: tuple[str, ...]           # sids covered by this chunk (doc order)
    sid_range: str = ""             # JSON list of sids (chunks.sid_range column)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sid_range", _json_list(self.sids))


def _json_list(items) -> str:
    import json

    return json.dumps(list(items), ensure_ascii=False, separators=(",", ":"))


def _art_short(artifact_id: str) -> str:
    return short_hash(artifact_id)[:8]


def _slug(path: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", path.strip().lower()).strip("-")
    return s or "doc"


def _sentence_grid(text: str) -> list[tuple[int, int, str]]:
    """Global (para_idx, sent_idx, text) grid; sid = f'{artifact}:{pi}:{si}'."""
    return [
        (pi, si, s)
        for pi, p in enumerate(split_paragraphs(text))
        for si, s in enumerate(split_sentences(p))
    ]


def _windows(sents: list[str], max_chars: int, overlap: float) -> list[list[int]]:
    """Sentence windows <= max_chars with fractional overlap. Deterministic.

    Greedy fill; a single sentence longer than max_chars becomes its own
    window (hard overflow, documented). overlap is applied in sentences
    (rounded) and clamped so the window always advances.
    """
    if not sents:
        return []
    windows: list[list[int]] = []
    i = 0
    n = len(sents)
    while i < n:
        end, length = i, 0
        while end < n:
            add = len(sents[end]) + (1 if length else 0)
            if length and length + add > max_chars:
                break
            length += add
            end += 1
        if end == i:
            end = i + 1
        step = end - i
        windows.append(list(range(i, end)))
        if end >= n:
            break
        ov = max(1, round(overlap * step))
        if ov >= step:
            ov = step - 1
        i = end - ov if ov > 0 else end
    return windows


def _split_windows(
    artifact_id: str, branch: str, kind: str,
    base_id: str, grid: list[tuple[int, int, str]],
    max_chars: int, overlap: float,
) -> list[Chunk]:
    """Turn a sentence grid slice into window chunks (shared by md/pdf)."""
    sents = [s for _, _, s in grid]
    windows = _windows(sents, max_chars, overlap)
    out: list[Chunk] = []
    for w_i, idxs in enumerate(windows):
        cid = f"{_art_short(artifact_id)}:{branch}:{base_id}" + (f"#{w_i}" if len(windows) > 1 else "")
        sids = tuple(f"{artifact_id}:{grid[i][0]}:{grid[i][1]}" for i in idxs)
        text = " ".join(sents[i] for i in idxs)
        out.append(Chunk(cid, artifact_id, branch, kind, text, sids))
    return out


def chunk_markdown(text: str, artifact_id: str, branch: str = "main") -> list[Chunk]:
    """md/txt: heading sections (id = section path), sentence windows <=600, 10% overlap.

    A section = one heading paragraph + everything below it until the next
    heading. Text without headings is a single section (path 'doc'). Headings
    participate in the sentence grid, so the first window of a section carries
    the heading text (searchable).
    """
    paras = split_paragraphs(text)
    grid = _sentence_grid(text)
    heading_idx = [pi for pi, p in enumerate(paras) if _HEADING_RE.match(p)]

    if not heading_idx:
        return _split_windows(artifact_id, branch, "md", "doc", grid, MD_MAX_CHARS, MD_OVERLAP)

    sections: list[tuple[str, int, int]] = []
    if heading_idx[0] > 0:
        sections.append(("preamble", 0, heading_idx[0]))
    for k, hp in enumerate(heading_idx):
        end = heading_idx[k + 1] if k + 1 < len(heading_idx) else len(paras)
        sections.append((_slug(paras[hp]), hp, end))

    out: list[Chunk] = []
    for path, p_start, p_end in sections:
        sec_grid = [(pi, si, s) for pi, si, s in grid if p_start <= pi < p_end]
        out.extend(_split_windows(artifact_id, branch, "md", path, sec_grid, MD_MAX_CHARS, MD_OVERLAP))
    return out


def chunk_chat(messages: list[dict], artifact_id: str, branch: str = "main") -> list[Chunk]:
    """Chat: 1 message = 1 chunk; text prefixed with `role: ` (ADR-11)."""
    out: list[Chunk] = []
    for m in messages:
        ord_ = m["ord"]
        role = m["role"]
        text = m["text"]
        sid = f"{artifact_id}:msg:{ord_}:{role}"
        cid = f"{_art_short(artifact_id)}:{branch}:msg:{ord_}:{role}"
        out.append(Chunk(cid, artifact_id, branch, "chat", f"{role}: {text}", (sid,)))
    return out


def chunk_pdf(pages: list[dict], artifact_id: str, branch: str = "main") -> list[Chunk]:
    """PDF: page -> paragraph blocks (sentence windows) <=800 chars, no overlap."""
    out: list[Chunk] = []
    for page in pages:
        n = page["n"]
        for pidx, ptext in enumerate(page.get("paragraphs", [])):
            sents = split_sentences(ptext)
            windows = _windows(sents, PDF_MAX_CHARS, 0.0)
            for w_i, idxs in enumerate(windows):
                cid = f"{_art_short(artifact_id)}:{branch}:p{n}:{pidx}" + (f"#{w_i}" if len(windows) > 1 else "")
                sids = tuple(f"{artifact_id}:p{n}:{pidx}:{si}" for si in idxs)
                text = " ".join(sents[i] for i in idxs)
                out.append(Chunk(cid, artifact_id, branch, "pdf", text, sids))
    return out


# ---------------------------------------------------------------------------
# Code chunking — tree-sitter function/class spans (<=120 lines), fallback to
# a deterministic top-level def/class line scan when the grammars are absent.
# ---------------------------------------------------------------------------

def _qualified_name(node) -> str:
    name = node.child_by_field_name("name")
    return name.text.decode("utf-8", "replace") if name is not None else "<anon>"


def _node_lines(node) -> int:
    return node.end_point[0] - node.start_point[0] + 1


def _code_chunks_from_tree(
    source: str, file_path: str, artifact_id: str, branch: str, parser, max_lines: int,
) -> list[Chunk]:
    chunked: list[Chunk] = []
    ids: set[str] = set()
    tree = parser.parse(source.encode("utf-8"))
    root = tree.root_node

    def emit(qname: str, start_byte: int, end_byte: int, start_line: int) -> None:
        cid = f"{_art_short(artifact_id)}:{branch}:{file_path}::{qname}"
        if cid in ids:  # duplicate qualified names -> suffix deterministically
            cid = f"{cid}#{len(ids)}"
        ids.add(cid)
        sid = f"{artifact_id}:{file_path}::{qname}"
        text = source[start_byte:end_byte]
        if start_line < 0:
            start_line = 0
        chunked.append(Chunk(cid, artifact_id, branch, "code", text, (sid,)))

    for child in root.children:
        if child.type not in _DEF_NODE_TYPES:
            continue
        real = child.child_by_field_name("definition") if child.type == "decorated_definition" else child
        if real is None:
            real = child
        name = _qualified_name(real)
        if _node_lines(real) <= max_lines:
            emit(name, real.start_byte, real.end_byte, real.start_point[0])
            continue
        # Oversized span: split into direct children definitions (methods) if
        # any, otherwise hard line-split every max_lines lines.
        inner = [c for c in real.named_children if c.type in _DEF_NODE_TYPES]
        if inner:
            for sub in inner:
                sub_name = f"{name}.{_qualified_name(sub)}"
                emit(sub_name, sub.start_byte, sub.end_byte, sub.start_point[0])
        else:
            start_line, start_byte = real.start_point[0], real.start_byte
            while start_byte < real.end_byte:
                # advance to the line max_lines below (or the end)
                cur = start_line
                end_byte = start_byte
                while cur < start_line + max_lines and end_byte < real.end_byte:
                    nl = source.find("\n", end_byte)
                    if nl == -1 or nl + 1 >= len(source) or nl + 1 > real.end_byte:
                        if nl + 1 > real.end_byte or nl == -1:
                            end_byte = real.end_byte
                            break
                    end_byte = nl + 1
                    cur += 1
                if end_byte <= start_byte:
                    end_byte = real.end_byte
                emit(f"{name}#{cur - start_line}", start_byte, end_byte, start_line)
                start_byte, start_line = end_byte, cur
    return chunked


try:  # optional grammars — the fallback path must exist (ADR-11 risk register)
    import tree_sitter as _ts
    import tree_sitter_python as _tsp

    def _make_parser():
        try:
            return _ts.Parser(_ts.Language(_tsp.language()))
        except TypeError:  # older capsule-based API
            return _ts.Parser(_ts.Language(_tsp.language()))  # pragma: no cover
    _PARSER_FACTORY = _make_parser
except Exception:  # pragma: no cover — exercised only when grammars are absent
    _PARSER_FACTORY = None


def _code_chunks_line_scan(
    source: str, file_path: str, artifact_id: str, branch: str, max_lines: int,
) -> list[Chunk]:
    """Deterministic fallback: split at top-level def/class lines."""
    lines = source.splitlines(keepends=True)
    marks = [(i, m.group(1)) for i, line in enumerate(lines) if (m := _DEF_RE.match(line))]
    spans = []
    if not marks:
        spans.append(("<file>", 0, len(lines), 0))
    else:
        for k, (i, name) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
            for base in range(i, end, max_lines):
                seg = min(end, base + max_lines)
                spans.append((f"{name}#{base - i}" if seg < end else name, base, seg, base - i))
    out: list[Chunk] = []
    for qname, lo, hi, _off in spans:
        cid = f"{_art_short(artifact_id)}:{branch}:{file_path}::{qname}"
        sid = f"{artifact_id}:{file_path}::{qname}"
        out.append(Chunk(cid, artifact_id, branch, "code", "".join(lines[lo:hi]), (sid,)))
    return out


def chunk_code(source: str, file_path: str, artifact_id: str, branch: str = "main") -> list[Chunk]:
    """Code: tree-sitter function/class spans <=120 lines; line-scan fallback."""
    if _PARSER_FACTORY is not None:
        try:
            return _code_chunks_from_tree(
                source, file_path, artifact_id, branch, _PARSER_FACTORY(), CODE_MAX_LINES
            )
        except Exception:
            pass  # grammar/parse failure -> deterministic fallback
    if not source.strip() or not source.splitlines():
        cid = f"{_art_short(artifact_id)}:{branch}:{file_path}::<empty>"
        return [Chunk(cid, artifact_id, branch, "code", source, (f"{artifact_id}:{file_path}::<empty>",))]
    return _code_chunks_line_scan(source, file_path, artifact_id, branch, CODE_MAX_LINES)


def chunk_document(kind: str, payload, artifact_id: str, branch: str = "main") -> list[Chunk]:
    """Dispatch a canonical payload (or raw text for md/txt) to its chunker."""
    if kind in ("md", "txt"):
        return chunk_markdown(payload if isinstance(payload, str) else payload.get("text", ""),
                              artifact_id, branch)
    if kind == "chat":
        return chunk_chat(payload.get("messages", []), artifact_id, branch)
    if kind == "pdf":
        return chunk_pdf(payload.get("pages", []), artifact_id, branch)
    if kind == "codebase":
        out: list[Chunk] = []
        for f in payload.get("files", []):
            out.extend(chunk_code(f["text"], f["path"], artifact_id, branch))
        return out
    if kind == "code-file":
        return chunk_code(payload.get("text", ""), payload.get("path", "file"), artifact_id, branch)
    # Unknown future kinds degrade to one chunk of the serialized payload.
    return [Chunk(f"{_art_short(artifact_id)}:{branch}:all", artifact_id, branch, kind,
                  str(payload), (f"{artifact_id}:all",))]