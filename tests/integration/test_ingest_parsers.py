"""Ingestion parser contracts (issue #8 / ingestion-spec.md).

Structure is preserved (never flattened): chat = message list, pdf = pages,
codebase = file tree. Both chat schemas converge to the same canonical form and
re-exported conversations with different volatile ids dedup to the same blob id.
"""
from __future__ import annotations

import io
import json
import zipfile

import pytest

from backend.src.core.objects.store import ObjectStore
from backend.src.ingestion import pipeline
from backend.src.ingestion.parsers import ParseError, parse
from backend.src.ingestion.parsers.pdf import PDF_NOT_EXTRACTABLE


def text_pdf(text: str = "Hello world. Second sentence here.") -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    objs = [
        bytearray(b"<< /Type /Catalog /Pages 2 0 R >>"),
        bytearray(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        bytearray(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
                  b"/Resources << /Font << /F1 5 0 R >> >> >>"),
        bytearray(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content.encode()), content.encode())),
        bytearray(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + bytes(obj) + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def chatgpt_conv(ids, texts):
    nodes = {}
    for i, (mid, role, text) in enumerate(zip(ids, ["user", "assistant"], texts)):
        parent = None if i == 0 else ids[i - 1]
        children = [ids[i + 1]] if i == 0 else []
        nodes[mid] = {"message": {"author": {"role": role},
                                  "content": {"parts": [text]}},
                      "parent": parent, "children": children}
    return [{"title": "t", "mapping": nodes}]


def test_markdown_identity_is_exact_bytes_and_claims_extracted():
    md = b"# Title\n\ntext.\n\nclaim: gravity accelerates.\n"
    unit = parse("markdown", "notes.md", md)[0]
    assert unit.kind == "md"
    assert unit.storage_bytes == md              # canonical = exact bytes
    assert unit.claims == ["gravity accelerates."]


def test_chatgpt_and_claude_converge_to_same_canonical():
    cg = chatgpt_conv(["a", "b"], ["what is x?", "x is the variable"])
    cu = parse("chatgpt", "c.json", json.dumps(cg).encode())[0]

    cl = json.dumps({"chat_messages": [
        {"role": "user", "content": [{"type": "text", "text": "what is x?"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "x is the variable"}]}]}) + "\n"
    clu = parse("claude", "c.jsonl", cl.encode())[0]

    assert cu.payload["source"] == "chatgpt"
    assert clu.payload["source"] == "claude"
    assert cu.payload["messages"] == clu.payload["messages"]
    # identical canonical chat -> identical blob identity
    assert cu.storage_bytes == clu.storage_bytes
    # role order preserved
    assert [m["role"] for m in cu.payload["messages"]] == ["user", "assistant"]


def test_chatgpt_reexport_with_different_ids_dedups():
    first = chatgpt_conv(["a", "b"], ["hi", "hello"])
    second = chatgpt_conv(["zz1", "zz2"], ["hi", "hello"])  # different node ids
    u1 = parse("chatgpt", "one.json", json.dumps(first).encode())[0]
    u2 = parse("chatgpt", "two.json", json.dumps(second).encode())[0]
    assert u1.storage_bytes == u2.storage_bytes     # volatile ids excluded
    assert u1.payload == u2.payload


def test_claude_tool_use_becomes_placeholder_and_ignores_non_text():
    cl = json.dumps({"chat_messages": [
        {"role": "user", "content": [{"type": "text", "text": "calculate"}]},
        {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Calculator"},
            {"type": "text", "text": "answer is 42"}]}]}) + "\n"
    u = parse("claude", "c.jsonl", cl.encode())[0]
    a = u.payload["messages"][1]["text"]
    assert "[tool: Calculator]" in a and "answer is 42" in a


def test_pdf_structure_preserved_and_image_only_422():
    pu = parse("pdf", "paper.pdf", text_pdf())[0]
    assert pu.kind == "pdf"
    assert isinstance(pu.payload["pages"], list)
    assert pu.payload["pages"][0]["n"] == 1
    assert isinstance(pu.payload["pages"][0]["paragraphs"], list)
    assert any("Hello" in p for p in pu.payload["pages"][0]["paragraphs"])

    # blank/image-only PDF -> PDF_NOT_EXTRACTABLE, not a traceback
    from pypdf import PdfWriter
    pw = PdfWriter(); pw.add_blank_page(width=200, height=200)
    bb = io.BytesIO(); pw.write(bb)
    with pytest.raises(ParseError) as ei:
        parse("pdf", "scan.pdf", bb.getvalue())
    assert ei.value.code == PDF_NOT_EXTRACTABLE


def test_codebase_file_tree_binaries_skipped_and_tree_stable():
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        z.writestr("pkg/__init__.py", "")
        z.writestr("pkg/core.py", "def f():\n    return 1\n")
        z.writestr("data.bin", b"\x00" * 50)
        z.writestr("notes.md", "text")
    u1 = parse("codebase", "repo.zip", zb.getvalue())[0]
    paths = {f.path for f in u1.files}
    assert paths == {"pkg/__init__.py", "pkg/core.py", "notes.md"}
    assert "data.bin" not in paths
    assert u1.kind == "codebase" and u1.kind_tag == "tree"
    assert "root_tree_id" in u1.payload

    # re-parse identical archive -> stable tree hash (file content addressing)
    u2 = parse("codebase", "repo.zip", zb.getvalue())[0]
    assert u1.payload["root_tree_id"] == u2.payload["root_tree_id"]


def test_malformed_inputs_raise_parse_error_not_traceback():
    with pytest.raises(ParseError):
        parse("chatgpt", "c.json", b"{oops")
    with pytest.raises(ParseError):
        parse("codebase", "r.zip", b"not a zip")
    with pytest.raises(ParseError):
        parse("pdf", "p.pdf", b"%PDF not really")


def test_pipeline_writes_rows_edges_and_root_commit(tmp_path):
    store = ObjectStore(str(tmp_path / "s"))
    md = b"# Title\n\nclaim: gravity accelerates.\n\nrest."
    out = pipeline.ingest(store, "markdown", "notes.md", md, "userA")
    assert out.source_id.startswith("src_")
    art = out.artifacts[0]
    assert art.artifact_id.startswith("art_")

    # rows + imported_as edge present
    assert store.db.execute("SELECT 1 FROM sources WHERE id=?", (out.source_id,)).fetchone()
    assert store.db.execute("SELECT 1 FROM artifacts WHERE id=?", (art.artifact_id,)).fetchone()
    edge = store.db.execute(
        "SELECT relation FROM provenance_edges WHERE from_id=? AND to_id=?",
        (out.source_id, art.artifact_id)).fetchone()
    assert edge[0] == "imported_as"

    # root commit now lands (versioning engine is implemented)
    pipeline.commit_roots(store, out, "userA")
    assert art.commit_id
    assert store.head("main", art.artifact_id) == art.commit_id
    # claim sentinel became a Claim row + states + derived_from edges
    claim = store.db.execute(
        "SELECT id, text FROM claims WHERE artifact_id=?", (art.artifact_id,)).fetchone()
    assert claim and "gravity accelerates" in claim[1]
    assert store.db.execute(
        "SELECT 1 FROM provenance_edges WHERE from_kind='commit' AND to_id=?",
        (claim[0],)).fetchone()
    assert store.db.execute(
        "SELECT 1 FROM provenance_edges WHERE from_kind='claim' AND to_id=?",
        (out.source_id,)).fetchone()