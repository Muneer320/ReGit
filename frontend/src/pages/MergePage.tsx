import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import type { BranchRef, MergeResponse, Resolution, ResolveResponse } from '../lib/types'
import { useApp } from '../state/store'
import { navigate, useRoute } from '../lib/router'
import { ConflictCard } from '../components/ConflictCard'
import type { PendingResolution } from '../components/ConflictCard'
import { ConflictBanner, MergeSuccess, OursTheirsHeader } from '../components/MergePieces'
import { Badge, ErrorState, LoadingState, MockChip, Spinner } from '../components/ui'

type Phase = 'setup' | 'merging' | 'conflicts' | 'resolving' | 'done'

export function MergePage({ artifactId }: { artifactId: string }) {
  const route = useRoute()
  const { toast } = useApp()

  const [branches, setBranches] = useState<BranchRef[]>([])
  const [branchesError, setBranchesError] = useState<string | null>(null)
  const [ours, setOurs] = useState(route.query.get('ours') ?? 'main')
  const [theirs, setTheirs] = useState(route.query.get('theirs') ?? '')

  const [phase, setPhase] = useState<Phase>('setup')
  const [merge, setMerge] = useState<MergeResponse | null>(null)
  const [resolutions, setResolutions] = useState<Record<string, PendingResolution>>({})
  const [resolve, setResolve] = useState<ResolveResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  /** branch heads captured before the merge attempt (for "diff of merge") */
  const [preHeads, setPreHeads] = useState<{ ours: string; theirs: string }>({ ours: '', theirs: '' })

  useEffect(() => {
    let alive = true
    setBranchesError(null)
    api
      .listBranches(artifactId)
      .then((bs) => {
        if (!alive) return
        setBranches(bs)
        const names = bs.map((b) => b.name)
        if (!route.query.get('ours')) {
          setOurs(names.includes('main') ? 'main' : (names[0] ?? 'main'))
        }
        if (!theirs) {
          setTheirs(names.find((n) => n !== ours && n !== 'main') ?? names.find((n) => n !== ours) ?? '')
        }
      })
      .catch((e) => alive && setBranchesError(e instanceof Error ? e.message : String(e)))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [artifactId])

  const attemptMerge = useCallback(async () => {
    if (!ours || !theirs || ours === theirs) {
      toast('Pick two different branches', 'error')
      return
    }
    setPhase('merging')
    setError(null)
    try {
      const bs = await api.listBranches(artifactId)
      setPreHeads({
        ours: bs.find((b) => b.name === ours)?.head_commit_id ?? '',
        theirs: bs.find((b) => b.name === theirs)?.head_commit_id ?? '',
      })
      const res = await api.merge(artifactId, ours, theirs)
      setMerge(res)
      setResolutions({})
      setResolve(null)
      if (res.state === 'clean') {
        setPhase('done')
        toast(`Merge was clean — ${res.result_commit_id?.slice(0, 7)} created on ${ours}`, 'success')
      } else {
        setPhase('conflicts')
        toast(`${res.conflicts.length} conflict${res.conflicts.length === 1 ? '' : 's'} detected`, 'info')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setPhase('setup')
    }
  }, [artifactId, ours, theirs, toast])

  const unresolvedCount = useMemo(() => {
    if (!merge || merge.state !== 'conflicts') return 0
    return merge.conflicts.filter((c) => !resolutions[c.id]).length
  }, [merge, resolutions])

  const submitResolutions = useCallback(async () => {
    if (!merge || !merge.merge_id) return
    setPhase('resolving')
    setError(null)
    const payload: Resolution[] = merge.conflicts.map((c) => {
      const r = resolutions[c.id]!
      return {
        conflict_id: c.id,
        resolution: r.kind,
        resolved_text: r.text,
      }
    })
    try {
      const res = await api.resolveMerge(merge.merge_id, payload)
      setResolve(res)
      setPhase('done')
      toast(`Resolution committed — ${res.result_commit_id.slice(0, 7)}`, 'success')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setPhase('conflicts')
    }
  }, [merge, resolutions, toast])

  const goHistory = () => navigate(`/art/${artifactId}/history?branch=${encodeURIComponent(ours)}`)
  const goDiffOfMerge = () =>
    navigate(
      `/art/${artifactId}/diff?branch=${encodeURIComponent(ours)}&from=${encodeURIComponent(
        preHeads.ours,
      )}&to=${encodeURIComponent(resolve?.result_commit_id ?? merge?.result_commit_id ?? '')}`,
    )

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Merge</h1>
          <p className="page-sub">
            Sentence-level three-way merge. Incompatible edits surface as conflicts — the engine never guesses.
          </p>
        </div>
        {merge?.viaMock && <MockChip />}
      </div>

      {/* ---- setup ---- */}
      {(phase === 'setup' || phase === 'merging') && (
        <>
          {branchesError && (
            <div className="panel" style={{ marginBottom: 14 }}>
              <ErrorState message={branchesError} retry={() => window.location.reload()} />
            </div>
          )}
          <OursTheirsHeader ours={ours} theirs={theirs}>
            <div className="panel">
              <div className="panel-head">
                Merge setup
                <span className="spacer" />
                {phase === 'merging' && (
                  <span className="small dim" style={{ display: 'flex', gap: 6 }}>
                    <Spinner /> running 3-way alignment…
                  </span>
                )}
              </div>
              <div className="panel-body" style={{ display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div className="field" style={{ width: 220 }}>
                  <label>Ours (target)</label>
                  <select className="select mono" value={ours} onChange={(e) => setOurs(e.target.value)}>
                    {branches.map((b) => (
                      <option key={b.name} value={b.name}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field" style={{ width: 220 }}>
                  <label>Theirs (incoming)</label>
                  <select className="select mono" value={theirs} onChange={(e) => setTheirs(e.target.value)}>
                    <option value="">— pick branch —</option>
                    {branches.map((b) => (
                      <option key={b.name} value={b.name}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  className="btn primary"
                  onClick={attemptMerge}
                  disabled={!theirs || phase === 'merging'}
                  style={{ height: 32 }}
                >
                  ⑃ Attempt merge
                </button>
              </div>
            </div>
          </OursTheirsHeader>
        </>
      )}

      {error && (
        <div className="panel" style={{ marginBottom: 14 }}>
          <ErrorState message={error} retry={phase === 'resolving' ? undefined : attemptMerge} />
        </div>
      )}

      {/* ---- clean success / resolved success ---- */}
      {phase === 'done' && merge && (
        <>
          <MergeSuccess merge={{ ...merge, ours_branch: ours, theirs_branch: theirs }} resolve={resolve ?? undefined} onViewHistory={goHistory} onViewDiff={goDiffOfMerge} />
          {merge.preview_text && !resolve && (
            <div className="panel">
              <div className="panel-head">Merged result</div>
              <div className="panel-body">
                <pre className="content-preview" style={{ margin: 0 }}>{merge.preview_text}</pre>
              </div>
            </div>
          )}
        </>
      )}

      {/* ---- conflicts ---- */}
      {(phase === 'conflicts' || phase === 'resolving') && merge && merge.state === 'conflicts' && (
        <>
          <ConflictBanner count={merge.conflicts.length} />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 12, marginBottom: 14 }}>
            <div className="ot-card ours" style={{ padding: '8px 14px' }}>
              <span className="ot-label" style={{ display: 'inline' }}>OURS</span>{' '}
              <span className="ot-branch" style={{ fontSize: 12.5 }}>{ours}</span>
            </div>
            <span className="ot-arrow small">vs</span>
            <div className="ot-card theirs" style={{ padding: '8px 14px', textAlign: 'right' }}>
              <span className="ot-label" style={{ display: 'inline' }}>THEIRS</span>{' '}
              <span className="ot-branch" style={{ fontSize: 12.5 }}>{theirs}</span>
            </div>
          </div>

          {merge.viaMock && (
            <p className="small faint" style={{ margin: '0 2px 10px' }}>
              Backend conflict persistence is still a stub — this scene is computed by the local demo adapter over the real DAG and commits through the live API.
            </p>
          )}

          {merge.conflicts.map((c) => (
            <ConflictCard
              key={c.id}
              conflict={c}
              oursBranch={ours}
              theirsBranch={theirs}
              value={resolutions[c.id]}
              onChange={(r) => setResolutions((prev) => ({ ...prev, [c.id]: r as PendingResolution }))}
              disabled={phase === 'resolving'}
            />
          ))}

          <div className="panel" style={{ marginTop: 16 }}>
            <div className="panel-body btn-row" style={{ justifyContent: 'space-between' }}>
              <span className="small dim">
                {unresolvedCount === 0 ? (
                  <>All conflicts resolved — ready to write the merge commit.</>
                ) : (
                  <>
                    <Badge variant="amber">{unresolvedCount}</Badge> remaining
                  </>
                )}
              </span>
              <div className="btn-row">
                <button
                  className="btn"
                  onClick={() => {
                    setMerge(null)
                    setPhase('setup')
                    setError(null)
                  }}
                  disabled={phase === 'resolving'}
                >
                  Abort merge
                </button>
                <button className="btn success" onClick={submitResolutions} disabled={unresolvedCount > 0 || phase === 'resolving'}>
                  {phase === 'resolving' ? (
                    <>
                      <Spinner /> Committing resolution…
                    </>
                  ) : (
                    `Commit merge (${merge.conflicts.length} resolution${merge.conflicts.length === 1 ? '' : 's'})`
                  )}
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {phase === 'setup' && !branchesError && branches.length <= 1 && (
        <div className="demo-hint" style={{ marginTop: 14 }}>
          <span>ⓘ</span>
          <span>
            Merging needs two branches. Create one via History → create branch, or load demo data from the Workspace.
          </span>
        </div>
      )}

      {phase === 'merging' && <LoadingState label="" />}
    </div>
  )
}
