# Current data model

`objects` indexes immutable type-tagged SHA-256 blobs stored compressed on disk. `commits` references a root hash, an artifact, author/message/date and up to two parents. `refs` and `branches` are mutable pointers updated together in guarded transactions. Commit and object update/delete triggers protect existing records.

An artifact of kind `repository` roots a canonical manifest: version, sorted folders and a mapping from relative file paths to raw blob hash, byte size, kind, editability and pinned parsed-artifact references. File artifacts retain their own commits on a branch scoped to the repository/branch. Repository branch creation initially shares a tree; later mutations create new snapshots. Historical downloads use the pinned raw hash.

`sources`, `claims` and `provenance_edges` record import origins, explicit statements and commit relationships. Prose claim capture runs in the commit transaction. Claims-at-commit is ancestry-filtered; it is a statement history, not an assertion that every ancestor claim remains true.

`crdt_documents` stores full CRDT updates plus their base commit. `crdt_ops` preserves received operations. Persisting identities avoids duplicate seed text across restarts. `chunks`, `chunks_fts` and `sentence_index` are derived current retrieval indexes. Historical search reconstructs the immutable selected revision rather than relying on overwritten current rows.

`tombstones` hides deleted repositories/artifacts from ordinary listing/search. Data is retained for history, not securely erased. The older mutable `repository_entries` table remains for compatibility with earlier artifact-attached folders; new repositories use manifests. Old artifact data is not silently rewritten into a different repository model.
