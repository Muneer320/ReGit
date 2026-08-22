import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { CommitInfo } from '../lib/types'
import { useApp } from '../state/store'
import { useRoute, navigate } from '../lib/router'
import { BranchSelector } from '../components/BranchSelector'
import { Badge, EmptyState, ErrorState, Hash, LoadingState, shortHash, timeAgo } from '../components/ui'

export function HistoryPage({ artifactId }: { artifactId: string }) {
  const route = useRoute()
  const branch = route.query.get('branch') ?? 'main'
  const { toast } = useApp()
  const [commits, setCommits] = useState<CommitInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [checkingOut, setCheckingOut] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ cid: string; content: string } | null>(null)

  const load = useCallback(async () => {
    setError(null)
    setCommits(null)
    try {
      const h = await api.history(artifactId, branch)
      setCommits(h)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [artifactId, branch])

  useEffect(() => {
    load()
  }, [load])

  const checkout = async (cid: string) => {
    setCheckingOut(cid)
    try {
      const res = await api.checkout({ artifact_id: artifactId, commit: cid })
      setPreview({ cid, content: res.content })
      toast(`Checked out ${shortHash(cid)} (read-only view)`, 'success')
    } catch (e) {
      toast(`Checkout failed: ${e instanceof Error ? e.message : String(e)}`, 'error')
    } finally {
      setCheckingOut(null)
    }
  }

  const diffFrom = (cid: string) => {
    // Diff this commit against its first parent when it has one.
    const idx = commits?.findIndex((c) => c.commit_id === cid) ?? -1
    if (idx >= 0 && commits && idx + 1 < commits.length) {
      navigate(`/art/${artifactId}/diff?branch=${encodeURIComponent(branch)}&from=${commits[idx + 1].commit_id}&to=${cid}`)
    } else {
      toast('Root commit has no parent to diff against', 'info')
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>History</h1>
          <p className="page-sub">The evolution of this artifact — newest first, straight off the DAG.</p>
        </div>
        <div className="btn-row">
          <Badge variant="branch">⌥ {branch}</Badge>
          <BranchSelector artifactId={artifactId} value={branch} onChange={(b) => navigate(`/art/${artifactId}/history?branch=${encodeURIComponent(b)}`)} />
        </div>
      </div>

      {error && (
        <div className="panel">
          <ErrorState message={error} retry={load} />
        </div>
      )}
      {!error && !commits && <LoadingState label="Walking the DAG…" />}
      {!error && commits && commits.length === 0 && (
        <div className="panel">
          <EmptyState icon="⌥" title="No commits on this branch" hint={`Branch "${branch}" has no head yet.`} />
        </div>
      )}

      {!error && commits && commits.length > 0 && (
        <>
          <div className="panel">
            <div className="timeline">
              {commits.map((c, i) => {
                const isHead = i === 0
                const isMerge = c.parents.length >= 2
                return (
                  <div className="commit-item" key={c.commit_id}>
                    <div className="commit-rail">
                      <span
                        className={`commit-dot ${isHead ? 'head' : ''} ${isMerge ? 'merge' : ''}`}
                        title={isHead ? 'branch head' : isMerge ? 'merge commit (2 parents)' : undefined}
                      />
                      {i < commits.length - 1 && <span className="commit-line" />}
                    </div>
                    <div className="commit-main">
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                        <span className="commit-msg">{c.message}</span>
                        {isHead && <Badge variant="green">head</Badge>}
                        {isMerge && <Badge variant="blue">merge · 2 parents</Badge>}
                      </div>
                      <div className="commit-meta">
                        <Hash hash={c.commit_id} />
                        <span>·</span>
                        <span>{c.author}</span>
                        <span>·</span>
                        <span title={c.author_date}>{timeAgo(c.author_date)}</span>
                        {c.parents.length > 0 && (
                          <span className="commit-parents">
                            parents: {c.parents.map((p) => shortHash(p)).join(', ')}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="checkout-btns btn-row">
                      <button className="btn sm" onClick={() => diffFrom(c.commit_id)} disabled={c.parents.length === 0}>
                        View diff
                      </button>
                      <button
                        className="btn sm"
                        onClick={() => checkout(c.commit_id)}
                        disabled={checkingOut !== null}
                      >
                        {checkingOut === c.commit_id ? '…' : 'Checkout'}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {preview && (
            <div className="panel">
              <div className="panel-head">
                Checked-out snapshot <Hash hash={preview.cid} />
                <span className="spacer" />
                <button className="btn ghost sm" onClick={() => setPreview(null)}>
                  ✕ close
                </button>
              </div>
              <div className="panel-body">
                <pre className="content-preview" style={{ margin: 0 }}>{preview.content}</pre>
              </div>
            </div>
          )}

          <p className="faint small" style={{ marginTop: 10 }}>
            Checkout is read-only per the contract — it never moves refs. Merge commits link two parents.
          </p>
        </>
      )}
    </div>
  )
}
