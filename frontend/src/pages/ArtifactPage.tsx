import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Artifact, BranchRef } from '../lib/types'
import { navigate, useRoute } from '../lib/router'
import { useApp } from '../state/store'
import { ErrorState, Hash, KindBadge } from '../components/ui'
import { LiveEditor } from '../components/LiveEditor'

export function ArtifactPage({ artifactId }: {artifactId: string}) {
  const route = useRoute()
  const requestedBranch = route.query.get('branch')
  const branch = requestedBranch || 'main'
  const { toast } = useApp()
  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const [branches, setBranches] = useState<BranchRef[]>([])
  const [content, setContent] = useState('')
  const [head, setHead] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [live, setLive] = useState(false)
  const [draft, setDraft] = useState('')
  const [message, setMessage] = useState('')
  const [newBranch, setNewBranch] = useState('')
  const [busy, setBusy] = useState(false)
  const load = useCallback(async () => {
    try {
      const [item, refs] = await Promise.all([api.getArtifact(artifactId), api.listBranches(artifactId)])
      const target = refs.find(ref => ref.name === branch) || (!requestedBranch ? refs[0] : undefined)
      if (!target) throw new Error('Branch does not exist.')
      if (target.name !== branch) { navigate(`/art/${artifactId}?branch=${encodeURIComponent(target.name)}`); return }
      const checkout = await api.checkout({artifact_id: artifactId, branch})
      setArtifact(item); setBranches(refs); setContent(checkout.content); setHead(checkout.commit_id); setError(null)
    } catch (e) { setError(String(e)) }
  }, [artifactId, branch, requestedBranch])
  useEffect(() => { setEditing(false); setLive(false); void load() }, [load])
  const commit = async () => {
    if (!message.trim()) { toast('Enter a commit message.', 'error'); return }
    setBusy(true)
    try { await api.commit(artifactId, {branch, content: draft, message: message.trim(), base_commit: head}); setEditing(false); setMessage(''); await load(); toast('Research artifact committed.', 'success') }
    catch (e) { toast(String(e), 'error') } finally { setBusy(false) }
  }
  const createBranch = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true)
    try { await api.createBranch({artifact_id: artifactId, name: newBranch.trim(), from_commit: head}); navigate(`/art/${artifactId}?branch=${encodeURIComponent(newBranch.trim())}`); setNewBranch('') }
    catch (e) { toast(String(e), 'error') } finally { setBusy(false) }
  }
  if (error) return <div className="page"><ErrorState message={error} retry={load} /></div>
  if (!artifact) return <div className="page state-block">Loading research artifact…</div>
  const prose = artifact.kind === 'md' || artifact.kind === 'txt'
  const query = `branch=${encodeURIComponent(branch)}`
  return <div className="page">
    <div className="page-head"><div><h1>{artifact.title} <KindBadge kind={artifact.kind} /></h1><p className="page-sub">{branch} · <Hash hash={head} /></p></div><div className="btn-row">
      <button className="btn" onClick={() => { if (!editing || draft === content || confirm('Discard the unsaved edit and refresh?')) { setEditing(false); void load() } }}>Refresh artifact</button>
      <button className="btn" onClick={() => navigate(`/art/${artifactId}/history?${query}`)}>History</button>
      <button className="btn" disabled={!prose && artifact.kind !== 'chat'} onClick={() => navigate(`/art/${artifactId}/diff?${query}`)}>Diff</button>
      <button className="btn" disabled={!prose} onClick={() => navigate(`/art/${artifactId}/merge?ours=${encodeURIComponent(branch)}`)}>Merge prose</button>
    </div></div>
    <div className="panel repo-controls"><label>Artifact branch<select className="select" aria-label="Artifact branch" value={branch} onChange={e => navigate(`/art/${artifactId}?branch=${encodeURIComponent(e.target.value)}`)}>{branches.map(ref => <option key={ref.name}>{ref.name}</option>)}</select></label>
      <form className="btn-row" onSubmit={createBranch}><label>New branch<input className="input" aria-label="New artifact branch" value={newBranch} onChange={e => setNewBranch(e.target.value)} required /></label><button className="btn" disabled={busy || !newBranch.trim()}>Create artifact branch</button></form></div>
    <div className="panel"><div className="panel-head"><button className={`btn sm ${!live ? 'primary' : ''}`} onClick={() => setLive(false)}>Working copy</button>{prose && <button className={`btn sm ${live ? 'primary' : ''}`} onClick={() => { setEditing(false); setLive(true) }}>Live editor</button>}<span className="spacer" />{!live && prose && !editing && <button className="btn sm" onClick={() => { setDraft(content); setEditing(true) }}>Edit &amp; commit</button>}</div>
      {live && prose ? <LiveEditor artifactId={artifactId} branch={branch} onCommitted={load} /> : editing ? <div className="panel-body">
        <textarea className="repo-editor mono" aria-label="Research artifact contents" value={draft} onChange={e => setDraft(e.target.value)} spellCheck={false} />
        <div className="btn-row"><input className="input" aria-label="Artifact commit message" value={message} onChange={e => setMessage(e.target.value)} placeholder="Commit message" /><button className="btn primary" disabled={busy || draft === content || !message.trim()} onClick={commit}>Commit artifact changes</button><button className="btn" onClick={() => setEditing(false)}>Cancel edit</button></div>
      </div> : <pre className="content-preview" style={{padding: 16, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{content}</pre>}
    </div>
    <p className="dim small">Prose supports live editing, sentence diff and three-way merge. Chat supports message diff; PDF and codebase artifacts show their parsed representation. Repository downloads retain original files.</p>
    {artifact.source_id && <p className="mono faint small">Source: {artifact.source_id}</p>}
  </div>
}
