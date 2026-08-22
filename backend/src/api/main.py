"""FastAPI REST layer — one process serving REST + WS + static client.

Wires every route in docs/specs/api-contract.md against the ObjectStore and the
per-kind engines. Error shape everywhere: `{error: {code, message}}`. Mock users
via the `X-User` header (userA|userB); mutating endpoints are idempotent through
content addressing.

Per adr-07: single uvicorn worker (the in-memory CRDT registry and the shared
ObjectStore must not be duplicated). Run: uvicorn backend.src.api.main:app.

Engine status today:
  - versioning (ObjectStore.commit/history/branches/merge_base): IMPLEMENTED.
  - diff (core/diff/align.diff_prose) for md/txt: IMPLEMENTED.
  - parsing + ingest pipeline: IMPLEMENTED (this change).
  - provenance reads: IMPLEMENTED.
  - three-way merge (core/merge/three_way.merge_prose): STUB -> 501.
  - retrieval/search (retrieval/service.search): IMPLEMENTED — hybrid
    FTS5 BM25 + Chroma kNN, delta-reindexed on every commit; degraded to
    keyword-only when the vector stack is unavailable (retrieval-spec.md).
  - chat/pdf/codebase diff engines: STUB -> 501. Collaboration/WS
    (realtime/ws.py): IMPLEMENTED — live CRDT editing + commit-from-live.
Those stubs raise NotImplementedError which is mapped to 501; we do NOT fake
responses — the route + contract shape are fixed and the engine slots in later.
"""
from __future__ import annotations

import logging
import os
from datetime import UTC
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..core.diff import align
from ..core.ids import new_id
from ..core.objects.store import BranchExistsError, ObjectStore, RefConflictError
from ..ingestion import pipeline
from ..ingestion.parsers import VALID_TYPES, ParseError
from ..provenance import service as provenance
from ..realtime import ws as realtime_ws
from ..retrieval import indexer as retrieval_indexer
from ..retrieval import service as retrieval

# ---------------------------------------------------------------------------
# Paths / defaults
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parents[3]          # repo root
_FRONTEND = _BASE / "frontend"
_ARTIFACT_KINDS = {"md", "txt", "chat", "pdf", "codebase"}
_BLOB_TAG = {"md": "md", "txt": "txt", "chat": "chat", "pdf": "pdf", "codebase": "tree"}

app = FastAPI(title="ReGit", version="0.1.0")


# ---------------------------------------------------------------------------
# Error shape: {error: {code, message}}
# ---------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
def _on_api_error(_req: Request, exc: ApiError) -> JSONResponse:
    return _error_response(exc.status, exc.code, exc.message)


@app.exception_handler(ParseError)
def _on_parse_error(_req: Request, exc: ParseError) -> JSONResponse:
    return _error_response(422, exc.code, exc.message)


@app.exception_handler(NotImplementedError)
def _on_not_implemented(_req: Request, exc: NotImplementedError) -> JSONResponse:
    return _error_response(501, "NOT_IMPLEMENTED", str(exc))


@app.exception_handler(RefConflictError)
def _on_ref_conflict(_req: Request, exc: RefConflictError) -> JSONResponse:
    return _error_response(409, "REF_CONFLICT", str(exc))


@app.exception_handler(BranchExistsError)
def _on_branch_exists(_req: Request, exc: BranchExistsError) -> JSONResponse:
    return _error_response(409, "BRANCH_EXISTS", str(exc))


@app.exception_handler(ValueError)
def _on_value_error(_req: Request, exc: ValueError) -> JSONResponse:
    return _error_response(400, "BAD_REQUEST", str(exc))


@app.exception_handler(RequestValidationError)
def _on_validation(_req: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(422, "VALIDATION_FAILED", str(exc.errors()).replace("'", '"')[:1000])


@app.exception_handler(HTTPException)
def _on_http(_req: Request, exc: HTTPException) -> JSONResponse:
    return _error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
def get_store(request: Request) -> ObjectStore:
    store = getattr(request.app.state, "store", None)
    if store is None:
        store = ObjectStore(os.environ.get("GR_API_DATA_DIR", "data"))
        request.app.state.store = store
    return store


def get_user(x_user: str | None = Header(default=None, alias="X-User")) -> str:
    """Mock auth: `X-User: userA|userB`. Defaults to 'anonymous'."""
    return (x_user or "anonymous").strip() or "anonymous"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _ensure_tombstones(store: ObjectStore) -> None:
    store.db.execute(
        "CREATE TABLE IF NOT EXISTS tombstones(artifact_id TEXT PRIMARY KEY, deleted_at TEXT)"
    )
    store.db.commit()


def _tombstoned(store: ObjectStore, artifact_id: str) -> bool:
    return store.db.execute(
        "SELECT 1 FROM tombstones WHERE artifact_id=?", (artifact_id,)
    ).fetchone() is not None


def _artifact(store: ObjectStore, artifact_id: str) -> tuple | None:
    if _tombstoned(store, artifact_id):
        return None
    return store.db.execute(
        "SELECT id, kind, title, source_id, created_at FROM artifacts WHERE id=?",
        (artifact_id,),
    ).fetchone()


def _root_hash(store: ObjectStore, commit_id: str) -> str | None:
    row = store.db.execute(
        "SELECT root_hash FROM commits WHERE id=?", (commit_id,)
    ).fetchone()
    return row[0] if row else None


def _content(store: ObjectStore, kind: str, commit_id: str) -> str:
    root = _root_hash(store, commit_id)
    if root is None:
        raise ApiError(404, "COMMIT_NOT_FOUND", f"unknown commit {commit_id}")
    try:
        return store.get_blob(root).decode("utf-8", "replace")
    except KeyError:
        raise ApiError(404, "OBJECT_NOT_FOUND", f"root blob {root} missing") from None


def _require_branch_head(store: ObjectStore, artifact_id: str, branch: str) -> str:
    head = store.head(branch, artifact_id)
    if head is None:
        raise ApiError(404, "BRANCH_NOT_FOUND", f"branch '{branch}' has no head for {artifact_id}")
    return head


def _content_root(store: ObjectStore, kind: str, content: str | None, artifact_id: str) -> str:
    """Write the artifact's initial content blob; return the root hash."""
    tag = _BLOB_TAG[kind]
    data = (content or "").encode("utf-8") if kind in ("md", "txt") else (content or "{}").encode("utf-8")
    return store.put_blob(tag, data)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ArtifactCreate(BaseModel):
    kind: str
    title: str
    content: str | None = None
    source_id: str | None = None


class CommitBody(BaseModel):
    branch: str = "main"
    content: str
    message: str
    base_commit: str | None = None


class BranchCreate(BaseModel):
    artifact_id: str
    name: str
    from_commit: str | None = None


class CheckoutBody(BaseModel):
    artifact_id: str
    branch: str = "main"
    commit: str | None = None


class MergeBody(BaseModel):
    artifact_id: str
    ours_branch: str
    theirs_branch: str


class Resolution(BaseModel):
    conflict_id: str
    resolution: str            # ours | theirs | free
    resolved_text: str | None = None


class ResolveBody(BaseModel):
    resolutions: list[Resolution]

    def by_id(self) -> dict[str, Resolution]:
        out: dict[str, Resolution] = {}
        for r in self.resolutions:
            out.setdefault(r.conflict_id, r)
        return out


class SearchBody(BaseModel):
    query: str
    k: int = 5
    branch: str | None = None
    as_of_commit: str | None = None
    artifact_kind: str | None = None


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------
@app.post("/api/artifacts", status_code=201)
def create_artifact(
    body: ArtifactCreate,
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
) -> dict:
    kind = (body.kind or "").lower()
    if kind not in _ARTIFACT_KINDS:
        raise ApiError(400, "BAD_KIND", f"kind must be one of {sorted(_ARTIFACT_KINDS)}")

    art_id = new_id("art_")
    root_hash = _content_root(store, kind, body.content, art_id)
    with store._tx() as db:
        db.execute(
            "INSERT INTO artifacts(id, kind, title, source_id, created_at) VALUES (?,?,?,?,?)",
            (art_id, kind, body.title, body.source_id, _now()),
        )
    cid = store.commit([], root_hash, art_id, "root", user, kind=kind)
    _index_commit(store, cid, "main")
    return {"artifact_id": art_id, "root_commit_id": cid}


@app.get("/api/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, store: ObjectStore = Depends(get_store)) -> dict:
    row = _artifact(store, artifact_id)
    if row is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {artifact_id}")
    _id, kind, title, source_id, _created = row
    branches = [
        {"name": b, "head": h}
        for b, h in store.db.execute(
            "SELECT name, head_commit_id FROM branches WHERE artifact_id=? ORDER BY name",
            (artifact_id,),
        )
    ]
    return {"id": _id, "kind": kind, "title": title, "branches": branches, "source_id": source_id}


@app.delete("/api/artifacts/{artifact_id}", status_code=204)
def delete_artifact(
    artifact_id: str,
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
) -> Response:
    if _artifact(store, artifact_id) is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {artifact_id}")
    _ensure_tombstones(store)
    store.db.execute(
        "INSERT OR REPLACE INTO tombstones(artifact_id, deleted_at) VALUES (?,?)",
        (artifact_id, _now()),
    )
    store.db.commit()
    return Response(status_code=204)


@app.post("/api/artifacts/{artifact_id}/commit", status_code=201)
def commit_artifact(
    artifact_id: str,
    body: CommitBody,
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
):
    row = _artifact(store, artifact_id)
    if row is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {artifact_id}")
    kind = row[1]
    head = store.head(body.branch, artifact_id)

    # Stale-base guard (concurrency, api-contract.md): 409 {head}.
    if body.base_commit is not None and body.base_commit != head:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "STALE_BASE", "message": "base_commit != branch head"},
                      "head": head},
        )

    root_hash = _content_root(store, kind, body.content, artifact_id)
    expected = body.base_commit if body.base_commit is not None else None
    parents = [head] if head else []

    # Pin author_date exactly as store.commit will, so the dedup id probe and
    # the commit agree deterministically (versioning-spec.md determinism).
    author_date = _pinned_date(store, parents)

    from ..core.objects.hashutil import commit_id as _ci
    cid = _ci(parents, root_hash, artifact_id, body.message, user, author_date=author_date)
    exists = store.db.execute("SELECT 1 FROM commits WHERE id=?", (cid,)).fetchone() is not None

    created = store.commit(
        parents, root_hash, artifact_id, body.message, user,
        branch=body.branch, expected_head=expected, kind=kind, author_date=author_date,
    )
    if created != cid:  # pragma: no cover — defensive; identity must match
        return JSONResponse(status_code=500, content={"error": {
            "code": "IDENTITY_MISMATCH", "message": "commit id mismatch", "commit_id": created}})
    _index_commit(store, created, body.branch)
    return JSONResponse(
        status_code=200 if exists else 201,
        content={"commit_id": created, "parent_ids": parents},
    )


def _pinned_date(store: ObjectStore, parents: list[str]) -> str:
    """author_date: GR_AUTHOR_DATE env, else the first parent's date, else now.

    Mirrors ObjectStore.commit's resolution so the API's dedup id probe and the
    engine-use the same date (commit identity input, versioning-spec.md).
    """
    import os as _os
    from datetime import datetime, timezone

    env = _os.environ.get("GR_AUTHOR_DATE")
    if env:
        return env
    if parents:
        row = store.db.execute(
            "SELECT author_date FROM commits WHERE id=?", (parents[0],)
        ).fetchone()
        if row and row[0]:
            return row[0]
    return datetime.now(timezone.utc).isoformat()


@app.get("/api/artifacts/{artifact_id}/history")
def artifact_history(
    artifact_id: str, branch: str = "main", store: ObjectStore = Depends(get_store)
) -> list[dict]:
    if _artifact(store, artifact_id) is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {artifact_id}")
    return store.history(artifact_id, branch)


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------
@app.post("/api/branches", status_code=201)
def create_branch(
    body: BranchCreate,
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
) -> dict:
    if _artifact(store, body.artifact_id) is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {body.artifact_id}")
    from_commit = body.from_commit or _require_branch_head(store, body.artifact_id, "main")
    store.create_branch(body.name, body.artifact_id, from_commit)
    return {"name": body.name, "head": from_commit}


@app.get("/api/branches")
def list_branches(artifact_id: str, store: ObjectStore = Depends(get_store)) -> list[dict]:
    return [
        {"name": n, "head_commit_id": h}
        for n, h in store.db.execute(
            "SELECT name, head_commit_id FROM branches WHERE artifact_id=? ORDER BY name",
            (artifact_id,),
        )
    ]


@app.post("/api/checkout")
def checkout(
    body: CheckoutBody,
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
) -> dict:
    row = _artifact(store, body.artifact_id)
    if row is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {body.artifact_id}")
    commit_id = body.commit or _require_branch_head(store, body.artifact_id, body.branch)
    return {"content": _content(store, row[1], commit_id), "commit_id": commit_id}


# ---------------------------------------------------------------------------
# Diff  (md/txt via align.diff_prose; chat/pdf/codebase engines pending -> 501)
# ---------------------------------------------------------------------------
@app.get("/api/diff")
def diff(
    artifact_id: str,
    from_commit: str = Query(..., alias="from"),
    to: str = Query(...),
    store: ObjectStore = Depends(get_store),
) -> dict:
    if from_commit == to:
        raise ApiError(400, "SAME_COMMIT", "from and to must differ")
    row = _artifact(store, artifact_id)
    if row is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {artifact_id}")
    kind = row[1]
    if _root_hash(store, from_commit) is None:
        raise ApiError(404, "COMMIT_NOT_FOUND", f"unknown commit {from_commit}")
    if _root_hash(store, to) is None:
        raise ApiError(404, "COMMIT_NOT_FOUND", f"unknown commit {to}")

    if kind in ("md", "txt"):
        old_text = _content(store, kind, from_commit)
        new_text = _content(store, kind, to)
        return {"kind": kind, "changes": align.diff_prose(old_text, new_text, artifact_id)}
    raise NotImplementedError(
        f"H2/H6: diff engine for kind '{kind}' pending — chat/pdf/codebase (diff-spec.md)"
    )


# ---------------------------------------------------------------------------
# Merge  (three_way.merge_prose is a stub -> 501 until H5 lands)
# ---------------------------------------------------------------------------
@app.post("/api/merge", status_code=201)
def merge(
    body: MergeBody,
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
) -> dict:
    row = _artifact(store, body.artifact_id)
    if row is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {body.artifact_id}")
    kind = row[1]
    ours_head = _require_branch_head(store, body.artifact_id, body.ours_branch)
    theirs_head = _require_branch_head(store, body.artifact_id, body.theirs_branch)

    base_commit = store.merge_base(ours_head, theirs_head)
    base_text = _content(store, kind, base_commit) if base_commit else ""
    ours_text = _content(store, kind, ours_head)
    theirs_text = _content(store, kind, theirs_head)

    if kind not in ("md", "txt"):
        raise NotImplementedError(
            f"H5: merge for kind '{kind}' pending — file/message-level (merge-spec.md)"
        )
    from ..core.merge.three_way import merge_prose

    result = merge_prose(base_text, ours_text, theirs_text)
    if result.state == "clean":
        merged_root = store.put_blob(kind, result.merged_text.encode("utf-8"))
        result_commit = store.commit(
            [ours_head, theirs_head], merged_root, body.artifact_id,
            f"merge {body.theirs_branch} into {body.ours_branch}", user,
            branch=body.ours_branch, kind=kind,
        )
        return {
            "merge_id": "", "state": "clean", "conflicts": [],
            "preview_text": result.merged_text, "result_commit_id": result_commit,
            "ours_branch": body.ours_branch, "theirs_branch": body.theirs_branch,
        }
    # --- conflict path: persist a pending Merge + one Conflict row per
    # divergence, so the UI can render conflict cards and POST /resolve.
    merge_id = new_id("mrg_")
    with store._tx() as db:
        db.execute(
            "INSERT INTO merges(id, artifact_id, base_commit, ours_commit, "
            "theirs_commit, result_commit, state, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (merge_id, body.artifact_id, base_commit, ours_head, theirs_head,
             None, "conflicts", _now()),
        )
        conflict_recs = []
        for c in result.conflicts:
            cid = new_id("cnf_")
            db.execute(
                "INSERT INTO conflicts(id, merge_id, sid, base_text, ours_text, "
                "theirs_text, resolution, resolved_text) VALUES (?,?,?,?,?,?,?,?)",
                (cid, merge_id, c.sid, c.base_text, c.ours_text, c.theirs_text,
                 None, None),
            )
            conflict_recs.append({
                "id": cid, "sid": c.sid, "base_text": c.base_text,
                "ours_text": c.ours_text, "theirs_text": c.theirs_text,
                "resolution": None,
            })
    return {
        "merge_id": merge_id, "state": "conflicts", "conflicts": conflict_recs,
        "preview_text": result.merged_text,
        "ours_branch": body.ours_branch, "theirs_branch": body.theirs_branch,
        "artifact_id": body.artifact_id,
    }


@app.post("/api/merge/{merge_id}/resolve")
def resolve_merge(
    merge_id: str,
    body: ResolveBody,
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
) -> dict:
    mrow = store.db.execute(
        "SELECT id, artifact_id, base_commit, ours_commit, theirs_commit, result_commit, state "
        "FROM merges WHERE id=?",
        (merge_id,),
    ).fetchone()
    if mrow is None:
        raise ApiError(404, "MERGE_NOT_FOUND", f"unknown merge {merge_id}")
    _mid, _aid, _base, ours, theirs, result_commit, state = mrow
    if result_commit is not None or state == "resolved":
        raise ApiError(409, "ALREADY_RESOLVED", "merge already resolved")
    conflicts = store.db.execute(
        "SELECT id, sid, base_text, ours_text, theirs_text, resolution FROM conflicts WHERE merge_id=?",
        (merge_id,),
    ).fetchall()
    by_id = body.by_id()
    unresolved = [c[0] for c in conflicts if by_id.get(c[0]) is None]
    if unresolved:
        raise ApiError(400, "UNRESOLVED_CONFLICTS", f"conflicts without resolution: {unresolved}")
    # Re-run the engine so we have a fresh MergeResult whose markers carry the
    # conflict sids (compose_final_text needs the marker blocks, not raw rows).
    from ..core.merge.three_way import merge_prose, compose_final_text

    kind_row = store.db.execute("SELECT kind FROM artifacts WHERE id=?", (_aid,)).fetchone()
    kind = kind_row[0] if kind_row else "md"
    base_text = _content(store, kind, _base) if _base else ""
    ours_text = _content(store, kind, ours)
    theirs_text = _content(store, kind, theirs)
    result = merge_prose(base_text, ours_text, theirs_text)

    # Derive each conflict's final_text: ours -> keep ours, theirs -> theirs,
    # free -> caller-supplied resolved_text. '' (empty) == keep the deletion.
    resolutions: dict[str, str] = {}
    for c_conf in conflicts:
        (cid, sid, _b, _o, _t, _res) = c_conf
        r = by_id[cid]
        if r.resolution == "ours":
            resolutions[sid] = _o
        elif r.resolution == "theirs":
            resolutions[sid] = _t
        else:  # free
            resolutions[sid] = (r.resolved_text or _o) if r.resolved_text is not None else _o

    final_text = compose_final_text(result, resolutions)
    merged_root = store.put_blob(kind, final_text.encode("utf-8"))
    # Advance the branch that points at OUR side (the merge target): the ref
    # whose head == ours_commit. Prefer body.ours_branch-equivalent via that ref.
    target_branch = store.db.execute(
        "SELECT name FROM branches WHERE artifact_id=? AND head_commit_id=? LIMIT 1",
        (_aid, ours),
    ).fetchone()
    branch_name = target_branch[0] if target_branch else None
    result_commit = store.commit(
        [ours, theirs], merged_root, _aid,
        f"merge resolve {merge_id}", user, branch=branch_name, kind=kind,
    )
    # Persist resolutions + finalize the pending Merge row.
    with store._tx() as db:
        for c_conf in conflicts:
            (cid, _sid, _b, _o, _t, _res) = c_conf
            r = by_id[cid]
            db.execute(
                "UPDATE conflicts SET resolution=?, resolved_text=? WHERE id=?",
                (r.resolution, resolutions[_sid], cid),
            )
        db.execute(
            "UPDATE merges SET result_commit=?, state='resolved' WHERE id=?",
            (result_commit, merge_id),
        )
    return {"result_commit_id": result_commit, "merge_id": merge_id,
            "final_text": final_text}


# ---------------------------------------------------------------------------
# Ingestion  (multipart; parse -> source/artifact/edges -> root commit)
# ---------------------------------------------------------------------------
@app.post("/api/ingest", status_code=201)
async def ingest(
    file: UploadFile = File(...),
    type: str = Form(...),                       # markdown|txt|chatgpt|claude|pdf|codebase
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
) -> dict:
    kind = (type or "").lower()
    if kind not in VALID_TYPES:
        raise ApiError(400, "UNKNOWN_TYPE", f"unknown ingest type '{type}'")
    data = await file.read()
    outcome = pipeline.ingest(store, kind, file.filename or "upload", data, user)
    pipeline.commit_roots(store, outcome, user)
    for art in outcome.artifacts:
        if art.commit_id:
            _index_commit(store, art.commit_id, "main")
    return {
        "source_id": outcome.source_id,
        "artifact_ids": outcome.artifact_ids,
        "warnings": outcome.warnings,
    }


# ---------------------------------------------------------------------------
# Retrieval / search  (engine stub -> 501)
# ---------------------------------------------------------------------------
@app.post("/api/search")
def search(
    body: SearchBody,
    user: str = Depends(get_user),
    store: ObjectStore = Depends(get_store),
) -> dict:
    if not body.query.strip():
        raise ApiError(400, "EMPTY_QUERY", "query must be non-empty")
    return retrieval.search(
        store, body.query, max(1, body.k), body.branch,
        body.as_of_commit, body.artifact_kind,
    )  # NotImplementedError -> 501 until the retrieval engine lands


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
@app.get("/api/provenance/claim/{claim_id}")
def provenance_claim(claim_id: str, store: ObjectStore = Depends(get_store)) -> dict:
    res = provenance.get_claim(store, claim_id)
    if res is None:
        raise ApiError(404, "CLAIM_NOT_FOUND", f"unknown claim {claim_id}")
    return res


@app.get("/api/provenance/artifact/{artifact_id}/sources")
def provenance_artifact_sources(
    artifact_id: str, store: ObjectStore = Depends(get_store)
) -> list[dict]:
    if _artifact(store, artifact_id) is None:
        raise ApiError(404, "ARTIFACT_NOT_FOUND", f"unknown artifact {artifact_id}")
    return provenance.artifact_sources(store, artifact_id)


@app.get("/api/provenance/at/{commit_id}/claims")
def provenance_at(commit_id: str, store: ObjectStore = Depends(get_store)) -> list[dict]:
    return provenance.claims_at(store, commit_id)


# ---------------------------------------------------------------------------
# Realtime collaboration (realtime-protocol.md / collaboration-spec.md)
# ---------------------------------------------------------------------------
@app.websocket("/collaborate/{artifact_id}")
async def collaborate_ws(
    websocket: WebSocket,
    artifact_id: str,
    branch: str = "main",
    user: str = "anonymous",
) -> None:
    """WS /collaborate/:artifact_id?branch=X&user=userA — live CRDT editing.

    Binary yjs sync + awareness frames and JSON control frames
    (commit_request / presence_ping) are handled in backend/src/realtime/ws.py
    against a per-(artifact, branch) pycrdt Doc; commit-from-live is serialized
    per artifact and lands as a normal DAG commit (store.commit CAS).
    """
    await realtime_ws.collaborate(websocket, artifact_id, branch, user)


# ---------------------------------------------------------------------------
# Static frontend + health
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


if _FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="static")


def _now() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def _index_commit(store: ObjectStore, commit_id: str, branch: str) -> None:
    """Delta-reindex the retrieval index for a fresh commit (retrieval-spec.md).

    The index is DERIVED data: a failure here must never corrupt the commit
    response or the object store — log it and let scripts/reindex.py rebuild
    from the object store. Vector-leg failures degrade inside the indexer.
    """
    try:
        retrieval_indexer.get_indexer(store).reindex(commit_id, branch=branch)
    except Exception:
        logging.exception("retrieval index update failed for commit %s", commit_id)