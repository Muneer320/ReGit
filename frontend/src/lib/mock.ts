// Demo fallback adapter — used ONLY where the backend engine is still a 501
// stub (merge-conflict persistence, resolve, retrieval) or unreachable.
//
// Honesty rules:
//  - Every fallback result is flagged `viaMock` and the UI says so.
//  - The fallback works on REAL data: branch contents come from /checkout,
//    the merge base comes from the real commit DAG, and a resolved merge is
//    committed as a REAL commit via POST /artifacts/:id/commit so it shows up
//    in the genuine history. Nothing here fakes the version graph.

import type { ArtifactRecord, MergeResponse, Resolution, ResolveResponse, SearchResult } from './types'
import { api, ApiError } from './api'
import { composeResolvedText, mergeProse } from './merge3'

export function registryList(): ArtifactRecord[] {
  try {
    return JSON.parse(localStorage.getItem('regit_artifacts') || '[]') as ArtifactRecord[]
  } catch {
    return []
  }
}

export function registerArtifacts(ids: string[], sourceFilename?: string) {
  const existing = new Map(registryList().map((r) => [r.id, r]))
  for (const id of ids) {
    existing.set(id, {
      ...existing.get(id),
      id,
      title: existing.get(id)?.title ?? '',
      kind: existing.get(id)?.kind ?? 'md',
      created_at: existing.get(id)?.created_at ?? new Date().toISOString(),
      source_filename: sourceFilename ?? existing.get(id)?.source_filename,
    })
  }
  localStorage.setItem(
    'regit_artifacts',
    JSON.stringify([...existing.values()].sort((a, b) => b.created_at.localeCompare(a.created_at))),
  )
}

// ---------------------------------------------------------------------------
// Pending merges (localStorage stand-in for the `merges`/`conflicts` tables)
// ---------------------------------------------------------------------------
interface PendingMerge {
  id: string
  artifact_id: string
  ours_branch: string
  theirs_branch: string
  base_commit: string
  ours_commit: string
  theirs_commit: string
  state: 'pending' | 'resolved'
  conflicts: { id: string; sid: string; base_text: string; ours_text: string; theirs_text: string }[]
  merged_text_with_markers: string
}

const MERGES_KEY = 'regit_pending_merges'

function loadMerges(): Record<string, PendingMerge> {
  try {
    return JSON.parse(localStorage.getItem(MERGES_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveMerges(m: Record<string, PendingMerge>) {
  localStorage.setItem(MERGES_KEY, JSON.stringify(m))
}

function rid(prefix: string): string {
  const rnd = crypto.getRandomValues(new Uint8Array(8))
  const hex = [...rnd].map((b) => b.toString(16).padStart(2, '0')).join('')
  return `${prefix}_${hex}`
}

// ---------------------------------------------------------------------------
// LCA from the real DAG (client-side approximation of store.merge_base)
// ---------------------------------------------------------------------------
async function mergeBaseFromDag(
  artifactId: string,
  oursBranch: string,
  theirsBranch: string,
): Promise<string | null> {
  const [oursHist, theirsHist] = await Promise.all([
    api.history(artifactId, oursBranch),
    api.history(artifactId, theirsBranch),
  ])
  const oursSet = new Set(oursHist.map((c) => c.commit_id))
  const common = theirsHist.filter((c) => oursSet.has(c.commit_id)).map((c) => c.commit_id)
  if (common.length === 0) return null
  // Deepest common ancestor = earliest in either newest-first walk among commons.
  const rank = new Map<string, number>()
  theirsHist.forEach((c, i) => rank.set(c.commit_id, i))
  oursHist.forEach((c, i) => {
    if (!rank.has(c.commit_id)) rank.set(c.commit_id, i + theirsHist.length)
  })
  return common.sort((a, b) => (rank.get(b) ?? 0) - (rank.get(a) ?? 0))[0] ?? null
}

// ---------------------------------------------------------------------------
// mockMerge — real branches -> real base via LCA -> local 3-way prose merge.
// Clean results are committed for real; conflicts persist as pending merges.
// ---------------------------------------------------------------------------
export async function mockMerge(
  artifactId: string,
  oursBranch: string,
  theirsBranch: string,
): Promise<MergeResponse> {
  const [oursHead, theirsHead] = await Promise.all([
    api.listBranches(artifactId).then((bs) => bs.find((b) => b.name === oursBranch)?.head_commit_id),
    api.listBranches(artifactId).then((bs) => bs.find((b) => b.name === theirsBranch)?.head_commit_id),
  ])
  if (!oursHead || !theirsHead) throw new ApiError(404, 'BRANCH_NOT_FOUND', 'unknown branch')

  if (oursHead === theirsHead) {
    return { merge_id: '', state: 'clean', conflicts: [], preview_text: '' }
  }

  const baseCommit =
    (await mergeBaseFromDag(artifactId, oursBranch, theirsBranch)) ??
    (await api.history(artifactId, oursBranch)).slice(-1)[0]?.commit_id

  const [baseC, oursC, theirsC] = await Promise.all([
    baseCommit
      ? api.checkout({ artifact_id: artifactId, commit: baseCommit })
      : Promise.resolve({ content: '', commit_id: '' }),
    api.checkout({ artifact_id: artifactId, commit: oursHead }),
    api.checkout({ artifact_id: artifactId, commit: theirsHead }),
  ])

  const result = mergeProse(baseC.content, oursC.content, theirsC.content)

  if (result.state === 'clean') {
    const commit = await api.commit(artifactId, {
      branch: oursBranch,
      content: result.mergedText,
      message: `merge ${theirsBranch} into ${oursBranch}`,
    })
    return {
      merge_id: '',
      state: 'clean',
      conflicts: [],
      preview_text: result.mergedText,
      result_commit_id: commit.commit_id,
      ours_branch: oursBranch,
      theirs_branch: theirsBranch,
      artifact_id: artifactId,
      viaMock: true,
    }
  }

  const id = rid('mrg')
  const pending: PendingMerge = {
    id,
    artifact_id: artifactId,
    ours_branch: oursBranch,
    theirs_branch: theirsBranch,
    base_commit: baseCommit ?? '',
    ours_commit: oursHead,
    theirs_commit: theirsHead,
    state: 'pending',
    conflicts: result.conflicts.map((c) => ({ id: c.sid, ...c })),
    merged_text_with_markers: result.mergedText,
  }
  const all = loadMerges()
  all[id] = pending
  saveMerges(all)

  return {
    merge_id: id,
    state: 'conflicts',
    conflicts: pending.conflicts,
    preview_text: result.mergedText,
    ours_branch: oursBranch,
    theirs_branch: theirsBranch,
    artifact_id: artifactId,
    viaMock: true,
  }
}

// ---------------------------------------------------------------------------
// mockResolve — compose final text and write a REAL commit onto ours_branch.
// ---------------------------------------------------------------------------
/** True when this merge id was issued locally (backend never saw it). */
export function mockHasMerge(mergeId: string): boolean {
  return Object.prototype.hasOwnProperty.call(loadMerges(), mergeId)
}

export async function mockResolve(
  mergeId: string,
  resolutions: Resolution[],
): Promise<ResolveResponse> {
  const m = loadMerges()[mergeId]
  if (!m) throw new ApiError(404, 'MERGE_NOT_FOUND', `unknown merge ${mergeId}`)
  if (m.state === 'resolved') throw new ApiError(409, 'ALREADY_RESOLVED', 'merge already resolved')

  const byId = new Map(resolutions.map((r) => [r.conflict_id, r]))
  const unresolved = m.conflicts.filter((c) => !byId.has(c.id))
  if (unresolved.length > 0) {
    throw new ApiError(400, 'UNRESOLVED_CONFLICTS', `conflicts without resolution: ${unresolved.map((c) => c.id).join(', ')}`)
  }

  const composed = composeResolvedText(
    m.merged_text_with_markers,
    resolutions.map((r) => ({
      conflict_id: r.conflict_id,
      resolved_text:
        r.resolution === 'ours'
          ? m.conflicts.find((c) => c.id === r.conflict_id)!.ours_text
          : r.resolution === 'theirs'
            ? m.conflicts.find((c) => c.id === r.conflict_id)!.theirs_text
            : (r.resolved_text ?? ''),
    })),
  )

  const commit = await api.commit(m.artifact_id, {
    branch: m.ours_branch,
    content: composed,
    message: `merge ${m.theirs_branch} into ${m.ours_branch} [resolved ${m.conflicts.length} conflict${m.conflicts.length === 1 ? '' : 's'}]`,
  })
  m.state = 'resolved'
  const all = loadMerges()
  all[mergeId] = m
  saveMerges(all)
  return { result_commit_id: commit.commit_id, viaMock: true }
}

// ---------------------------------------------------------------------------
// mockSearch — BM25-lite over REAL head contents of registered artifacts.
// Provenance fields come from the live backend (branch head = introduced_in).
// ---------------------------------------------------------------------------
const STOP = new Set(['the', 'a', 'an', 'of', 'in', 'on', 'and', 'or', 'to', 'is', 'are', 'with', 'for', 'at'])

function tokenize(s: string): string[] {
  return s
    .toLowerCase()
    .split(/[^a-z0-9^]+/)
    .filter((t) => t.length > 1 && !STOP.has(t))
}

export async function mockSearch(
  query: string,
  opts: { k?: number; branch?: string; as_of_commit?: string; artifact_kind?: string } = {},
): Promise<SearchResult[]> {
  const qTerms = tokenize(query)
  if (qTerms.length === 0) throw new ApiError(400, 'EMPTY_QUERY', 'query must be non-empty')
  const k = opts.k ?? 8

  const recs = registryList()
  type Chunk = { text: string; art: ArtifactRecord; branch: string; head: string }
  const chunks: Chunk[] = []

  await Promise.all(
    recs.map(async (rec) => {
      try {
        const arts = await api.listBranches(rec.id).catch(() => [])
        const allNames: string[] = arts.map((b) => b.name)
        const mains: string[] = allNames.filter((n) => n === 'main')
        const wanted: string[] = opts.branch ? [opts.branch] : mains.concat(allNames.filter((n) => n !== 'main'))
        for (const br of wanted.slice(0, opts.branch ? 1 : 2)) {
          const head = arts.find((b) => b.name === br)?.head_commit_id
          if (!head) continue
          const c = await api.checkout({ artifact_id: rec.id, branch: br })
          // Chunk per paragraph (md-style); keep paragraphs <= ~600 chars.
          for (const para of c.content.split(/\n\s*\n/)) {
            const t = para.replace(/^#+\s*/, '').trim()
            if (t.length < 24) continue
            for (let i = 0; i < t.length; i += 600) {
              const piece = t.slice(i, i + 600)
              chunks.push({ text: piece, art: rec, branch: br, head })
            }
          }
        }
      } catch {
        /* artifact unavailable — skip */
      }
    }),
  )

  // BM25-lite scoring.
  const df = new Map<string, number>()
  const chunkTokens = chunks.map((c) => tokenize(c.text))
  for (const toks of chunkTokens) {
    new Set(toks).forEach((t) => df.set(t, (df.get(t) ?? 0) + 1))
  }
  const N = Math.max(chunks.length, 1)
  const scored = chunks.map((c, idx) => {
    const tf = new Map<string, number>()
    chunkTokens[idx].forEach((t) => tf.set(t, (tf.get(t) ?? 0) + 1))
    let score = 0
    let matched = 0
    for (const term of qTerms) {
      const f = tf.get(term)
      if (f) {
        matched++
        const idf = Math.log(1 + N / (df.get(term) ?? 1))
        score += idf * (f / (f + 1.2))
      }
    }
    score *= 0.4 + 0.6 * (matched / qTerms.length)
    return { c, score }
  })

  return scored
    .filter((s) => s.score > 0.08)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map(({ c, score }) => ({
      chunk_id: `${c.art.id}:${c.branch}:${chunks.indexOf(c)}`,
      text: c.text,
      score: Math.min(0.99, score),
      artifact_id: c.art.id,
      artifact_title: c.art.title || c.art.source_filename || c.art.id,
      branch: c.branch,
      introduced_in_commit: c.head,
      sid_range: '',
      kind: c.art.kind,
      source: {
        type: c.art.kind === 'chat' ? 'chatgpt' : 'markdown',
        filename: c.art.source_filename ?? `${c.art.title || 'document'}.md`,
      },
      viaMock: true,
    }))
}
