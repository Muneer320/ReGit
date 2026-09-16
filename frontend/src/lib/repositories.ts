import { apiFetch, request } from './api'
import type { CommitInfo } from './types'

export interface Repository {
  id: string
  name: string
  created_at?: string
  branches: {name: string; head: string}[]
}
export interface FileReference {artifact_id: string; commit_id: string; kind: string; branch: string}
export interface TreeEntry {
  path: string
  type: 'folder' | 'file'
  kind?: string
  size?: number
  editable?: boolean
  artifacts?: FileReference[]
}
export interface Snapshot extends Repository {branch: string; commit_id: string; entries: TreeEntry[]}
export interface Activity {commit_id: string; artifact_id: string; title: string; kind: string; message: string; author: string; author_date: string}

const route = (id: string) => `/repositories/${encodeURIComponent(id)}`
export const repositories = {
  list: () => request<Repository[]>('GET', '/repositories'),
  create: (name: string) => request<Snapshot>('POST', '/repositories', {name}),
  snapshot: (id: string, branch = 'main', commit = '') => request<Snapshot>('GET', `${route(id)}?${new URLSearchParams({branch, ...(commit ? {commit} : {})})}`),
  history: (id: string, branch: string) => request<CommitInfo[]>('GET', `${route(id)}/history?${new URLSearchParams({branch})}`),
  branch: (snapshot: Snapshot, name: string) => request<Snapshot>('POST', `${route(snapshot.id)}/branches`, {name, from_commit: snapshot.commit_id}),
  folder: (snapshot: Snapshot, path: string, message: string) => request<Snapshot>('POST', `${route(snapshot.id)}/folders`, {path, branch: snapshot.branch, base_commit: snapshot.commit_id, message}),
  upload: (snapshot: Snapshot, files: File[], path: string, message: string, type: string) => {
    const form = new FormData()
    files.forEach(file => form.append('files', file)); form.append('path', path); form.append('branch', snapshot.branch)
    form.append('base_commit', snapshot.commit_id); form.append('message', message); form.append('file_type', type)
    return request<Snapshot>('POST', `${route(snapshot.id)}/files`, form)
  },
  bytes: (snapshot: Snapshot, path: string) => apiFetch('GET', `${route(snapshot.id)}/file?${new URLSearchParams({path, branch: snapshot.branch, commit: snapshot.commit_id})}`),
  edit: (snapshot: Snapshot, path: string, content: string, message: string) => request<Snapshot>('PATCH', `${route(snapshot.id)}/file`, {path, content, message, branch: snapshot.branch, base_commit: snapshot.commit_id}),
  remove: (snapshot: Snapshot, path: string, message: string) => request<Snapshot>('DELETE', `${route(snapshot.id)}/entry`, {path, message, branch: snapshot.branch, base_commit: snapshot.commit_id}),
  delete: (id: string) => request<void>('DELETE', route(id)),
  activity: () => request<Activity[]>('GET', '/activity'),
}
