import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Artifact } from '../lib/types'
import { navigate, useRoute } from '../lib/router'
import { useApp } from '../state/store'
import { seedDemoData } from '../lib/seed'
import { IngestDialog } from '../components/IngestDialog'
import { BranchBadge, EmptyState, ErrorState, KindBadge } from '../components/ui'
import { Icon } from '../components/Icon'

interface Row {
  artifact: Artifact
}

export function WorkspacePage() {
  const route = useRoute()
  const { toast } = useApp()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showIngest, setShowIngest] = useState(route.query.get('ingest') === '1')
  const [seeding, setSeeding] = useState(false)
  const [repoFilter, setRepoFilter] = useState('')

  const load = useCallback(async () => {
    setLoadError(null)
    try {
      const arts = await api.listArtifacts()
      const hydrated: Row[] = arts.map((artifact) => ({ artifact }))
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
  const filteredRows = rows?.filter(({ artifact }) => {
    const q = repoFilter.trim().toLowerCase()
    return !q || artifact.title.toLowerCase().includes(q) || artifact.id.toLowerCase().includes(q)
  })

  return (
    <div className="page">
      <div className="page-head">
        <div>
            <h1>Your repositories</h1>
            <p className="page-sub">
             Version-controlled research artifacts you own or have access to.
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
            icon="repo"
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
        <div className="repository-list">
          <section>
            <div className="dashboard-section-head">
              <div>
                <h2><Icon name="repo" size={14} /> {filteredRows?.length ?? 0} repositories</h2>
                <p className="faint small">Research artifacts you own or have access to.</p>
              </div>
              <div className="repo-filter-wrap">
                <Icon name="search" size={12} />
                <input className="input repo-filter" aria-label="Find a repository" placeholder="Find a repository…" value={repoFilter} onChange={(e) => setRepoFilter(e.target.value)} />
              </div>
            </div>
            <div className="panel">
              <div className="repository-card-grid">
                {filteredRows?.map(({ artifact: a }) => (
                  <article className="repository-card" key={a.id}>
                    <div className="repository-card-header">
                      <div className="repository-card-title"><Icon name="repo" size={16} /><h3>{a.title || a.id}</h3></div>
                      <span className="repo-visibility">Public</span>
                    </div>
                    <div className="repository-card-meta"><KindBadge kind={a.kind} /><span className="mono faint">{a.id}</span></div>
                    <p>{a.source_id ? `Source: ${a.source_id}` : 'Research artifact repository'}</p>
                    <div className="repository-card-branches">
                      <span className="microcaps">Branches</span>
                      {a.branches.length > 0 ? a.branches.slice(0, 3).map((b) => <BranchBadge key={b.name} name={b.name} />) : <span className="faint small">No branches</span>}
                      {a.branches.length > 3 && <span className="faint small">+{a.branches.length - 3} more</span>}
                    </div>
                    <button className="btn sm repository-open" onClick={() => navigate(`/art/${a.id}`)}>Open repository <Icon name="chevron-right" size={12} /></button>
                  </article>
                ))}
              </div>
               {filteredRows?.length === 0 && <div className="state-block">No repositories match “{repoFilter}”.</div>}
            </div>
          </section>
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
