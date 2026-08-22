import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Artifact } from '../lib/types'
import { navigate } from '../lib/router'
import { useApp } from '../state/store'
import { seedDemoData } from '../lib/seed'
import { IngestDialog } from '../components/IngestDialog'
import { BranchBadge, EmptyState, ErrorState, Hash, KindBadge, timeAgo } from '../components/ui'

interface Row {
  artifact: Artifact
  head?: { message: string; author: string; author_date: string; commit_id: string }
  error?: boolean
}

export function WorkspacePage() {
  const { toast } = useApp()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showIngest, setShowIngest] = useState(false)
  const [seeding, setSeeding] = useState(false)

  const load = useCallback(async () => {
    setLoadError(null)
    try {
      const arts = await api.listArtifacts()
      const hydrated = await Promise.all<Row>(
        arts.map(async (a) => {
          const main = a.branches.find((b) => b.name === 'main') ?? a.branches[0]
          if (!main) return { artifact: a }
          try {
            const hist = await api.history(a.id, main.name)
            return {
              artifact: a,
              head: hist[0]
                ? {
                    message: hist[0].message,
                    author: hist[0].author,
                    author_date: hist[0].author_date,
                    commit_id: hist[0].commit_id,
                  }
                : undefined,
            }
          } catch {
            return { artifact: a, error: true }
          }
        }),
      )
      setRows(hydrated)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e))
      setRows([])
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const seed = async () => {
    setSeeding(true)
    try {
      const r = await seedDemoData()
      toast('Demo research workspace created — merge scene ready in lr-stability.md', 'success')
      await load()
      void r
    } catch (e) {
      toast(`Seeding failed: ${e instanceof Error ? e.message : String(e)}`, 'error')
    } finally {
      setSeeding(false)
    }
  }

  const empty = rows !== null && rows.length === 0 && !loadError

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Workspace</h1>
          <p className="page-sub">
            Version-controlled research artifacts — every edit becomes an immutable, content-addressed commit.
          </p>
        </div>
        <div className="btn-row">
          {seeding && (
            <button className="btn" disabled>
              Seeding…
            </button>
          )}
          {!empty && (
            <button className="btn" onClick={seed} disabled={seeding} title="Create the scripted demo scenario via the live API">
              Load demo data
            </button>
          )}
          <button className="btn primary" onClick={() => setShowIngest(true)}>
            + Ingest source
          </button>
        </div>
      </div>

      {empty && (
        <div className="panel">
          <EmptyState
            icon="⬡"
            title="No artifacts yet"
            hint="Ingest a markdown file, chat export, or PDF — or load the scripted demo data to explore diffs, branches and merges."
            action={
              <div className="btn-row" style={{ justifyContent: 'center' }}>
                <button className="btn primary" onClick={() => setShowIngest(true)}>
                  Ingest a source
                </button>
                <button className="btn" onClick={seed}>
                  Load demo data
                </button>
              </div>
            }
          />
        </div>
      )}

      {loadError && (
        <div className="panel">
          <ErrorState message={loadError} retry={load} />
          <p className="faint small" style={{ textAlign: 'center', paddingBottom: 14 }}>
            Start the backend with <code className="mono">uvicorn backend.src.api.main:app --port 8377</code>
          </p>
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="panel">
          <table className="artifact-table">
            <thead>
              <tr>
                <th style={{ width: '34%' }}>Artifact</th>
                <th>Type</th>
                <th>Branches</th>
                <th style={{ width: '30%' }}>Latest commit</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map(({ artifact: a, head }) => (
                <tr key={a.id} onClick={() => navigate(`/art/${a.id}`)}>
                  <td>
                    <span className="title-cell">{a.title || a.id}</span>
                    <div className="mono faint small">{a.id}</div>
                  </td>
                  <td>
                    <KindBadge kind={a.kind} />
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                      {(a.branches.length ? a.branches : [{ name: '—', head: '' }]).slice(0, 3).map((b) => (
                        <BranchBadge key={b.name} name={b.name} />
                      ))}
                      {a.branches.length === 0 && <span className="faint small">none</span>}
                    </div>
                  </td>
                  <td>
                    {head ? (
                      <>
                        <div style={{ color: 'var(--fg)' }}>{head.message}</div>
                        <div className="small faint mono">
                          {head.author} · {timeAgo(head.author_date)} · <Hash hash={head.commit_id} />
                        </div>
                      </>
                    ) : (
                      <span className="faint">no commits</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <span className="btn ghost sm">Open →</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows && rows.length > 0 && (
        <p className="faint small" style={{ marginTop: 10 }}>
          Tip: open an artifact to browse its version graph, sentence-level diffs and merges.
        </p>
      )}

      {showIngest && <IngestDialog onClose={() => setShowIngest(false)} onIngested={load} />}
    </div>
  )
}
