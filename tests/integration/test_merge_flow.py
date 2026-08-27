"""Integration test: the live merge-conflict demo moment (issue #4, stretch).

Post /api/merge on the demo fixture must SURFACE a conflict (not 501), return
conflict cards, and /api/merge/:id/resolve must produce a 2-parent merge commit.
This is the #1 thing judges ask to see — it must work through the real API.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

FIXTURES = Path(__file__).resolve().parents[2] / "scripts" / "fixtures" / "merge"


def test_live_merge_conflict_and_resolve(client):
    def rd(n: str) -> bytes:
        return (FIXTURES / n).read_bytes()

    # Ingest the demo base -> root commit on main.
    r = client.post("/api/ingest",
                    headers={"X-User": "muneer"},
                    files={"file": ("base.md", rd("base.md"), "text/markdown")},
                    data={"type": "markdown"})
    assert r.status_code == 201
    art = r.json()["artifact_ids"][0]
    root = client.get(f"/api/artifacts/{art}/history",
                      headers={"X-User": "muneer"}).json()[0]["commit_id"]

    # Branch feature off the COMMON root so both sides diverge independently.
    client.post("/api/branches", headers={"X-User": "muneer"},
                json={"artifact_id": art, "name": "feature", "from_commit": root})
    client.post(f"/api/artifacts/{art}/commit", headers={"X-User": "muneer"},
                json={"branch": "main", "content": rd("ours.md").decode(), "message": "ours"})
    client.post(f"/api/artifacts/{art}/commit", headers={"X-User": "muneer"},
                json={"branch": "feature", "content": rd("theirs.md").decode(), "message": "theirs"})

    # MERGE must surface exactly 1 conflict on the shared sentence (0:1).
    m = client.post("/api/merge", headers={"X-User": "muneer"},
                    json={"artifact_id": art, "ours_branch": "main", "theirs_branch": "feature"})
    assert m.status_code == 201
    body = m.json()
    assert body["state"] == "conflicts"
    assert len(body["conflicts"]) == 1
    c = body["conflicts"][0]
    assert c["sid"] == "0:1"
    assert c["ours_text"].strip() and c["theirs_text"].strip()  # both sides shown
    merge_id = body["merge_id"]
    assert merge_id.startswith("mrg_")

    # Resolve by accepting OURS -> 2-parent merge commit.
    res = client.post(f"/api/merge/{merge_id}/resolve", headers={"X-User": "muneer"},
                      json={"resolutions": [{"conflict_id": c["id"], "resolution": "ours"}]})
    assert res.status_code == 200
    rc = res.json()["result_commit_id"]
    store = client.app.state.store
    parents = [p[0] for p in store.db.execute(
        "SELECT parent_id FROM commit_parents WHERE commit_id=?", (rc,))]
    assert len(parents) == 2  # merge commit
    assert "deeper models" in res.json()["final_text"]
    again = client.post(f"/api/merge/{merge_id}/resolve", headers={"X-User": "muneer"},
                        json={"resolutions": [{"conflict_id": c["id"], "resolution": "theirs"}]})
    assert again.status_code == 409


def test_repository_tree_folder_and_file_upload(client):
    root = client.post(
        "/api/ingest", headers={"X-User": "muneer"},
        files={"file": ("README.md", b"# root\n", "text/markdown")},
        data={"type": "markdown"},
    )
    assert root.status_code == 201
    artifact_id = root.json()["artifact_ids"][0]

    folder = client.post(
        f"/api/artifacts/{artifact_id}/folders", headers={"X-User": "muneer"},
        json={"path": "research/notes"},
    )
    assert folder.status_code == 201

    uploaded = client.post(
        f"/api/artifacts/{artifact_id}/files", headers={"X-User": "muneer"},
        files=[
            ("files", ("finding.md", b"# finding\n", "text/markdown")),
            ("files", ("data.txt", b"measurement\n", "text/plain")),
        ],
        data={"path": "research/notes"},
    )
    assert uploaded.status_code == 201
    assert [item["path"] for item in uploaded.json()["files"]] == [
        "research/notes/finding.md", "research/notes/data.txt"
    ]

    tree = client.get(f"/api/artifacts/{artifact_id}/tree")
    assert tree.status_code == 200
    assert {(item["path"], item["type"]) for item in tree.json()} == {
        ("research", "folder"),
        ("research/notes", "folder"),
        ("research/notes/finding.md", "file"),
        ("research/notes/data.txt", "file"),
    }

    rejected = client.post(
        f"/api/artifacts/{artifact_id}/folders", json={"path": "../escape"}
    )
    assert rejected.status_code == 400
