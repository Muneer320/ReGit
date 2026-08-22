"""Core data model types for ReGit.

Mirrors docs/data-model.md exactly. Content-addressed ids are hex SHA-256;
relational ids use prefixed ULIDs. Keep in sync with the spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ArtifactKind(str, Enum):
    MD = "md"
    TXT = "txt"
    CHAT = "chat"
    PDF = "pdf"
    CODEBASE = "codebase"
    CODE_FILE = "code-file"
    TREE = "tree"


BLOB_HASH_TAG = "gr-obj-v1"
COMMIT_HASH_TAG = "gr-commit-v1"


@dataclass(frozen=True)
class Blob:
    id: str  # sha256 hex
    kind: ArtifactKind
    size: int
    data: bytes  # canonical bytes (uncompressed in memory; zlib on disk)


@dataclass(frozen=True)
class TreeEntry:
    path: str
    blob_id: str
    kind: ArtifactKind


@dataclass(frozen=True)
class Tree:
    id: str
    entries: tuple[TreeEntry, ...]  # sorted by path


@dataclass(frozen=True)
class Commit:
    id: str
    artifact_id: str
    parents: tuple[str, ...]  # 0, 1, or 2
    root_hash: str            # blob or tree id
    message: str
    author: str
    author_date: str          # ISO-8601; part of identity; pinnable via GR_AUTHOR_DATE
    kind: ArtifactKind


@dataclass
class Branch:
    name: str
    artifact_id: str
    head_commit_id: str
    created_at: str


@dataclass(frozen=True)
class Artifact:
    id: str
    kind: ArtifactKind
    title: str
    source_id: str | None
    created_at: str


@dataclass(frozen=True)
class ArtifactVersion:
    commit_id: str
    artifact_id: str
    author_date: str
    message: str
    root_hash: str


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    created_at: str


class ChangeStatus(str, Enum):
    UNCHANGED = "unchanged"
    EDITED = "edited"
    ADDED = "added"
    DELETED = "deleted"
    MOVED = "moved"
    RENAMED = "renamed"


@dataclass(frozen=True)
class Change:
    span: str  # prose sid | code qualified name | chat "msg:ord:role" | pdf "page:p:s"
    status: ChangeStatus
    old_text: str | None = None
    new_text: str | None = None
    similarity: float | None = None


@dataclass(frozen=True)
class Diff:
    id: str
    artifact_id: str
    from_commit: str
    to_commit: str
    kind: ArtifactKind
    changes: tuple[Change, ...]
    created_at: str


class MergeState(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    ABORTED = "aborted"


@dataclass
class Merge:
    id: str
    artifact_id: str
    base_commit: str
    ours_commit: str
    theirs_commit: str
    result_commit: str | None
    state: MergeState
    created_at: str


class Resolution(str, Enum):
    OURS = "ours"
    THEIRS = "theirs"
    FREE = "free"


@dataclass
class Conflict:
    id: str
    merge_id: str
    span: str
    base_text: str
    ours_text: str
    theirs_text: str
    resolution: Resolution | None = None
    resolved_text: str | None = None


@dataclass(frozen=True)
class CRDTOperation:
    id: str
    room: str            # f"{artifact_id}:{branch}"
    seq: int             # per-room monotonic; observability only
    client_id: str
    op: bytes            # yjs binary update
    received_at: str


@dataclass(frozen=True)
class ResearchSource:
    id: str
    type: str            # chatgpt|claude|pdf|markdown|codebase|manual
    original_filename: str
    imported_at: str
    uploader: str


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    artifact_id: str
    commit_id: str
    sid: str | None
    created_at: str


@dataclass(frozen=True)
class ProvenanceEdge:
    id: str
    from_kind: str       # source|artifact|version|commit|claim
    from_id: str
    to_kind: str
    to_id: str
    relation: str        # imported_as|has_version|in_commit|states|derived_from
    created_at: str


@dataclass(frozen=True)
class EmbeddingMeta:
    chunk_id: str
    vector_dim: int      # 384 for MiniLM-L6-v2
    model: str           # "all-MiniLM-L6-v2" | "hash-fallback"


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    text: str
    score: float
    artifact_id: str
    artifact_title: str
    branch: str
    introduced_in_commit: str
    sid_range: str
    source_type: str | None
    source_filename: str | None
