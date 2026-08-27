// Domain types mirroring docs/specs/api-contract.md + docs/data-model.md.
// These are the ONLY shapes the UI is allowed to depend on.

export type ArtifactKind = 'md' | 'txt' | 'chat' | 'pdf' | 'codebase'
export type IngestType = 'markdown' | 'chatgpt' | 'claude' | 'pdf' | 'codebase'

export interface Branch {
  name: string
  head: string // GET /artifacts/:id shape
}
export interface BranchRef {
  name: string
  head_commit_id: string // GET /branches shape
}

export interface Artifact {
  id: string
  kind: ArtifactKind
  title: string
  branches: Branch[]
  source_id: string | null
}

export interface RepositoryEntry {
  path: string
  type: 'file' | 'folder'
  artifact_id?: string | null
}

/** Locally-registered artifact metadata (the contract has no list endpoint). */
export interface ArtifactRecord {
  id: string
  title: string
  kind: ArtifactKind
  created_at: string
  source_filename?: string
}

export interface CommitInfo {
  commit_id: string
  parents: string[]
  message: string
  author: string
  author_date: string
}

/** Change from diff-spec.md — the unit of the semantic diff. */
export type ChangeStatus = 'unchanged' | 'edited' | 'added' | 'deleted' | 'moved'

export interface Change {
  sid: string
  status: ChangeStatus
  old_text?: string
  new_text?: string
  similarity?: number
}

export interface DiffResponse {
  kind: string
  changes: Change[]
  /** true when produced by the local demo fallback */
  viaMock?: boolean
}

export interface Conflict {
  id: string
  sid: string
  base_text: string
  ours_text: string
  theirs_text: string
}

export type ResolutionKind = 'ours' | 'theirs' | 'free'

export interface Resolution {
  conflict_id: string
  resolution: ResolutionKind
  resolved_text?: string
}

export interface MergeResponse {
  merge_id: string
  state: 'clean' | 'conflicts'
  conflicts: Conflict[]
  preview_text?: string
  result_commit_id?: string
  ours_branch?: string
  theirs_branch?: string
  artifact_id?: string
  /** true when produced by the local demo fallback, not the backend engine */
  viaMock?: boolean
}

export interface ResolveResponse {
  result_commit_id: string
  viaMock?: boolean
}

export interface IngestResponse {
  source_id: string
  source_ids?: string[]
  artifact_ids: string[]
  warnings: string[]
  errors?: { filename: string; code: string; message: string }[]
  files?: { filename: string; source_id: string; artifact_ids: string[]; warnings: string[] }[]
}

/** SearchResult per docs/data-model.md — citations are mandatory. */
export interface SearchResult {
  chunk_id: string
  text: string
  score: number
  artifact_id: string
  artifact_title: string
  branch: string
  introduced_in_commit: string
  sid_range: string
  kind: string
  source: { type: string; filename: string } | null
  viaMock?: boolean
}
