-- Canonical DDL from docs/data-model.md (ADR-09). Append-only + immutability triggers.
CREATE TABLE IF NOT EXISTS objects(hash TEXT PRIMARY KEY, kind TEXT NOT NULL, size INTEGER NOT NULL, path TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commits(id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, root_hash TEXT NOT NULL,
                     message TEXT, author TEXT, author_date TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS commit_parents(commit_id TEXT NOT NULL, parent_id TEXT NOT NULL, PRIMARY KEY(commit_id, parent_id));
CREATE TABLE IF NOT EXISTS refs(name TEXT NOT NULL, artifact_id TEXT NOT NULL, head TEXT NOT NULL, PRIMARY KEY(name, artifact_id));
CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT, source_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS branches(name TEXT NOT NULL, artifact_id TEXT NOT NULL, head_commit_id TEXT NOT NULL, created_at TEXT,
                      PRIMARY KEY(name, artifact_id));
CREATE TABLE IF NOT EXISTS tombstones(artifact_id TEXT PRIMARY KEY, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY, name TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS workspace_members(workspace_id TEXT, artifact_id TEXT, branch_name TEXT, PRIMARY KEY(workspace_id, artifact_id, branch_name));
CREATE TABLE IF NOT EXISTS merges(id TEXT PRIMARY KEY, artifact_id TEXT, base_commit TEXT, ours_commit TEXT, theirs_commit TEXT,
                    result_commit TEXT, state TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS conflicts(id TEXT PRIMARY KEY, merge_id TEXT, sid TEXT, base_text TEXT, ours_text TEXT, theirs_text TEXT,
                       resolution TEXT, resolved_text TEXT);
CREATE TABLE IF NOT EXISTS crdt_ops(id TEXT PRIMARY KEY, room TEXT, seq INTEGER, client_id TEXT, op BLOB, received_at TEXT);
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, type TEXT, original_filename TEXT, imported_at TEXT, uploader TEXT);
CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY, text TEXT, artifact_id TEXT, commit_id TEXT, sid TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS provenance_edges(id TEXT PRIMARY KEY, from_kind TEXT, from_id TEXT, to_kind TEXT, to_id TEXT, relation TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS repository_entries(
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    path TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('file','folder')),
    artifact_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(repository_id, path),
    FOREIGN KEY(repository_id) REFERENCES artifacts(id),
    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS provenance_edges_logical_unique
  ON provenance_edges(from_kind, from_id, to_kind, to_id, relation);
CREATE TABLE IF NOT EXISTS chunks(chunk_id TEXT PRIMARY KEY, artifact_id TEXT, branch TEXT, introduced_in_commit TEXT,
                    replaces TEXT, sid_range TEXT, kind TEXT, source_id TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS sentence_index(commit_id TEXT, artifact_id TEXT, sid TEXT, status TEXT, old_hash TEXT, new_hash TEXT,
                            text TEXT, PRIMARY KEY(commit_id, artifact_id, sid));
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id, text);
CREATE TRIGGER IF NOT EXISTS objects_no_update BEFORE UPDATE ON objects BEGIN SELECT RAISE(ABORT,'objects immutable'); END;
CREATE TRIGGER IF NOT EXISTS objects_no_delete BEFORE DELETE ON objects BEGIN SELECT RAISE(ABORT,'objects immutable'); END;
CREATE TRIGGER IF NOT EXISTS commits_no_update BEFORE UPDATE ON commits BEGIN SELECT RAISE(ABORT,'commits immutable'); END;
CREATE TRIGGER IF NOT EXISTS commits_no_delete BEFORE DELETE ON commits BEGIN SELECT RAISE(ABORT,'commits immutable'); END;
