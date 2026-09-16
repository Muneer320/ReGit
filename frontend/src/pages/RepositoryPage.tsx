import { useCallback, useEffect, useState } from 'react'
import { repositories } from '../lib/repositories'
import type { Snapshot, TreeEntry, FileReference } from '../lib/repositories'
import type { CommitInfo } from '../lib/types'
import { navigate, useRoute } from '../lib/router'
import { useApp } from '../state/store'
import { ErrorState, Hash } from '../components/ui'
import { LiveEditor } from '../components/LiveEditor'

export function RepositoryPage({ repositoryId }: {repositoryId: string}) {
  const route = useRoute()
  const branch = route.query.get('branch') || 'main'
  const revision = route.query.get('commit') || ''
  const { toast } = useApp()
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [history, setHistory] = useState<CommitInfo[]>([])
  const [error, setError] = useState<string | null>(null)
  const [folder, setFolder] = useState('')
  const [folderName, setFolderName] = useState('')
  const [newBranch, setNewBranch] = useState('')
  const [selected, setSelected] = useState('')
  const [draft, setDraft] = useState('')
  const [original, setOriginal] = useState('')
  const [fileLoading, setFileLoading] = useState(false)
  const [message, setMessage] = useState('Update research files')
  const [fileType, setFileType] = useState('auto')
  const [busy, setBusy] = useState(false)
  const [live, setLive] = useState<FileReference | null>(null)
  useEffect(() => { setLive(null) }, [repositoryId, branch, selected, revision])
  const load = useCallback(async () => {
    try {
      const [tree, commits] = await Promise.all([repositories.snapshot(repositoryId, branch, revision), repositories.history(repositoryId, branch)])
      setSnapshot(tree); setHistory(commits); setError(null)
    } catch (e) { setError(String(e)) }
  }, [repositoryId, branch, revision])
  useEffect(() => { setFolder(''); setSelected(''); void load() }, [load])
  const entry = snapshot?.entries.find(item => item.path === selected && item.type === 'file')
  useEffect(() => {
    let active = true
    if (!snapshot || !entry?.editable) { setDraft(''); setOriginal(''); return }
    setFileLoading(true)
    repositories.bytes(snapshot, selected).then(response => response.text()).then(text => {
      if (active) { setDraft(text); setOriginal(text) }
    }).catch(e => { if (active) setError(String(e)) }).finally(() => { if (active) setFileLoading(false) })
    return () => { active = false }
  }, [snapshot, entry, selected])
  const act = async (operation: () => Promise<Snapshot>, success: string) => {
    setBusy(true)
    try { const tree = await operation(); setSnapshot(tree); setError(null); setHistory(await repositories.history(repositoryId, branch)); toast(success, 'success'); return true }
    catch (e) { toast(String(e), 'error'); return false }
    finally { setBusy(false) }
  }
  const upload = (files: FileList | null) => {
    if (!snapshot || !files?.length) return
    void act(() => repositories.upload(snapshot, Array.from(files), folder, message, fileType), 'Files committed to this repository.')
  }
  const download = async () => {
    if (!snapshot || !selected) return
    try {
      const response = await repositories.bytes(snapshot, selected)
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a'); link.href = url; link.download = selected.split('/').pop() || 'download'
      document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { toast(String(e), 'error') }
  }
  const remove = (item: TreeEntry) => {
    if (!snapshot || !confirm(`Delete ${item.path}${item.type === 'folder' ? ' and all its contents' : ''} from this branch? Earlier revisions remain available.`)) return
    void act(() => repositories.remove(snapshot, item.path, message), 'Deletion committed.').then(ok => { if (ok && selected === item.path) setSelected('') })
  }
  if (error) return <div className="page"><ErrorState message={error} retry={load} /></div>
  if (!snapshot) return <div className="page state-block">Loading repository…</div>
  const visible = snapshot.entries.filter(item => (item.path.includes('/') ? item.path.slice(0, item.path.lastIndexOf('/')) : '') === folder)
  return <div className="page">
    <div className="page-head"><div><button className="link small" onClick={() => navigate('/repositories')}>← All repositories</button><h1>{snapshot.name}</h1><p className="page-sub"><Hash hash={snapshot.commit_id} /> · {snapshot.entries.filter(item => item.type === 'file').length} files · {branch}</p></div>
      <button className="btn" onClick={load}>Refresh repository</button></div>
    {revision && <div className="notice">Viewing an earlier snapshot. Downloads use this exact revision. Select Latest to edit.</div>}
    <div className="panel repo-controls">
      <label>Branch<select aria-label="Repository branch" value={branch} onChange={e => navigate(`/repo/${repositoryId}?branch=${encodeURIComponent(e.target.value)}`)}>{snapshot.branches.map(item => <option key={item.name}>{item.name}</option>)}</select></label>
      <label>Revision<select aria-label="Repository revision" value={revision} onChange={e => navigate(`/repo/${repositoryId}?branch=${encodeURIComponent(branch)}${e.target.value ? `&commit=${e.target.value}` : ''}`)}><option value="">Latest</option>{history.map(commit => <option key={commit.commit_id} value={commit.commit_id}>{commit.commit_id.slice(0, 7)} · {commit.message}</option>)}</select></label>
      <form className="btn-row" onSubmit={event => { event.preventDefault(); void act(() => repositories.branch(snapshot, newBranch), 'Branch created.').then(ok => { if (ok) { navigate(`/repo/${repositoryId}?branch=${encodeURIComponent(newBranch)}`); setNewBranch('') } }) }}><label>New branch<input aria-label="New repository branch" value={newBranch} onChange={e => setNewBranch(e.target.value)} required /></label><button className="btn" disabled={busy || !newBranch.trim()}>Create branch</button></form>
    </div>
    {!revision && <div className="panel repo-controls"><label>Commit message<input aria-label="Repository commit message" value={message} onChange={e => setMessage(e.target.value)} required /></label>
      <label>Upload format<select aria-label="Upload format" value={fileType} onChange={e => setFileType(e.target.value)}><option value="auto">Auto (JSON/code as text)</option><option value="markdown">Markdown</option><option value="plaintext">Plain text</option><option value="chatgpt">ChatGPT export</option><option value="claude">Claude export</option><option value="pdf">PDF</option><option value="codebase">Codebase ZIP</option></select></label>
      <label>Upload to /{folder}<input aria-label="Upload repository files" type="file" multiple disabled={busy || !message.trim()} onChange={e => { upload(e.target.files); e.target.value = '' }} /></label>
      <form className="btn-row" onSubmit={event => { event.preventDefault(); const path = folder ? `${folder}/${folderName}` : folderName; void act(() => repositories.folder(snapshot, path, message), 'Folder committed.').then(ok => { if (ok) setFolderName('') }) }}><label>New folder<input aria-label="New folder name" value={folderName} onChange={e => setFolderName(e.target.value)} required /></label><button className="btn" disabled={busy || !folderName.trim() || !message.trim()}>Create folder</button></form>
    </div>}
    <div className="repo-layout"><section className="panel"><div className="panel-head"><button className="link" onClick={() => setFolder('')}>Root</button><span>/{folder}</span><span className="spacer" />{folder && <button className="btn sm" onClick={() => setFolder(folder.includes('/') ? folder.slice(0, folder.lastIndexOf('/')) : '')}>Parent folder</button>}</div>
      <div className="repo-file-list">{visible.map(item => <div className={`repo-file-row ${selected === item.path ? 'selected' : ''}`} key={item.path}><span>{item.type === 'folder' ? '▸' : '·'}</span><button className="link repo-path" onClick={() => item.type === 'folder' ? setFolder(item.path) : setSelected(item.path)}>{item.path.split('/').pop()}{item.type === 'folder' ? '/' : ''}</button><span className="faint small">{item.kind || 'folder'}</span><span className="spacer" />{!revision && <button className="btn sm" disabled={busy} onClick={() => remove(item)}>Delete</button>}</div>)}</div>
      {visible.length === 0 && <p className="state-block">This folder is empty. Add a nested folder or upload files.</p>}
    </section><section className="panel"><div className="panel-head">{selected || 'File preview'}<span className="spacer" />{entry && <button className="btn sm" onClick={download}>Download file</button>}</div>
      {!entry ? <p className="state-block">Select a file to view or edit its versioned contents.</p> : <div className="repo-preview">
        {entry.editable ? <>
          {!revision && <div className="btn-row"><button className="btn sm" onClick={() => setLive(null)}>File contents</button><button className="btn sm" disabled={busy} onClick={() => repositories.live(snapshot, selected).then(setLive).catch(error => toast(String(error), 'error'))}>Live collaboration</button></div>}
          {live ? <><LiveEditor artifactId={live.artifact_id} branch={live.branch} onCommitted={() => toast('Live version saved. Publish it to record this file in the repository snapshot.', 'info')} /><button className="btn primary" disabled={busy || !message.trim()} onClick={() => act(() => repositories.publish(snapshot, selected, message), 'Live file version published to the repository.')}>Publish live file version</button></> : <><textarea aria-label="Repository file contents" className="repo-editor mono" value={draft} onChange={e => setDraft(e.target.value)} disabled={busy || fileLoading || !!revision} spellCheck={false} />{!revision && <button className="btn primary" disabled={busy || fileLoading || draft === original || !message.trim()} onClick={() => act(() => repositories.edit(snapshot, selected, draft, message), 'File changes committed.')}>Commit file changes</button>}</>}
        </> : <p className="dim">{entry.kind} · {entry.size?.toLocaleString()} bytes. Download preserves the original file.</p>}
        {entry.artifacts?.map(reference => <p key={reference.artifact_id}><button className="link" onClick={() => navigate(`/art/${reference.artifact_id}?branch=${encodeURIComponent(reference.branch)}`)}>Open {reference.kind} artifact workspace →</button></p>)}
      </div>}
    </section></div>
    <section className="panel"><div className="panel-head">Commit history · {branch}</div>{history.map(commit => <div className="repo-file-row" key={commit.commit_id}><button className="link mono" onClick={() => navigate(`/repo/${repositoryId}?branch=${encodeURIComponent(branch)}&commit=${commit.commit_id}`)}>{commit.commit_id.slice(0, 7)}</button><span>{commit.message}</span><span className="spacer" /><span className="dim small">{commit.author}</span></div>)}</section>
  </div>
}
