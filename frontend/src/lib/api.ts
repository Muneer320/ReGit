// Thin REST client for the ReGit backend (docs/specs/api-contract.md).
// Base URL comes from Vite's dev proxy (same origin in dev) or the API base.
const BASE = (import.meta.env.VITE_API_BASE as string) || '/api'

type Headers = Record<string, string>

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Headers = { 'Content-Type': 'application/json' }
  // Mock auth: the demo uses two users for presence/concurrency.
  const user = localStorage.getItem('regit_user') || 'userA'
  headers['X-User'] = user

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const j = await res.json()
      msg = j?.error?.message || j?.detail || msg
    } catch {
      /* non-JSON error body */
    }
    throw new Error(msg)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  health: () => request<{ status: string }>('GET', '/health'),

  // Artifacts
  listArtifacts: () => request<any[]>('GET', '/artifacts'),
  getArtifact: (id: string) => request<any>('GET', `/artifacts/${id}`),
  createArtifact: (body: unknown) => request<any>('POST', '/artifacts', body),
  deleteArtifact: (id: string) => request<void>('DELETE', `/artifacts/${id}`),
  commit: (id: string, body: unknown) => request<any>('POST', `/artifacts/${id}/commit`, body),
  history: (id: string, branch?: string) =>
    request<any[]>('GET', `/artifacts/${id}/history${branch ? `?branch=${branch}` : ''}`),

  // Branches
  createBranch: (body: unknown) => request<any>('POST', '/branches', body),
  listBranches: (artifact_id?: string) =>
    request<any[]>('GET', `/branches${artifact_id ? `?artifact_id=${artifact_id}` : ''}`),
  checkout: (body: unknown) => request<any>('POST', '/checkout', body),

  // Diff / merge
  diff: (artifact_id: string, from: string, to: string) =>
    request<any>('GET', `/diff?artifact_id=${artifact_id}&from=${from}&to=${to}`),
  merge: (body: unknown) => request<any>('POST', '/merge', body),
  resolveMerge: (mergeId: string, body: unknown) =>
    request<any>('POST', `/merge/${mergeId}/resolve`, body),

  // Ingest / search
  ingest: (form: FormData) => ingestForm(form),
  search: (body: unknown) => request<any>('POST', '/search', body),

  // Provenance
  claim: (id: string) => request<any>('GET', `/provenance/claim/${id}`),
  artifactSources: (id: string) => request<any>('GET', `/provenance/artifact/${id}/sources`),
  claimsAtCommit: (commitId: string) => request<any>('GET', `/provenance/at/${commitId}/claims`),
}

// Ingest is multipart (no JSON header).
async function ingestForm(form: FormData): Promise<any> {
  const user = localStorage.getItem('regit_user') || 'userA'
  const res = await fetch(`${BASE}/ingest`, { method: 'POST', body: form, headers: { 'X-User': user } })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const j = await res.json()
      msg = j?.error?.message || j?.detail || msg
    } catch {
      /* ignore */
    }
    throw new Error(msg)
  }
  return res.json()
}

// Global user switcher for the two-tab presence demo.
export function setUser(u: string) {
  localStorage.setItem('regit_user', u)
}