// Requests always use the backend; failures remain visible to the interface.
import type { Artifact, CommitInfo, DiffResponse, IngestResponse, IngestType, MergeResponse,
  RepositoryEntry, Resolution, ResolveResponse, SearchResult } from './types'

export const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api'

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) { super(message); this.status = status; this.code = code }
}
export function currentUser(): string { return localStorage.getItem('regit_user') || 'userA' }
export function setCurrentUser(user: string) { localStorage.setItem('regit_user', user) }

export async function apiFetch(method: string, path: string, body?: unknown): Promise<Response> {
  const multipart = body instanceof FormData
  const headers: Record<string, string> = { 'X-User': currentUser() }
  if (!multipart && body !== undefined) headers['Content-Type'] = 'application/json'
  const token = sessionStorage.getItem('regit_demo_token')
  if (token) headers.Authorization = `Bearer ${token}`
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { method, headers,
      body: body === undefined ? undefined : multipart ? body : JSON.stringify(body) })
  } catch { throw new ApiError(0, 'NETWORK', 'Backend unreachable. Start the local ReGit server.') }
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    let code = `HTTP_${response.status}`
    try { const error = await response.json(); message = error?.error?.message ?? error?.detail ?? message; code = error?.error?.code ?? code } catch { /* non-JSON error */ }
    throw new ApiError(response.status, code, String(message))
  }
  return response
}
export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await apiFetch(method, path, body)
  return response.status === 204 ? undefined as T : await response.json() as T
}

export const api = {
  health: () => request<{ status: string; version?: string }>('GET', '/health'),
  listArtifacts: () => request<Artifact[]>('GET', '/artifacts'),
  getArtifact: (id: string) => request<Artifact>('GET', `/artifacts/${id}`),
  tree: (id: string) => request<RepositoryEntry[]>('GET', `/artifacts/${id}/tree`),
  createFolder: (id: string, path: string) => request<{path: string; type: 'folder'}>('POST', `/artifacts/${id}/folders`, {path}),
  uploadFiles: (id: string, files: File[], path = '') => {
    const form = new FormData(); files.forEach(file => form.append('files', file)); form.append('path', path)
    return request<{files: {path: string; artifact_id?: string; commit_id?: string; error?: string}[]; errors: {path: string; error: string}[]}>('POST', `/artifacts/${id}/files`, form)
  },
  createArtifact: (body: {kind: string; title: string; content?: string}) => request<{artifact_id: string; root_commit_id: string}>('POST', '/artifacts', body),
  deleteArtifact: (id: string) => request<void>('DELETE', `/artifacts/${id}`),
  commit: (id: string, body: {branch: string; content: string; message: string; base_commit?: string}) => request<{commit_id: string; parent_ids: string[]}>('POST', `/artifacts/${id}/commit`, body),
  history: (id: string, branch?: string) => request<CommitInfo[]>('GET', `/artifacts/${id}/history${branch ? `?branch=${encodeURIComponent(branch)}` : ''}`),
  createBranch: (body: {artifact_id: string; name: string; from_commit?: string}) => request<{name: string; head: string}>('POST', '/branches', body),
  listBranches: (id: string) => request<{name: string; head_commit_id: string}[]>('GET', `/branches?artifact_id=${encodeURIComponent(id)}`),
  checkout: (body: {artifact_id: string; branch?: string; commit?: string}) => request<{content: string; commit_id: string}>('POST', '/checkout', body),
  diff: (id: string, from: string, to: string) => request<DiffResponse>('GET', `/diff?artifact_id=${encodeURIComponent(id)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`),
  merge: (artifactId: string, oursBranch: string, theirsBranch: string) => request<MergeResponse>('POST', '/merge', {artifact_id: artifactId, ours_branch: oursBranch, theirs_branch: theirsBranch}),
  resolveMerge: (id: string, resolutions: Resolution[]) => request<ResolveResponse>('POST', `/merge/${id}/resolve`, {resolutions}),
  ingest: (files: File | File[], type: IngestType) => {
    const form = new FormData(); (Array.isArray(files) ? files : [files]).forEach(file => form.append('files', file)); form.append('type', type)
    return request<IngestResponse>('POST', '/ingest', form)
  },
  search: async (query: string, options: {k?: number; branch?: string; as_of_commit?: string; artifact_kind?: string} = {}): Promise<SearchResult[]> => {
    const result = await request<{results: SearchResult[]}>('POST', '/search', {query, k: options.k ?? 8, ...options})
    return result.results
  },
}
