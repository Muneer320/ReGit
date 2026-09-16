import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { repositories } from '../lib/repositories'
import type { Repository } from '../lib/repositories'
import type { Artifact } from '../lib/types'
import { navigate } from '../lib/router'
import { useApp } from '../state/store'
import { seedDemoData } from '../lib/seed'
import { IngestDialog } from '../components/IngestDialog'
import { ErrorState, KindBadge } from '../components/ui'

export function WorkspacePage() {
  const { toast } = useApp()
  const [repos, setRepos] = useState<Repository[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [filter, setFilter] = useState('')
  const [busy, setBusy] = useState(false)
  const [ingest, setIngest] = useState(false)
  const load = useCallback(async () => {
    try { setError(null); const [r, a] = await Promise.all([repositories.list(), api.listArtifacts()]); setRepos(r); setArtifacts(a) }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])
  const create = async (event: React.FormEvent) => {
    event.preventDefault(); if (!name.trim()) return; setBusy(true)
    try { const repo = await repositories.create(name.trim()); navigate(`/repo/${repo.id}`) }
    catch (e) { toast(String(e), 'error') } finally { setBusy(false) }
  }
  const seed = async () => {
    setBusy(true)
    try { await seedDemoData(); await load(); toast('Created a real merge example in Research artifacts.', 'success') }
    catch (e) { toast(String(e), 'error') } finally { setBusy(false) }
  }
  const remove = async (artifact: Artifact) => {
    if (!confirm(`Delete “${artifact.title}” from the workspace?`)) return
    try { await api.deleteArtifact(artifact.id); await load() } catch (e) { toast(String(e), 'error') }
  }
  return <div className="page">
    <div className="page-head"><div><h1>Research workspace</h1><p className="page-sub">{repos.length} repositories · {artifacts.length} research artifacts in this local store.</p></div>
      <div className="btn-row"><button className="btn" disabled={busy} onClick={seed}>Load merge example</button><button className="btn" onClick={() => setIngest(true)}>Import research source</button></div></div>
    <div className="notice">Local shared demo. User A/B are editing identities; all workspace contents are shared.</div>
    {error && <ErrorState message={error} retry={load} />}
    <section className="panel"><div className="panel-head">Repositories</div>
      <form className="repo-form" onSubmit={create}><label>New repository name<input aria-label="Repository name" value={name} onChange={e => setName(e.target.value)} maxLength={120} required /></label><button className="btn primary" disabled={busy}>Create repository</button></form>
      <div className="repo-form"><label>Filter repositories<input aria-label="Filter repositories" value={filter} onChange={e => setFilter(e.target.value)} /></label></div>
      {loading ? <p className="state-block">Loading workspace…</p> : <div className="repo-grid">{repos.filter(repo => repo.name.toLowerCase().includes(filter.toLowerCase())).map(repo =>
        <article className="panel repo-summary" key={repo.id}><h2><button className="link" onClick={() => navigate(`/repo/${repo.id}`)}>{repo.name}</button></h2><p className="dim">{repo.branches.length} branch{repo.branches.length === 1 ? '' : 'es'}</p><p className="mono faint small">{repo.id}</p><button className="btn" onClick={() => navigate(`/repo/${repo.id}`)}>Open repository</button></article>)}</div>}
      {!loading && repos.length === 0 && <p className="state-block">Create a repository, then add folders and upload files. Every change saves a versioned snapshot.</p>}
    </section>
    <section className="panel"><div className="panel-head">Research artifacts <span className="faint small">Typed sources, per-file branches, semantic diff and prose merge</span></div>
      {artifacts.map(artifact => <div className="repo-file-row" key={artifact.id}><KindBadge kind={artifact.kind} /><button className="link" onClick={() => navigate(`/art/${artifact.id}?branch=${encodeURIComponent(artifact.branches[0]?.name || 'main')}`)}>{artifact.title}</button><span className="spacer" /><span className="faint small">{artifact.branches.length} branches</span><button className="btn sm" onClick={() => remove(artifact)}>Delete artifact</button></div>)}
      {!loading && artifacts.length === 0 && <p className="state-block">Import a source or load the merge example. Repository uploads also extract supported research artifacts.</p>}
    </section>
    {ingest && <IngestDialog onClose={() => setIngest(false)} onIngested={load} />}
  </div>
}
