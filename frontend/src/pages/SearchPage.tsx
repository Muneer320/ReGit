import { useCallback, useEffect, useRef, useState } from 'react'
import { api, registryLoad } from '../lib/api'
import type { ArtifactRecord, SearchResult } from '../lib/types'
import { navigate, useRoute } from '../lib/router'
import {
  Badge,
  EmptyState,
  ErrorState,
  Hash,
  KindBadge,
  LoadingState,
  MockChip,
  Spinner,
  timeAgo,
} from '../components/ui'

function highlight(text: string, terms: string[]) {
  const clean = terms.filter((t) => t.length > 0)
  if (clean.length === 0) return text
  const escaped = clean.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const re = new RegExp(`(${escaped.join('|')})`, 'gi')
  const testRe = new RegExp(`^(?:${escaped.join('|')})$`, 'i')
  return text.split(re).map((p, i) => (testRe.test(p) ? <mark key={i}>{p}</mark> : p))
}

export function SearchPage() {
  const route = useRoute()
  const initialQ = route.query.get('q') ?? ''

  const [query, setQuery] = useState(initialQ)
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastQuery, setLastQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // Suggested queries derived from what's actually in the corpus.
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([])
  useEffect(() => setArtifacts(registryLoad()), [])

  useEffect(() => {
    if (initialQ) run(initialQ)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQ])

  const run = useCallback(
    async (q: string) => {
      const trimmed = q.trim()
      if (!trimmed) return
      setSearching(true)
      setError(null)
      setLastQuery(trimmed)
      try {
        const r = await api.search(trimmed, { k: 8 })
        setResults(r)
        navigate(`/search?q=${encodeURIComponent(trimmed)}`)
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
        setResults(null)
      } finally {
        setSearching(false)
      }
    },
    [],
  )

  const anyMock = results?.some((r) => r.viaMock) ?? false

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Search research history</h1>
          <p className="page-sub">
            Every hit carries its provenance — artifact, branch, introducing commit, source file. Not a website search box.
          </p>
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          run(query)
        }}
      >
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <span
              className="mono faint"
              style={{ position: 'absolute', left: 14, top: 12, fontSize: 13 }}
            >
              ⌕
            </span>
            <input
              ref={inputRef}
              className="input search-input"
              style={{ paddingLeft: 34 }}
              placeholder="query the corpus — e.g. gradient descent instability"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>
          <button className="btn primary" type="submit" disabled={searching || !query.trim()} style={{ height: 38 }}>
            {searching ? (
              <>
                <Spinner /> Searching
              </>
            ) : (
              'Search'
            )}
          </button>
        </div>
      </form>

      <div className="btn-row" style={{ margin: '10px 0 4px' }}>
        <span className="faint small">try:</span>
        {['gradient descent instability', 'learning rate divergence', 'surface code logical error'].map((s) => (
          <button
            key={s}
            className="btn ghost sm mono"
            onClick={() => {
              setQuery(s)
              run(s)
            }}
          >
            “{s}”
          </button>
        ))}
        {artifacts.length > 0 && (
          <span className="faint small" style={{ marginLeft: 'auto' }}>
            corpus: {artifacts.length} artifact{artifacts.length === 1 ? '' : 's'} ·{' '}
            {timeAgo(artifacts[0].created_at)}
          </span>
        )}
      </div>

      {error && (
        <div className="panel" style={{ marginTop: 12 }}>
          <ErrorState message={error} retry={() => run(lastQuery)} />
        </div>
      )}

      {!error && searching && !results && (
        <div className="panel" style={{ marginTop: 12 }}>
          <LoadingState label="Scanning versions…" />
        </div>
      )}

      {!error && results && results.length === 0 && !searching && (
        <div className="panel" style={{ marginTop: 12 }}>
          <EmptyState icon="⌕" title={`No results for “${lastQuery}”`} hint="Try broader terms — the corpus only contains ingested artifacts." />
        </div>
      )}

      {!error && results && results.length > 0 && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '16px 0 10px' }}>
            <h2>
              {results.length} result{results.length === 1 ? '' : 's'}
            </h2>
            <span className="faint small">for “{lastQuery}”, ranked by relevance</span>
            {anyMock && <MockChip />}
          </div>

          {results.map((r) => (
            <article className="result-card" key={r.chunk_id}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
                <KindBadge kind={r.kind} />
                <b
                  style={{ color: 'var(--heading)', cursor: 'pointer' }}
                  onClick={() => navigate(`/art/${r.artifact_id}`)}
                  title="open artifact"
                >
                  {r.artifact_title}
                </b>
                <Badge variant="branch">⌥ {r.branch}</Badge>
                <span style={{ marginLeft: 'auto' }} className="result-score">
                  {(r.score * 100).toFixed(0)}% match
                </span>
              </div>

              <blockquote className="result-excerpt">
                “{highlight(r.text, lastQuery.trim().toLowerCase().split(/\s+/))}”
              </blockquote>

              <footer className="citation-line">
                <span>
                  <span className="ck">source</span> {r.source?.filename ?? '—'}
                  {r.source?.type ? ` (${r.source.type})` : ''}
                </span>
                <span
                  style={{ cursor: 'pointer' }}
                  title="commit that introduced this content — click to inspect"
                  onClick={() => navigate(`/art/${r.artifact_id}/history?branch=${encodeURIComponent(r.branch)}`)}
                >
                  <span className="ck">introduced in</span> <Hash hash={r.introduced_in_commit} n={12} />
                </span>
                <span>
                  <span className="ck">artifact</span>{' '}
                  <a
                    onClick={(e) => {
                      e.preventDefault()
                      navigate(`/art/${r.artifact_id}`)
                    }}
                    href="#"
                  >
                    {r.artifact_id.slice(0, 18)}…
                  </a>
                </span>
                {r.sid_range && (
                  <span>
                    <span className="ck">sid</span> {r.sid_range}
                  </span>
                )}
              </footer>
            </article>
          ))}
        </>
      )}

      {!results && !error && !searching && (
        <div className="demo-hint" style={{ marginTop: 14 }}>
          <span>ⓘ</span>
          <span>
            Search runs against the retrieval engine when available; otherwise a local index over your real artifacts keeps the demo honest (marked “demo adapter”).
          </span>
        </div>
      )}
    </div>
  )
}
