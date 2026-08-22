# Data Model — exact schemas + invariants (LOCKED)

IDs: content-addressed entities (Blob, Tree, Commit) use hex SHA-256 ids. Ephemeral/relational entities use `prefix_ulid` (e.g. `art_01J…`). All timestamps ISO-8601 UTC; `author_date` is part of commit identity and pinnable via `GR_AUTHOR_DATE`.

## Core objects

### Blob
`{id: sha256hex, kind: md|txt|chat|pdf|code-file|tree, size: int, data: bytes(zlib on disk)}`
- id = SHA256("gr-obj-v1" || kind || "\0" || canonical_bytes). Invariant: recomputing hash of stored canonical bytes == id.

### Tree
`{id: sha256hex, entries: sorted list of {path: str, blob_id: sha256hex, kind: str}}`
- id = SHA256("gr-obj-v1" || "tree" || "\0" || canonical(entries)) where canonical = JSON, sorted by path, compact separators.

### Commit
`{id: sha256hex, artifact_id: str, parents: [commit_id] (0,1,2), root_hash: sha256hex (blob or tree), message: str, author: str, author_date: iso, kind: artifact kind}`
- id = SHA256("gr-commit-v1" || sorted(parents).join(",") || root_hash || artifact_id || message || author || author_date).
- 0 parents = root; 1 = normal; 2 = merge (must link a Merge row).

### Branch
`{name: str (unique per artifact), artifact_id: str, head_commit_id: sha256hex, created_at: iso}` — the ONLY mutable pointer. Updates serialized per artifact.

### Artifact
`{id: art_*, kind: md|txt|chat|pdf|codebase, title: str, source_id: src_*|null, created_at: iso}`

### ArtifactVersion (view, not a table)
A commit id + its root content for an artifact. Exposed in API as `{commit_id, artifact_id, author_date, message, root_hash}`.

### Workspace
`{id: ws_*, name: str, created_at}` + members: `{workspace_id, artifact_id, branch_name}` (an artifact appears once per branch attached to the workspace).

## Change / Diff / Merge

### Change (unit inside a Diff)
`{sid|span, status: unchanged|edited|added|deleted|moved|renamed, old_text?, new_text?, similarity?: float}`
- prose sid = `artifact:para_idx:sent_idx` at the OLD commit; code span = qualified function/class name; chat = message ordinal+role; pdf = `page:pIdx:sIdx`.

### Diff
`{id: diff_*, artifact_id, from_commit, to_commit, kind, changes: [Change], created_at}` — derived data, recomputable; persisted for speed.

### Merge
`{id: mrg_*, artifact_id, base_commit, ours_commit, theirs_commit, result_commit|null, state: pending|resolved|aborted, created_at}`

### Conflict
`{id: cnf_*, merge_id, sid|span, base_text, ours_text, theirs_text, resolution: ours|theirs|free|null, resolved_text|null}`
- Invariant: a Merge with state=resolved has result_commit set and every Conflict has resolution set.

## Collaboration

### CRDTOperation (op log per draft doc)
`{id: op_*, room: artifact_id:branch, seq: int (per-room monotonic, debug only), client_id: str, update: bytes (yjs binary), received_at: iso}`
- Invariant: applying the log in ANY order to an empty doc converges to the same state (CRDT property); `seq` never gates correctness.

## Provenance

### ResearchSource
`{id: src_*, type: chatgpt|claude|pdf|markdown|codebase|manual, original_filename, imported_at, uploader: mock user id}`

### Claim
`{id: clm_*, text: str, artifact_id, commit_id, sid|null, created_at}` — declared via `claim: ...` sentinel lines (markdown) or `claim:`-prefixed chat messages.

### ProvenanceEdge
`{id: pe_*, from_kind: source|artifact|version|commit|claim, from_id, to_kind, to_id, relation: imported_as|has_version|in_commit|states|derived_from, created_at}`
- Invariant: every Claim has ≥1 path to a ResearchSource via edges.

## Retrieval

### Embedding (implicit in Chroma)
384-dim MiniLM-L6-v2 vector per chunk; chunk metadata: `{artifact_id, branch, introduced_in_commit, replaces: [chunk_id], sid_range, kind, source_id}`.

### SearchResult
`{chunk_id, text, score, artifact_id, artifact_title, branch, introduced_in_commit, sid_range, source: {type, filename}|null}` — citations are mandatory; a result without provenance metadata is a bug.

## SQLite DDL (canonical)

```sql
CREATE TABLE objects(hash TEXT PRIMARY KEY, kind TEXT NOT NULL, size INTEGER NOT NULL, path TEXT NOT NULL);
CREATE TABLE commits(id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, root_hash TEXT NOT NULL,
                     message TEXT, author TEXT, author_date TEXT, kind TEXT);
CREATE TABLE commit_parents(commit_id TEXT NOT NULL, parent_id TEXT NOT NULL, PRIMARY KEY(commit_id, parent_id));
CREATE TABLE refs(name TEXT NOT NULL, artifact_id TEXT NOT NULL, head TEXT NOT NULL, PRIMARY KEY(name, artifact_id));
CREATE TABLE artifacts(id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT, source_id TEXT, created_at TEXT);
CREATE TABLE branches(name TEXT NOT NULL, artifact_id TEXT NOT NULL, head_commit_id TEXT NOT NULL, created_at TEXT,
                      PRIMARY KEY(name, artifact_id));
CREATE TABLE workspaces(id TEXT PRIMARY KEY, name TEXT, created_at TEXT);
CREATE TABLE workspace_members(workspace_id TEXT, artifact_id TEXT, branch_name TEXT, PRIMARY KEY(workspace_id, artifact_id, branch_name));
CREATE TABLE merges(id TEXT PRIMARY KEY, artifact_id TEXT, base_commit TEXT, ours_commit TEXT, theirs_commit TEXT,
                    result_commit TEXT, state TEXT, created_at TEXT);
CREATE TABLE conflicts(id TEXT PRIMARY KEY, merge_id TEXT, sid TEXT, base_text TEXT, ours_text TEXT, theirs_text TEXT,
                       resolution TEXT, resolved_text TEXT);
CREATE TABLE crdt_ops(id TEXT PRIMARY KEY, room TEXT, seq INTEGER, client_id TEXT, update BLOB, received_at TEXT);
CREATE TABLE sources(id TEXT PRIMARY KEY, type TEXT, original_filename TEXT, imported_at TEXT, uploader TEXT);
CREATE TABLE claims(id TEXT PRIMARY KEY, text TEXT, artifact_id TEXT, commit_id TEXT, sid TEXT, created_at TEXT);
CREATE TABLE provenance_edges(id TEXT PRIMARY KEY, from_kind TEXT, from_id TEXT, to_kind TEXT, to_id TEXT,
                              relation TEXT, created_at TEXT);
CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY, artifact_id TEXT, branch TEXT, introduced_in_commit TEXT,
                    replaces TEXT, sid_range TEXT, kind TEXT, source_id TEXT, text TEXT);
CREATE TABLE sentence_index(commit_id TEXT, artifact_id TEXT, sid TEXT, status TEXT, old_hash TEXT, new_hash TEXT,
                            text TEXT, PRIMARY KEY(commit_id, artifact_id, sid));
CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id, text);
CREATE TRIGGER objects_no_update BEFORE UPDATE ON objects BEGIN SELECT RAISE(ABORT,'objects immutable'); END;
CREATE TRIGGER objects_no_delete BEFORE DELETE ON objects BEGIN SELECT RAISE(ABORT,'objects immutable'); END;
CREATE TRIGGER commits_no_update BEFORE UPDATE ON commits BEGIN SELECT RAISE(ABORT,'commits immutable'); END;
CREATE TRIGGER commits_no_delete BEFORE DELETE ON commits BEGIN SELECT RAISE(ABORT,'commits immutable'); END;
```

## Core invariants (automated tests, NEVER break)
1. **Content integrity:** `object_id == SHA256(canonical_content)`; verified on write and by `gr verify`.
2. **Commit immutability:** UPDATE/DELETE on objects/commits impossible (triggers) and meaningless (hashes).
3. **Branch semantics:** branch = mutable ref to immutable commit; ref updates are atomic per artifact.
4. **Convergence:** two clients applying the same valid CRDT op set reach equivalent state (property test with shuffled op logs).
5. **Provenance:** every returned claim/search hit traces to artifact version + source (edges exist; tested across branch+merge).
6. **Merge safety:** merge never silently discards incompatible changes — every both-sided divergence yields a Conflict row.
