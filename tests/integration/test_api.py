"""End-to-end API contract tests (issue #7 / api-contract.md).

Wires a TestClient to a throwaway ObjectStore per test via app.state.store
(get_store reads it first). Covers the real (implemented) routes and asserts
the {error:{code,message}} shape on failures; stubs (merge, search) must return
501, not fake data.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.src.api.main import app
from backend.src.core.objects.store import ObjectStore


@pytest.fixture()
def client(tmp_path):
    client = TestClient(app)
    # Isolate state per test: a brand-new store on app.state.
    client.app.state.store = ObjectStore(str(tmp_path / "store"))
    yield client


def hdr(user: str = "userA") -> dict:
    return {"X-User": user}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "version": "0.1.0"}


def test_root_artifact_roundtrip(client):
    r = client.post("/api/artifacts", json={
        "kind": "md", "title": "Notes", "content": "# One\n\nTwo.",
    }, headers=hdr())
    assert r.status_code == 201
    body = r.json()
    assert body["artifact_id"].startswith("art_")
    assert body["root_commit_id"]

    art_id = body["artifact_id"]
    g = client.get(f"/api/artifacts/{art_id}", headers=hdr())
    assert g.status_code == 200
    gb = g.json()
    assert gb["id"] == art_id and gb["kind"] == "md" and gb["title"] == "Notes"
    assert gb["branches"] == [{"name": "main", "head": body["root_commit_id"]}]

    hist = client.get(f"/api/artifacts/{art_id}/history?branch=main")
    assert hist.status_code == 200
    assert [c["commit_id"] for c in hist.json()] == [body["root_commit_id"]]

    # author recorded from mock X-User header
    author = client.app.state.store.db.execute(
        "SELECT author FROM commits WHERE id=?", (body["root_commit_id"],)
    ).fetchone()[0]
    assert author == "userA"


def test_commit_dedup_and_idempotency(client):
    art = client.post("/api/artifacts", json={"kind": "md", "title": "a", "content": "v0"},
                      headers=hdr()).json()["artifact_id"]
    c0 = client.post("/api/artifacts", json={"kind": "md", "title": "a", "content": "v0"},
                     headers=hdr()).json()["root_commit_id"]
    r1 = client.post(f"/api/artifacts/{art}/commit", json={
        "branch": "main", "content": "v1", "message": "second",
    }, headers=hdr())
    assert r1.status_code == 201
    c1 = r1.json()["commit_id"]

    # identical content + same message -> same commit id; second returns 200
    r2 = client.post(f"/api/artifacts/{art}/commit", json={
        "branch": "main", "content": "v1", "message": "second",
    }, headers=hdr())
    assert r2.status_code == 200
    assert r2.json()["commit_id"] == c1

    assert c1 != c0
    hist = client.get(f"/api/artifacts/{art}/history").json()
    assert [c["commit_id"] for c in hist] == [c1, c0]
    assert hist[0]["parents"] == [c0]


def test_stale_base_returns_409_with_head(client):
    art = client.post("/api/artifacts", json={"kind": "md", "title": "a", "content": "v0"},
                      headers=hdr()).json()["artifact_id"]
    head = client.get(f"/api/artifacts/{art}").json()["branches"][0]["head"]
    client.post(f"/api/artifacts/{art}/commit", json={
        "branch": "main", "content": "v1", "message": "m"}, headers=hdr())
    r = client.post(f"/api/artifacts/{art}/commit", json={
        "branch": "main", "content": "v2", "message": "stale", "base_commit": head,
    }, headers=hdr())
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STALE_BASE"
    assert r.json()["head"] == head


def test_bad_kind_400_error_shape(client):
    r = client.post("/api/artifacts", json={"kind": "exe", "title": "x", "content": "1"},
                    headers=hdr())
    assert r.status_code == 400
    body = r.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "BAD_KIND"


def test_unknown_artifact_404_error_shape(client):
    r = client.get("/api/artifacts/art_doesnotexist", headers=hdr())
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"


def test_branches_and_checkout(client):
    art = client.post("/api/artifacts", json={"kind": "md", "title": "a", "content": "base text"},
                      headers=hdr()).json()["artifact_id"]
    c0 = client.get(f"/api/artifacts/{art}").json()["branches"][0]["head"]
    rb = client.post("/api/branches", json={"artifact_id": art, "name": "feature"},
                     headers=hdr())
    assert rb.status_code == 201
    assert rb.json() == {"name": "feature", "head": c0}
    # duplicate branch -> 409
    assert client.post("/api/branches", json={"artifact_id": art, "name": "feature"},
                       headers=hdr()).status_code == 409
    listed = client.get(f"/api/branches?artifact_id={art}").json()
    assert {b["name"] for b in listed} == {"main", "feature"}

    co = client.post("/api/checkout", json={"artifact_id": art, "branch": "main"},
                     headers=hdr())
    assert co.status_code == 200
    assert co.json()["commit_id"] == c0
    assert "base text" in co.json()["content"]


def test_diff_real_for_md(client):
    art = client.post("/api/artifacts", json={"kind": "md", "title": "a",
                                              "content": "Alpha beta. Gamma delta."},
                      headers=hdr()).json()["artifact_id"]
    c0 = client.get(f"/api/artifacts/{art}").json()["branches"][0]["head"]
    c1 = client.post(f"/api/artifacts/{art}/commit", json={
        "branch": "main", "content": "Alpha beta. Epsilon zeta.", "message": "edit",
    }, headers=hdr()).json()["commit_id"]

    d = client.get(f"/api/diff", params={"artifact_id": art, "from": c0, "to": c1})
    assert d.status_code == 200
    body = d.json()
    assert body["kind"] == "md"
    assert isinstance(body["changes"], list)
    assert any(c["status"] in {"edited", "added", "deleted", "unchanged", "moved"} for c in body["changes"])

    # same from/to -> 400
    assert client.get(f"/api/diff", params={"artifact_id": art, "from": c0, "to": c0}).status_code == 400


def test_ingest_multipart_and_provenance(client):
    md = b"# Title\n\nGravity is accelerating.\n\nclaim: gravity accelerates field lines.\n"
    r = client.post("/api/ingest", headers=hdr("userA"),
                    files={"file": ("notes.md", md, "text/markdown")},
                    data={"type": "markdown"})
    assert r.status_code == 201
    body = r.json()
    src = body["source_id"]
    assert src.startswith("src_")
    assert len(body["artifact_ids"]) == 1
    art_id = body["artifact_ids"][0]

    # provenance: the claim sentinel became a Claim row + edges
    store = client.app.state.store
    claim = store.db.execute(
        "SELECT id, text, artifact_id, commit_id FROM claims WHERE artifact_id=?",
        (art_id,),
    ).fetchone()
    assert claim is not None and "gravity accelerates" in claim[1]
    claim_id = claim[0]

    pc = client.get(f"/api/provenance/claim/{claim_id}")
    assert pc.status_code == 200
    chain_kinds = {c["kind"] for c in pc.json()["chain"]}
    assert {"claim", "commit", "artifact", "source"} <= chain_kinds
    assert pc.json()["claim"]["id"] == claim_id

    pa = client.get(f"/api/provenance/artifact/{art_id}/sources")
    assert pa.status_code == 200
    assert pa.json()[0]["source"]["id"] == src

    pt = client.get(f"/api/provenance/at/{claim[2]}/claims")
    assert pt.status_code == 200
    assert any(c["id"] == claim_id for c in pt.json())


def test_ingest_chatgpt_converges_to_canonical(client):
    import json
    conv = [{"mapping": {
        "a": {"message": {"author": {"role": "user"}, "content": {"parts": ["hello"]}},
              "children": ["b"], "parent": None},
        "b": {"message": {"author": {"role": "assistant"}, "content": {"parts": ["hi there"]}},
              "children": [], "parent": "a"}}}]
    r = client.post("/api/ingest", headers=hdr(),
                    files={"file": ("conversations.json", json.dumps(conv).encode())},
                    data={"type": "chatgpt"})
    assert r.status_code == 201
    store = client.app.state.store
    blob = store.db.execute(
        "SELECT h.hash, h.kind FROM artifacts a JOIN commits c ON c.artifact_id=a.id "
        "JOIN objects h ON h.hash=c.root_hash WHERE a.id=?",
        (r.json()["artifact_ids"][0],),
    ).fetchone()
    assert blob[1] == "chat"


def test_bad_parse_returns_422_not_500(client):
    r = client.post("/api/ingest", headers=hdr(),
                    files={"file": ("bad.json", b"{not json")},
                    data={"type": "chatgpt"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "PARSE_ERROR"


def test_unknown_ingest_type_400(client):
    r = client.post("/api/ingest", headers=hdr(),
                    files={"file": ("x.txt", b"hi")}, data={"type": "carrot"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNKNOWN_TYPE"


def test_search_stub_returns_501_and_empty_query_400(client):
    assert client.post("/api/search", json={"query": "   "}).status_code == 400
    r = client.post("/api/search", json={"query": "gravity"})
    assert r.status_code == 501
    assert r.json()["error"]["code"] == "NOT_IMPLEMENTED"


def test_merge_stub_returns_501(client):
    art = client.post("/api/artifacts", json={"kind": "md", "title": "a", "content": "x"},
                      headers=hdr()).json()["artifact_id"]
    r = client.post("/api/merge", json={"artifact_id": art, "ours_branch": "main",
                                        "theirs_branch": "main"}, headers=hdr())
    assert r.status_code == 501
    assert r.json()["error"]["code"] == "NOT_IMPLEMENTED"


def test_delete_artifact_tombstones(client):
    art = client.post("/api/artifacts", json={"kind": "md", "title": "a", "content": "x"},
                      headers=hdr()).json()["artifact_id"]
    assert client.delete(f"/api/artifacts/{art}", headers=hdr()).status_code == 204
    assert client.get(f"/api/artifacts/{art}").status_code == 404
    # delete again -> 404
    assert client.delete(f"/api/artifacts/{art}", headers=hdr()).status_code == 404


def test_static_frontend_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "ReGit" in r.text