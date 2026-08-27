// ReGit REST client — single source of truth for backend communication
// (docs/specs/api-contract.md). Every component talks ONLY to this module.
//
// Strategy: try the real backend first. Where the engine is still a 501 stub
// (merge-conflict persistence, resolve, search) or the backend is unreachable,
// fall back to the local demo adapter in mock.ts and flag the response with
// `viaMock` so the UI can show it honestly. Contract errors (400/404/409…)
// always surface as ApiError — never silently swallowed.

import type {
  Artifact,
  ArtifactRecord,
  Change,
  CommitInfo,
  DiffResponse,
  IngestResponse,
  IngestType,
  MergeResponse,
  RepositoryEntry,
  Resolution,
  ResolveResponse,
  SearchResult,
} from './types'
import {
  mockHasMerge,
  mockMerge,
  mockResolve,
  mockSearch,
  registerArtifacts,
  registryList,
} from './mock'

export const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api'

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export function currentUser(): string {
  return localStorage.getItem('regit_user') || 'userA'
}

export function setCurrentUser(u: string) {
  localStorage.setItem('regit_user', u)
}

type Headers = Record<string, string>

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isMultipart = typeof FormData !== 'undefined' && body instanceof FormData
  const headers: Headers = {}
  if (!isMultipart) headers['Content-Type'] = 'application/json'
  headers['X-User'] = currentUser()

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isMultipart ? body : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'NETWORK', 'backend unreachable')
  }

  if (!res.ok) {
    let code = `HTTP_${res.status}`
    let msg = `HTTP ${res.status}`
    try {
      const j = await res.json()
      msg = j?.error?.message ?? j?.detail ?? msg
      code = j?.error?.code ?? code
    } catch {
      /* non-JSON body */
    }
    throw new ApiError(res.status, code, msg)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function isFallback(err: unknown): boolean {
  return (
    err instanceof ApiError &&
    (err.status === 0 || err.status === 501 || err.code === 'NOT_IMPLEMENTED' || err.code === 'NETWORK')
  )
}

// ---------------------------------------------------------------------------
// Artifact registry — the locked contract has no "list artifacts" endpoint, so
// the workspace tracks ids it has seen (ingest/create) and hydrates each one
// live. If a future backend adds GET /artifacts we prefer it transparently.
// ---------------------------------------------------------------------------
const REGISTRY_KEY = 'regit_artifacts'

function registryLoad(): ArtifactRecord[] {
  try {
    return JSON.parse(localStorage.getItem(REGISTRY_KEY) || '[]') as ArtifactRecord[]
  } catch {
    return []
  }
}

function registrySave(recs: ArtifactRecord[]) {
  localStorage.setItem(REGISTRY_KEY, JSON.stringify(recs))
}

export function registryRegister(recs: ArtifactRecord[]) {
  const existing = new Map(registryLoad().map((r) => [r.id, r]))
  for (const r of recs) existing.set(r.id, { ...existing.get(r.id), ...r })
  registrySave([...existing.values()].sort((a, b) => b.created_at.localeCompare(a.created_at)))
}

/** List artifacts: real list endpoint if present, else hydrate the registry. */
async function listArtifacts(): Promise<Artifact[]> {
  // Preferred path once the backend grows a list endpoint.
  try {
    const rows = await request<unknown[]>('GET', '/artifacts')
    if (Array.isArray(rows)) {
      const hydrated = await Promise.all(
        rows.map(async (r: any) => {
          if (r && typeof r.id === 'string' && r.kind && r.title !== undefined) return r as Artifact
          return request<Artifact>('GET', `/artifacts/${String(r?.id ?? r)}`).catch(() => null)
        }),
      )
      const ok = hydrated.filter(Boolean) as Artifact[]
      if (ok.length > 0) return ok
    }
  } catch {
    /* no list endpoint — fall through */
  }
  const recs = registryList()
  const arts = await Promise.all(
    recs.map(async (r): Promise<Artifact & { __dead?: boolean }> => {
      try {
        const a = await request<Artifact>('GET', `/artifacts/${r.id}`)
        return { ...a, title: a.title || r.title }
      } catch {
        return { id: r.id, kind: r.kind, title: r.title, branches: [], source_id: null, __dead: true }
      }
    }),
  )
  return arts.filter((a) => a.__dead !== true)
}

// ---------------------------------------------------------------------------
// Public API surface
// ---------------------------------------------------------------------------
export const api = {
  health: () => request<{ status: string; version?: string }>('GET', '/health'),

  listArtifacts,

  async getArtifact(id: string): Promise<Artifact> {
    return request<Artifact>('GET', `/artifacts/${id}`)
  },

  tree: (id: string) => request<RepositoryEntry[]>('GET', `/artifacts/${id}/tree`),

  createFolder: (id: string, path: string) =>
    request<{ path: string; type: 'folder' }>('POST', `/artifacts/${id}/folders`, { path }),

  uploadFiles: async (id: string, files: File[], path = '') => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    form.append('path', path)
    return request<{ files: { path: string; artifact_id?: string; commit_id?: string; error?: string }[]; errors: { path: string; error: string }[] }>(
      'POST', `/artifacts/${id}/files`, form,
    )
  },

  async createArtifact(body: { kind: string; title: string; content?: string }): Promise<{
    artifact_id: string
    root_commit_id: string
  }> {
    const r = await request<{ artifact_id: string; root_commit_id: string }>(
      'POST',
      '/artifacts',
      body,
    )
    registerArtifacts([r.artifact_id], body.title)
    return r
  },

  deleteArtifact: (id: string) => request<void>('DELETE', `/artifacts/${id}`),

  commit: (id: string, body: { branch: string; content: string; message: string; base_commit?: string }) =>
    request<{ commit_id: string; parent_ids: string[] }>(
      'POST',
      `/artifacts/${id}/commit`,
      body,
    ),

  history: (id: string, branch?: string): Promise<CommitInfo[]> =>
    request<CommitInfo[]>(
      'GET',
      `/artifacts/${id}/history${branch ? `?branch=${encodeURIComponent(branch)}` : ''}`,
    ),

  createBranch: (body: { artifact_id: string; name: string; from_commit?: string }) =>
    request<{ name: string; head: string }>('POST', '/branches', body),

  listBranches: (artifactId: string) =>
    request<{ name: string; head_commit_id: string }[]>(
      'GET',
      `/branches?artifact_id=${encodeURIComponent(artifactId)}`,
    ),

  checkout: (body: { artifact_id: string; branch?: string; commit?: string }) =>
    request<{ content: string; commit_id: string }>('POST', '/checkout', body),

  diff: async (artifactId: string, from: string, to: string): Promise<DiffResponse> => {
    try {
      return await request<DiffResponse>(
        'GET',
        `/diff?artifact_id=${encodeURIComponent(artifactId)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
      )
    } catch (err) {
      if (!isFallback(err)) throw err
      return mockDiff(artifactId, from, to)
    }
  },

  merge: async (
    artifactId: string,
    oursBranch: string,
    theirsBranch: string,
  ): Promise<MergeResponse> => {
    try {
      const r = await request<MergeResponse>('POST', '/merge', {
        artifact_id: artifactId,
        ours_branch: oursBranch,
        theirs_branch: theirsBranch,
      })
      return r
    } catch (err) {
      if (!isFallback(err)) throw err
      return mockMerge(artifactId, oursBranch, theirsBranch)
    }
  },

  resolveMerge: async (mergeId: string, resolutions: Resolution[]): Promise<ResolveResponse> => {
    // A merge id minted by the local adapter never exists on the backend —
    // resolving it must go through the adapter, not the 404 path.
    if (mockHasMerge(mergeId)) return mockResolve(mergeId, resolutions)
    try {
      return await request<ResolveResponse>('POST', `/merge/${mergeId}/resolve`, {
        resolutions,
      })
    } catch (err) {
      if (!isFallback(err)) throw err
      return mockResolve(mergeId, resolutions)
    }
  },

  ingest: async (files: File | File[], type: IngestType): Promise<IngestResponse> => {
    const selected = Array.isArray(files) ? files : [files]
    const form = new FormData()
    for (const file of selected) form.append('files', file)
    form.append('type', type)
    let res: Response
    try {
      res = await fetch(`${API_BASE}/ingest`, {
        method: 'POST',
        body: form,
        headers: { 'X-User': currentUser() },
      })
    } catch {
      throw new ApiError(0, 'NETWORK', 'backend unreachable')
    }
    if (!res.ok) {
      let code = `HTTP_${res.status}`
      let msg = `HTTP ${res.status}`
      try {
        const j = await res.json()
        msg = j?.error?.message ?? j?.detail ?? msg
        code = j?.error?.code ?? code
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, code, msg)
    }
    const out = (await res.json()) as IngestResponse
    registerArtifacts(out.artifact_ids, selected.map((file) => file.name).join(', '))
    return out
  },

  search: async (
    query: string,
    opts: { k?: number; branch?: string; as_of_commit?: string; artifact_kind?: string } = {},
  ): Promise<SearchResult[]> => {
    try {
      const r = await request<{ results: SearchResult[] }>('POST', '/search', {
        query,
        k: opts.k ?? 8,
        ...opts,
      })
      return r.results ?? []
    } catch (err) {
      if (!isFallback(err)) throw err
      return mockSearch(query, opts)
    }
  },
}

export { registryLoad, registrySave }

// ---------------------------------------------------------------------------
// Local diff fallback (mirrors align.diff_prose output shape).
// ---------------------------------------------------------------------------
async function mockDiff(artifactId: string, from: string, to: string): Promise<DiffResponse> {
  const [oldC, newC] = await Promise.all([
    api.checkout({ artifact_id: artifactId, commit: from }),
    api.checkout({ artifact_id: artifactId, commit: to }),
  ])
  const { diffProseLocal } = await import('./mergelocal')
  const changes: Change[] = diffProseLocal(oldC.content, newC.content, artifactId)
  return { kind: 'md', changes, viaMock: true }
}
