"""Chunker unit tests (ADR-11 table) — deterministic boundaries per type.

md: heading sections <=600 chars with 10% sentence overlap; chat: 1 message =
1 chunk with `role:` prefix; pdf: page paragraphs <=800 chars; code:
tree-sitter function/class spans <=120 lines (line-scan fallback covered).
Determinism is contractual: same input -> identical chunks (ids, texts, sids).
"""
from __future__ import annotations

import json

from backend.src.core.objects.hashutil import short_hash
from backend.src.retrieval import chunkers as C

ART = "art_01JRETRIEV"
PREFIX = short_hash(ART)[:8]

MD_TEXT = (
    "# Notes\n\n"
    "Gradient descent diverges when the learning rate exceeds the curvature bound.\n\n"
    "## Experiments\n\n"
    "Adam mitigates loss spikes.\n"
)

LONG_TEXT = (
    "# Long\n\n"
    + " ".join(
        f"Sentence number {i} about gradient descent stability in convex optimization settings."
        for i in range(25)
    )
)

CODE_TEXT = '''def compute_stats(x):
    """docstring"""
    total = sum(x)
    n = len(x)
    return total / n


def helper():
    return 42


class Optimizer:
    def step(self, lr):
        return lr * 0.9

    def reset(self):
        return 0
'''


# --- markdown ---------------------------------------------------------------

def test_md_heading_sections_become_chunks():
    chunks = C.chunk_markdown(MD_TEXT, ART, "main")
    assert [c.chunk_id for c in chunks] == [
        f"{PREFIX}:main:notes",
        f"{PREFIX}:main:experiments",
    ]
    assert chunks[0].text == (
        "# Notes Gradient descent diverges when the learning rate exceeds the curvature bound."
    )
    assert chunks[1].text == "## Experiments Adam mitigates loss spikes."
    assert all(len(c.text) <= C.MD_MAX_CHARS for c in chunks)
    # sid coverage is document-global (para:sent), per data-model.md
    assert chunks[0].sids == (f"{ART}:0:0", f"{ART}:1:0")
    assert chunks[1].sids == (f"{ART}:2:0", f"{ART}:3:0")
    assert json.loads(chunks[1].sid_range) == [f"{ART}:2:0", f"{ART}:3:0"]


def test_md_long_section_windows_with_overlap():
    chunks = C.chunk_markdown(LONG_TEXT, ART, "main")
    assert len(chunks) >= 3
    assert all(len(c.text) <= C.MD_MAX_CHARS for c in chunks)
    # window ids are position-stable
    assert [c.chunk_id for c in chunks] == [
        f"{PREFIX}:main:long#{i}" for i in range(len(chunks))
    ]
    # 10% overlap: consecutive windows share at least one sentence sid
    overlaps = [
        set(chunks[i].sids) & set(chunks[i + 1].sids)
        for i in range(len(chunks) - 1)
    ]
    assert all(ov for ov in overlaps), "consecutive windows must overlap"


def test_md_no_heading_single_doc_section():
    chunks = C.chunk_markdown("Just one paragraph with a few sentences. And another one here.", ART)
    assert [c.chunk_id for c in chunks] == [f"{PREFIX}:main:doc"]


def test_md_deterministic():
    assert C.chunk_markdown(MD_TEXT, ART, "main") == C.chunk_markdown(MD_TEXT, ART, "main")
    assert C.chunk_markdown(LONG_TEXT, ART, "x") == C.chunk_markdown(LONG_TEXT, ART, "x")


# --- chat --------------------------------------------------------------------

def test_chat_one_message_one_chunk():
    msgs = [
        {"ord": 0, "role": "user", "text": "hello"},
        {"ord": 1, "role": "assistant", "text": "hi there"},
        {"ord": 2, "role": "user", "text": "explain momentum"},
    ]
    chunks = C.chunk_chat(msgs, ART, "main")
    assert [c.chunk_id for c in chunks] == [
        f"{PREFIX}:main:msg:0:user",
        f"{PREFIX}:main:msg:1:assistant",
        f"{PREFIX}:main:msg:2:user",
    ]
    assert chunks[0].text == "user: hello"          # `role:` prefix (ADR-11)
    assert chunks[1].text == "assistant: hi there"
    assert chunks[0].sids == (f"{ART}:msg:0:user",)


# --- pdf ---------------------------------------------------------------------

def test_pdf_page_paragraph_chunks():
    pages = [
        {"n": 1, "paragraphs": ["First paragraph on page one with several words.",
                                "Second paragraph here."]},
        {"n": 2, "paragraphs": ["Page two paragraph."]},
    ]
    chunks = C.chunk_pdf(pages, ART, "main")
    assert [c.chunk_id for c in chunks] == [
        f"{PREFIX}:main:p1:0", f"{PREFIX}:main:p1:1", f"{PREFIX}:main:p2:0",
    ]
    assert chunks[0].sids == (f"{ART}:p1:0:0",)
    assert all(len(c.text) <= C.PDF_MAX_CHARS for c in chunks)


def test_pdf_long_paragraph_split_under_800():
    pages = [{"n": 1, "paragraphs": [" ".join(
        f"Token phrase {i} about stochastic gradient methods and their convergence rates."
        for i in range(40))]}]
    chunks = C.chunk_pdf(pages, ART, "main")
    assert len(chunks) >= 2
    assert all(len(c.text) <= C.PDF_MAX_CHARS for c in chunks)
    assert all(c.chunk_id.startswith(f"{PREFIX}:main:p1:0") for c in chunks)


# --- code --------------------------------------------------------------------

def test_code_tree_sitter_function_spans():
    chunks = C.chunk_code(CODE_TEXT, "pkg/train.py", ART, "main")
    by_name = {c.chunk_id.rsplit("::", 1)[-1]: c for c in chunks}
    assert set(by_name) == {"compute_stats", "helper", "Optimizer"}
    assert all(len(c.text.splitlines()) <= C.CODE_MAX_LINES for c in chunks)
    assert by_name["compute_stats"].sids == (f"{ART}:pkg/train.py::compute_stats",)
    assert "def step" in by_name["Optimizer"].text


def test_code_line_scan_fallback_when_no_tree_sitter(monkeypatch):
    monkeypatch.setattr(C, "_PARSER_FACTORY", None)
    chunks = C.chunk_code(CODE_TEXT, "pkg/train.py", ART, "main")
    names = {c.chunk_id.rsplit("::", 1)[-1] for c in chunks}
    assert {"compute_stats", "helper", "Optimizer"} <= names
    assert all(len(c.text.splitlines()) <= C.CODE_MAX_LINES for c in chunks)


def test_code_deterministic():
    assert C.chunk_code(CODE_TEXT, "pkg/train.py", ART, "main") == \
        C.chunk_code(CODE_TEXT, "pkg/train.py", ART, "main")


# --- dispatch ----------------------------------------------------------------

def test_chunk_document_dispatches_by_kind():
    md = C.chunk_document("md", MD_TEXT, ART, "main")
    assert md == C.chunk_markdown(MD_TEXT, ART, "main")
    chat = C.chunk_document("chat", {"messages": [{"ord": 0, "role": "user", "text": "hi"}]},
                            ART, "main")
    assert chat == C.chunk_chat([{"ord": 0, "role": "user", "text": "hi"}], ART, "main")
    code = C.chunk_document("code-file", {"text": CODE_TEXT, "path": "a.py"}, ART, "main")
    assert any(c.chunk_id.endswith("a.py::compute_stats") for c in code)