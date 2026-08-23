# API Contract (LOCKED before implementation)

Base: `http://localhost:8377/api`. JSON in/out. Errors: `{error: {code, message}}` with HTTP status. All mutating endpoints are idempotent via content addressing or natural keys. Mock users via header `X-User: userA|userB`.

## Artifacts
### POST /artifacts
Req `{kind, title, content?, source_id?}` → 201 `{artifact_id, root_commit_id}`. Creates root commit. 400 on bad kind.

### GET /artifacts
Lists every artifact → `[{id, kind, title, branches: [{name, head}], source_id}]` (newest first). Powers the workspace server-side (survives page reload).

### GET /artifacts/:id
→ `{id, kind, title, branches: [{name, head}], source_id}`. 404 unknown id.

### DELETE /artifacts/:id
Tombstones the artifact + detaches from workspaces. Object store untouched (immutability). → 204. 404 unknown.

### POST /artifacts/:id/commit
Req `{branch, content, message, base_commit?}` → 201 `{commit_id, parent_ids}`. Concurrency: per-artifact lock; if `base_commit` given and != branch head → 409 `{head}` (client must rebase/merge). Idempotency: identical canonical content + same parents = same commit id (dedup, returns 200 with existing id).

### GET /artifacts/:id/history?branch=
→ `[{commit_id, parents, message, author, author_date}]` newest-first DAG walk.

## Branches
### POST /branches
Req `{artifact_id, name, from_commit?}` (default: head of artifact's default branch) → 201 `{name, head}`.

### GET /branches?artifact_id=
→ `[{name, head_commit_id}]`.

### POST /checkout
Req `{artifact_id, branch, commit?}` → `{content, commit_id}`. Read-only; never moves refs.

## Diff
### GET /diff?artifact_id=&from=&to=
→ `{kind, changes: [Change]}` per diff-spec.md. `from`/`to` are commit ids. 400 if same; 404 unknown commit.

## Merge
### POST /merge
Req `{artifact_id, ours_branch, theirs_branch}` → 201 `{merge_id, state: clean|conflicts, conflicts: [...], preview_text}`. `clean` auto-creates result commit (2 parents) and advances ours_branch. `conflicts` persists pending Merge; no refs move.

### POST /merge/:id/resolve
Req `{resolutions: [{conflict_id, resolution, resolved_text?}]}` → 200 `{result_commit_id}`. 409 if already resolved; 400 if unresolved conflicts remain.

## Ingestion
### POST /ingest (multipart file + `type` field: markdown|chatgpt|claude|pdf|codebase)
→ 201 `{source_id, artifact_ids: [...], warnings: []}`. Parse failures: 422 with per-file message; image-only PDF → 422 `PDF_NOT_EXTRACTABLE`. Idempotent: re-ingesting identical canonical content dedups blobs (same ids returned).

## Retrieval
### POST /search
Req `{query, k?=5, branch?, as_of_commit?, artifact_kind?}` → `{results: [SearchResult]}` (cited per data-model). 400 empty query.

## Provenance
### GET /provenance/claim/:id → `{claim, chain: [{kind, id, snippet}]}`
### GET /provenance/artifact/:id/sources → `[{source, via_commits}]`
### GET /provenance/at/:commit_id/claims → `[Claim]` (ancestry-filtered — the "what was known at X" query)

## Realtime
### WS /collaborate/:artifact_id?branch=&user=
Binary yjs sync + awareness frames (see realtime-protocol.md). JSON control frames: `{type:"commit_request", message}` → server commits live doc (lock) → `{type:"committed", commit_id}` broadcast to room.

## Concurrency behavior summary
- Artifact commits: serialized per artifact (asyncio lock); stale-base writes → 409.
- Ref moves: single UPDATE guarded by expected head (compare-and-swap).
- Merge creation: serialized per artifact pair; duplicate pending merges return the existing merge id.
