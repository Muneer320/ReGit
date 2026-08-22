import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { CommitInfo } from '../lib/types'
import { useApp } from '../state/store'
import { useRoute, navigate } from '../lib/router'
import { BranchSelector } from '../components/BranchSelector'
import { Icon } from '../components/Icon'
import { Badge, EmptyState, ErrorState, Hash, LoadingState, shortHash, timeAgo } from '../components/ui'

/** One lane of the commit graph: vertical rail + node, drawn per row. */
function GraphRail({
  first,
  last,
  head,
  merge,
}: {
  first: boolean
  last: boolean
  head: boolean
  merge: boolean
}) {
  const lineTop = first ? 16 : 0
  return (
    <div className="commit-graph">
      {!last && <span className="graph-line" style={{ top: lineTop }} />}
      <span className={`graph-node ${head ? 'head' : ''} ${merge ? 'merge' : ''}`} title={head ? 'branch head' : merge ? 'merge commit' : undefined} />
      {merge && (
        <svg className="graph-branch-in" width="20" height="12" viewBox="0 0 20 12" aria-hidden>
          <path d="M19 1 C 12 1, 9 4, 6.5 7" fill="none" stroke="var(--border-strong)" strokeWidth="1.5" />
          <circle cx="19" cy="1" r="3" fill="var(--bg1)" stroke="var(--border-strong)" strokeWidth="1.5" />
        </svg>
      )}
    </div>
  )
}

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
          <BranchBadgeInline name={branch} />
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
          <EmptyState icon="commit" title="No commits on this branch" hint={`Branch "${branch}" has no head yet.`} />
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
                    <GraphRail first={i === 0} last={i === commits.length - 1} head={isHead} merge={isMerge} />
                    <div className="commit-main">
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                        <span className="commit-msg">{c.message}</span>
                        {isHead && <Badge variant="green">HEAD</Badge>}
                        {isMerge && <Badge variant="blue">merge · {c.parents.length} parents</Badge>}
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
                  <Icon name="x" size={11} /> close
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

function BranchBadgeInline({ name }: { name: string }) {
  return (
    <span className="badge branch">
      <Icon name="branch" size={10} />
      {name}
    </span>
  )
}
