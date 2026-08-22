import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import type { Change, CommitInfo, DiffResponse } from '../lib/types'
import { useApp } from '../state/store'
import { useRoute, navigate } from '../lib/router'
import { BranchSelector } from '../components/BranchSelector'
import {
  Badge,
  EmptyState,
  ErrorState,
  Hash,
  LoadingState,
  MockChip,
  Spinner,
  inlineHighlight,
  shortHash,
} from '../components/ui'

type ViewMode = 'unified' | 'split'

interface Stats {
  added: number
  deleted: number
  edited: number
  moved: number
  unchanged: number
}

function computeStats(changes: Change[]): Stats {
  const s: Stats = { added: 0, deleted: 0, edited: 0, moved: 0, unchanged: 0 }
  for (const c of changes) s[c.status]++
  return s
}

/** Unified row for one change. Marker gutter + prose body + sid column. */
function UnifiedRow({ c }: { c: Change }) {
  if (c.status === 'edited') {
    return (
      <div className="change-row row-edited">
        <div className="change-marker">~</div>
        <div className="change-body change-text">
          <del style={{ display: 'block' }}>{c.old_text}</del>
          <ins style={{ display: 'block', fontFamily: 'var(--serif)', fontSize: 13 }}>
            {inlineHighlight(c.old_text ?? '', c.new_text ?? '')}
          </ins>
        </div>
        <div className="change-sid">{c.sid}</div>
      </div>
    )
  }
  if (c.status === 'added') {
    return (
      <div className="change-row row-added">
        <div className="change-marker">+</div>
        <div className="change-body" style={{ fontFamily: 'var(--serif)', fontSize: 13 }}>{c.new_text}</div>
        <div className="change-sid">{c.sid}</div>
      </div>
    )
  }
  if (c.status === 'deleted') {
    return (
      <div className="change-row row-deleted">
        <div className="change-marker">&minus;</div>
        <div className="change-text change-body" style={{ fontFamily: 'var(--serif)', fontSize: 13 }}>{c.old_text}</div>
        <div className="change-sid">{c.sid}</div>
      </div>
    )
  }
  if (c.status === 'moved') {
    return (
      <div className="change-row row-moved">
        <div className="change-marker">&rarr;</div>
        <div className="change-body">
          {c.old_text}
          <span className="faint small" style={{ marginLeft: 8 }}>moved position, content unchanged</span>
        </div>
        <div className="change-sid">{c.sid}</div>
      </div>
    )
  }
  return (
    <div className="change-row row-unchanged">
      <div className="change-marker" />
      <div className="change-body" style={{ fontFamily: 'var(--serif)' }}>{c.old_text}</div>
      <div className="change-sid">{c.sid}</div>
    </div>
  )
}

export function DiffPage({ artifactId }: { artifactId: string }) {
  const route = useRoute()
  const { toast } = useApp()
  const branch = route.query.get('branch') ?? 'main'


  const [history, setHistory] = useState<CommitInfo[] | null>(null)
  const [diff, setDiff] = useState<DiffResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fromQ = route.query.get('from')
  const toQ = route.query.get('to')
  const [mode, setMode] = useState<ViewMode>('unified')

  // Default pair: head vs its first parent (the most recent change).
  useEffect(() => {
    let alive = true
    setHistory(null)
    api
      .history(artifactId, branch)
      .then((h) => alive && setHistory(h))
      .catch((e) => alive && setError(e.message))
    return () => {
      alive = false
    }
  }, [artifactId, branch])

  const defaultFrom = useMemo(() => {
    if (!history || history.length === 0) return null
    if (history.length >= 2) return history[1].commit_id
    return null
  }, [history])
  const defaultTo = history?.[0]?.commit_id ?? null

  useEffect(() => {
    const to = toQ ?? defaultTo
    const from = fromQ ?? defaultFrom
    if (!to || !from) {
      setLoading(false)
      return
    }
    let alive = true
    setLoading(true)
    setError(null)
    api
      .diff(artifactId, from, to)
      .then((d) => alive && setDiff(d))
      .catch((e) => {
        if (alive) {
          setError(e instanceof Error ? e.message : String(e))
          toast(`Diff failed: ${e instanceof Error ? e.message : e}`, 'error')
        }
      })
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [artifactId, fromQ, toQ, defaultFrom, defaultTo])

  const setParam = (k: string, v: string) => {
    const q = new URLSearchParams(route.query)
    q.set(k, v)
    navigate(`/art/${artifactId}/diff?${q.toString()}`)
  }

  const commitMeta = (cid?: string | null) =>
    history?.find((h) => h.commit_id === cid) ?? null

  const stats = diff ? computeStats(diff.changes) : null

  if (!history && !error) return <LoadingState label="Loading version graph…" />

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Semantic diff</h1>
          <p className="page-sub">
            Sentence-level alignment over research prose — not a byte or line diff.
          </p>
        </div>
        <div className="btn-row">
          {branch && <Badge variant="branch">{branch}</Badge>}
          <BranchSelector
            artifactId={artifactId}
            value={branch}
            onChange={(b) => setParam('branch', b)}
          />
        </div>
      </div>

      <div className="panel">
        <div className="diff-toolbar">
          <label className="small dim">from</label>
          <select
            className="select mono small"
            value={fromQ ?? defaultFrom ?? ''}
            onChange={(e) => setParam('from', e.target.value)}
          >
            {history?.slice(1).map((h) => (
              <option key={h.commit_id} value={h.commit_id}>
                {shortHash(h.commit_id)} · {h.message}
              </option>
            ))}
            {history && history.length > 0 && !defaultFrom && <option value="">root only</option>}
          </select>
          <span className="faint">→</span>
          <label className="small dim">to</label>
          <select
            className="select mono small"
            value={toQ ?? defaultTo ?? ''}
            onChange={(e) => setParam('to', e.target.value)}
          >
            {history?.map((h, i) => (
              <option key={h.commit_id} value={h.commit_id}>
                {i === 0 ? '(head) ' : ''}
                {shortHash(h.commit_id)} · {h.message}
              </option>
            ))}
          </select>

          <div style={{ flex: 1 }} />

          {stats && (
            <div className="diff-stats">
              <span className="add">+{stats.added}</span>
              <span className="del">−{stats.deleted}</span>
              <span className="mod">~{stats.edited}</span>
              {stats.moved > 0 && <span style={{ color: 'var(--violet)' }}>↦{stats.moved}</span>}
              <span className="ctx">{stats.unchanged} unchanged</span>
            </div>
          )}

          <div className="seg-toggle">
            <button className={mode === 'unified' ? 'active' : ''} onClick={() => setMode('unified')}>
              Unified
            </button>
            <button className={mode === 'split' ? 'active' : ''} onClick={() => setMode('split')}>
              Split
            </button>
          </div>
        </div>

        {/* commit metadata strip */}
        {(commitMeta(fromQ ?? defaultFrom) || commitMeta(toQ ?? defaultTo)) && (
          <div
            className="diff-toolbar"
            style={{ borderBottom: 'none', gap: 22, fontSize: 12, color: 'var(--fg-dim)' }}
          >
            {(['from', 'to'] as const).map((side) => {
              const meta = commitMeta(side === 'from' ? (fromQ ?? defaultFrom) : (toQ ?? defaultTo))
              if (!meta) return null
              return (
                <span key={side}>
                  <span className="mono faint">{side.toUpperCase()}</span>{' '}
                  <Hash hash={meta.commit_id} /> · {meta.message} ·{' '}
                  <span>{meta.author}</span>
                </span>
              )
            })}
          </div>
        )}

        {loading && (
          <div className="state-block">
            <Spinner />
            <p style={{ marginTop: 10 }}>Aligning sentences…</p>
          </div>
        )}

        {!loading && error && <ErrorState message={error} retry={() => setParam('to', toQ ?? defaultTo ?? '')} />}

        {!loading && !error && diff && (
          <>
            <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, alignItems: 'center' }}>
              {diff.viaMock !== true && <Badge variant="green">engine output</Badge>}
              {diff.viaMock === true && <MockChip />}
              <span className="faint small mono">kind={diff.kind}</span>
              <span className="faint small">
                {stats!.added + stats!.deleted + stats!.edited} semantic changes across{' '}
                {new Set(diff.changes.map((c) => c.sid.split(':').slice(0, 2).join(':'))).size} paragraphs
              </span>
            </div>

            {diff.changes.length === 0 && (
              <EmptyState icon="check" title="No differences" hint="These two versions are semantically identical." />
            )}

            {mode === 'unified' ? (
              <div>
                {diff.changes.map((c) => (
                  <UnifiedRow key={c.sid + c.status} c={c} />
                ))}
              </div>
            ) : (
              <SplitViewFixed changes={diff.changes} from={fromQ ?? defaultFrom ?? ''} to={toQ ?? defaultTo ?? ''} />
            )}
          </>
        )}

        {!loading && !error && !diff && defaultFrom === null && history && history.length <= 1 && (
          <EmptyState
            icon="diff"
            title="Nothing to diff yet"
            hint="This branch has a single commit — commit a change (or pick two commits) to see a sentence-level diff."
          />
        )}
      </div>
    </div>
  )
}

/** Split view with real labels. */
function SplitViewFixed({ changes, from, to }: { changes: Change[]; from: string; to: string }) {
  const rows = changes.filter((c) => c.status !== 'unchanged')
  return (
    <div className="split-grid">
      <div className="split-col">
        <div className="split-label">old · {shortHash(from)}</div>
        {rows.map((c, i) => (
          <div
            key={i}
            className={`split-cell ${c.old_text === undefined ? 'empty' : ''}`}
            style={
              c.status === 'deleted'
                ? { background: 'var(--red-bg)' }
                : c.status === 'edited'
                  ? { background: 'var(--amber-bg)' }
                  : undefined
            }
          >
            {c.old_text}
          </div>
        ))}
      </div>
      <div className="split-col">
        <div className="split-label">new · {shortHash(to)}</div>
        {rows.map((c, i) => (
          <div
            key={i}
            className={`split-cell ${c.new_text === undefined ? 'empty' : ''}`}
            style={
              c.status === 'added'
                ? { background: 'var(--green-bg)' }
                : c.status === 'edited'
                  ? { background: 'var(--amber-bg)' }
                  : undefined
            }
          >
            {c.status === 'edited' ? inlineHighlight(c.old_text ?? '', c.new_text ?? '') : c.new_text}
          </div>
        ))}
      </div>
    </div>
  )
}
