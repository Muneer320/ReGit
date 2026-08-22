import type { ReactNode } from 'react'
import type { MergeResponse, ResolveResponse } from '../lib/types'
import { Icon } from './Icon'

/** Strong completion state — the judge must SEE that the merge committed. */
export function MergeSuccess({
  merge,
  resolve,
  onViewHistory,
  onViewDiff,
}: {
  merge: MergeResponse
  resolve?: ResolveResponse
  onViewHistory: () => void
  onViewDiff: () => void
}) {
  const commitId = resolve?.result_commit_id ?? merge.result_commit_id
  const ours = merge.ours_branch ?? 'ours'
  const theirs = merge.theirs_branch ?? 'theirs'

  return (
    <div className="merge-success">
       <span className="check"><Icon name="check" size={20} /></span>
      <h2>Merge completed</h2>
      <p className="flow">
        {theirs} → {ours}
      </p>
      {commitId ? (
        <div className="merge-commit-box">
          <span className="label">Commit</span>
          <span className="cid">{commitId.slice(0, 12)}</span>
          <span className="small dim">
            “merge {theirs} into {ours}”
          </span>
          {resolve?.viaMock && (
            <span className="small faint">
              resolution committed via demo adapter (2-parent persistence pending on backend)
            </span>
          )}
        </div>
      ) : (
        <p className="dim small" style={{ marginTop: 8 }}>
          No result commit id returned.
        </p>
      )}
      <div className="btn-row" style={{ justifyContent: 'center', marginTop: 16 }}>
        <button className="btn primary" onClick={onViewHistory}>
          View history
        </button>
        {commitId && (
          <button className="btn" onClick={onViewDiff} disabled={!commitId}>
            View diff of merge
          </button>
        )}
      </div>
    </div>
  )
}

/** OURS/THEIRS branch header before attempting a merge. */
export function OursTheirsHeader({
  ours,
  theirs,
  children,
}: {
  ours: string
  theirs: string
  children?: ReactNode
}) {
  return (
    <>
      <div className="ours-theirs-header">
        <div className="ot-card ours">
          <div className="ot-label">Ours</div>
          <div className="ot-branch">{ours}</div>
          <div className="small faint mono">current branch · kept on conflict “accept ours”</div>
        </div>
         <div className="ot-arrow"><Icon name="merge" size={15} /> merge</div>
        <div className="ot-card theirs">
          <div className="ot-label">Theirs</div>
          <div className="ot-branch">{theirs}</div>
          <div className="small faint mono">incoming branch · kept on “accept theirs”</div>
        </div>
      </div>
      {children}
    </>
  )
}

export function ConflictBanner({ count }: { count: number }) {
  return (
    <div className="conflict-banner">
       <Icon name="merge" size={19} />
      <span className="count">{count}</span>
      <span>
        conflict{count === 1 ? '' : 's'} detected
        <span className="dim" style={{ display: 'block', fontSize: 12 }}>
          The engine refuses to guess. Resolve each card below — nothing is discarded silently.
        </span>
      </span>
    </div>
  )
}
