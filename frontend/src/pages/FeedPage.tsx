import { useCallback, useEffect, useState } from 'react'
import { repositories } from '../lib/repositories'
import type { Activity } from '../lib/repositories'
import { navigate } from '../lib/router'
import { ErrorState, Hash, timeAgo } from '../components/ui'

export function FeedPage() {
  const [rows, setRows] = useState<Activity[]>([])
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    try { setError(null); setRows(await repositories.activity()) } catch (e) { setError(String(e)) }
  }, [])
  useEffect(() => { void load() }, [load])
  return <div className="page"><div className="page-head"><div><h1>Workspace activity</h1><p className="page-sub">Recent commits from the current local store.</p></div><button className="btn" onClick={load}>Refresh activity</button></div>
    {error && <ErrorState message={error} retry={load} />}
    <div className="panel">{rows.map(row => <div className="repo-file-row" key={row.commit_id}><Hash hash={row.commit_id} /><div><strong>{row.message}</strong><p className="dim small">{row.title} · {row.author} · {timeAgo(row.author_date)}</p></div><span className="spacer" /><button className="btn sm" onClick={() => navigate(row.kind === 'repository' ? `/repo/${row.artifact_id}` : `/art/${row.artifact_id}/history`)}>View history</button></div>)}
    {!error && rows.length === 0 && <p className="state-block">No commits yet. Create a repository or import a research source.</p>}</div></div>
}
