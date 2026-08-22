import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Artifact, BranchRef } from '../lib/types'
import { useApp } from '../state/store'
import { useRoute, navigate } from '../lib/router'
import {
  Badge,
  ErrorState,
  Hash,
  KindBadge,
  LoadingState,
  Spinner,
  timeAgo,
} from '../components/ui'

export function ArtifactPage({ artifactId }: { artifactId: string }) {
  const route = useRoute()
  const { toast } = useApp()
  const branch = route.query.get('branch') ?? 'main'

  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const [branches, setBranches] = useState<BranchRef[]>([])
  const [content, setContent] = useState<string | null>(null)
  const [headCid, setHeadCid] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [message, setMessage] = useState('')
  const [committing, setCommitting] = useState(false)

  const [newBranchName, setNewBranchName] = useState('')
  const [creatingBranch, setCreatingBranch] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      const a = await api.getArtifact(artifactId)
      setArtifact(a)
      const bs = await api.listBranches(artifactId)
      setBranches(bs)
      const target = bs.find((b) => b.name === branch) ?? bs.find((b) => b.name === 'main') ?? bs[0]
      if (!target) return
      const co = await api.checkout({ artifact_id: artifactId, branch: target.name })
      setContent(co.content)
      setHeadCid(co.commit_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [artifactId, branch])

  useEffect(() => {
    load()
  }, [load])

  const startEdit = () => {
    setDraft(content ?? '')
    setEditing(true)
  }

  const commit = async () => {
    if (!message.trim()) {
      toast('A commit needs a message', 'error')
      return
    }
    setCommitting(true)
    try {
      const res = await api.commit(artifactId, {
        branch,
        content: draft,
        message: message.trim(),
        base_commit: headCid ?? undefined,
      })
      toast(`Committed ${res.commit_id.slice(0, 7)} to ${branch}`, 'success')
      setEditing(false)
      setMessage('')
      await load()
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      toast(`Commit failed: ${msg}`, 'error')
      // 409 STALE_BASE etc. — reload so the user sees the moved head.
      load()
    } finally {
      setCommitting(false)
    }
  }

  const createBranch = async () => {
    const name = newBranchName.trim()
    if (!name) return
    setCreatingBranch(true)
    try {
      await api.createBranch({ artifact_id: artifactId, name })
      toast(`Branch ${name} created at ${headCid?.slice(0, 7)}`, 'success')
      setNewBranchName('')
      await load()
    } catch (e) {
      toast(`Create branch failed: ${e instanceof Error ? e.message : String(e)}`, 'error')
    } finally {
      setCreatingBranch(false)
    }
  }

  if (error) {
    return (
      <div className="page">
        <div className="panel">
          <ErrorState message={error} retry={load} />
        </div>
      </div>
    )
  }
  if (!artifact || content === null) return <LoadingState label="Checking out working copy…" />

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {artifact.title}
            <KindBadge kind={artifact.kind} />
          </h1>
          <p className="page-sub mono small">
            {artifact.id}
            {artifact.source_id && <> · source {artifact.source_id}</>}
          </p>
        </div>
        <div className="btn-row">
           <Badge variant="branch">{branch}</Badge>
          {headCid && (
            <span className="small dim">
              @ <Hash hash={headCid} />
            </span>
          )}
          <button className="btn" onClick={() => navigate(`/art/${artifactId}/history?branch=${encodeURIComponent(branch)}`)}>
            History
          </button>
          <button className="btn" onClick={() => navigate(`/art/${artifactId}/diff?branch=${encodeURIComponent(branch)}`)}>
            Diff
          </button>
          <button className="btn primary" onClick={() => navigate(`/art/${artifactId}/merge?ours=${encodeURIComponent(branch)}`)}>
            Merge…
          </button>
        </div>
      </div>

      {/* branches */}
      <div className="panel">
        <div className="panel-head">Branches</div>
        <table className="artifact-table">
          <tbody>
            {branches.map((b) => (
              <tr key={b.name} onClick={() => navigate(`/art/${artifactId}?branch=${encodeURIComponent(b.name)}`)} style={{ cursor: 'pointer' }}>
                <td style={{ width: '30%' }}>
                  <Badge variant={b.name === branch ? 'blue' : 'branch'}>{b.name}</Badge>{' '}
                  {b.name === branch && <span className="faint small">current</span>}
                </td>
                <td className="mono small dim">head {b.head_commit_id.slice(0, 12)}</td>
                <td style={{ textAlign: 'right' }}>
                  <span
                    className="btn ghost sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/art/${artifactId}/history?branch=${encodeURIComponent(b.name)}`)
                    }}
                  >
                    history →
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="panel-body btn-row" style={{ borderTop: '1px solid var(--border)' }}>
          <input
            className="input mono"
            style={{ width: 220, fontSize: 12.5 }}
            placeholder="new-branch-name"
            value={newBranchName}
            onChange={(e) => setNewBranchName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && createBranch()}
          />
          <button className="btn" onClick={createBranch} disabled={!newBranchName.trim() || creatingBranch}>
            {creatingBranch ? <Spinner /> : '+ Create branch'}
          </button>
          <span className="faint small">forked from current head of {branch}</span>
        </div>
      </div>

      {/* content */}
      <div className="panel">
        <div className="panel-head">
          Working copy · {branch}
          <Hash hash={headCid ?? undefined} />
          <span className="spacer" />
          {!editing && (
            <button className="btn sm" onClick={startEdit}>
              Edit &amp; commit
            </button>
          )}
        </div>
        {!editing ? (
          <div className="panel-body">
            <pre className="content-preview">{content}</pre>
          </div>
        ) : (
          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <textarea
              className="code-editor"
              style={{ minHeight: 260 }}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
            <div className="btn-row">
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder={`commit message — e.g. revise divergence claim`}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && commit()}
              />
              <button className="btn primary" onClick={commit} disabled={committing || draft === content}>
                {committing ? (
                  <>
                    <Spinner /> Committing…
                  </>
                ) : (
                  `Commit to ${branch}`
                )}
              </button>
              <button className="btn" onClick={() => setEditing(false)} disabled={committing}>
                Cancel
              </button>
              {draft !== content && (
                <span className="badge amber">modified</span>
              )}
            </div>
            <span className="faint small">
              Content-addressed: identical text + same parent ⇒ same commit id (dedup, not noise).
            </span>
          </div>
        )}
      </div>

      {artifact.branches.length === 0 && branches.length > 0 && (
        <p className="faint small">Loaded {branches.length} branches for this artifact.</p>
      )}

      <p className="faint small" style={{ marginTop: 8 }}>
        Last refreshed {timeAgo(new Date().toISOString())}
      </p>
    </div>
  )
}
