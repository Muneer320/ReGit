// Local prose diff fallback — mirrors backend align.diff_prose output
// ({sid, status, old_text?, new_text?, similarity}) so DiffViewer renders
// identically whether data came from the engine or this adapter.

const SENT_SPLIT = /(?<=[.!?])\s+(?=[A-Z0-9"'(])/

type Sent = { para: number; sent: number; text: string }

function splitParagraphs(text: string): string[] {
  return text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean)
}

function flatten(text: string): Sent[] {
  const out: Sent[] = []
  splitParagraphs(text).forEach((p, pi) =>
    p.split(SENT_SPLIT).map((s) => s.trim()).filter(Boolean).forEach((s, si) => out.push({ para: pi, sent: si, text: s })),
  )
  return out
}

const normalize = (s: string) =>
  s.toLowerCase().replace(/[^\w\s]/g, '').replace(/\s+/g, ' ').trim()

function bigramRatio(a: string, b: string): number {
  if (a === b) return 1
  const grams = (s: string) => {
    const set = new Set<string>()
    for (let i = 0; i < s.length - 1; i++) set.add(s.slice(i, i + 2))
    return set
  }
  const ga = grams(a)
  const gb = grams(b)
  let inter = 0
  ga.forEach((g) => {
    if (gb.has(g)) inter++
  })
  return (2 * inter) / ((ga.size + gb.size) || 1)
}

interface Op { type: 'equal' | 'edit' | 'delete' | 'insert'; old?: number; new?: number; sim?: number }

function align(oldF: Sent[], newF: Sent[]): Op[] {
  const oh = oldF.map((s) => normalize(s.text))
  const nh = newF.map((s) => normalize(s.text))
  const n = oh.length
  const m = nh.length
  if (n === 0 && m === 0) return []
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = 1; i <= n; i++)
    for (let j = 1; j <= m; j++)
      dp[i][j] = oh[i - 1] === nh[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])

  type Raw = { type: 'equal' | 'delete' | 'insert'; o?: number; j?: number }
  const raw: Raw[] = []
  let i = n
  let j = m
  while (i > 0 && j > 0) {
    if (oh[i - 1] === nh[j - 1]) {
      raw.push({ type: 'equal', o: i - 1, j: j - 1 })
      i--
      j--
    } else if (dp[i - 1][j] >= dp[i][j - 1]) raw.push({ type: 'delete', o: --i })
    else raw.push({ type: 'insert', j: --j })
  }
  while (i > 0) raw.push({ type: 'delete', o: --i })
  while (j > 0) raw.push({ type: 'insert', j: --j })
  raw.reverse()

  // Pair delete/insert runs into edits when similar enough.
  const ops: Op[] = []
  let dels: number[] = []
  let ins: number[] = []
  const flush = () => {
    const used = new Set<number>()
    const pairs = new Map<number, [number, number]>()
    for (const nj of ins) {
      let best = -1
      let bestR = 0.7
      for (const oi of dels) {
        if (used.has(oi)) continue
        const r = bigramRatio(oldF[oi].text, newF[nj].text)
        if (r > bestR) {
          best = oi
          bestR = r
        }
      }
      if (best >= 0) {
        used.add(best)
        pairs.set(nj, [best, bestR])
      }
    }
    for (const oi of dels) {
      const partner = [...pairs.entries()].find(([, p]) => p[0] === oi)
      if (partner) ops.push({ type: 'edit', old: oi, new: partner[0], sim: partner[1][1] })
      else ops.push({ type: 'delete', old: oi })
    }
    for (const nj of ins) if (!pairs.has(nj)) ops.push({ type: 'insert', new: nj })
    dels = []
    ins = []
  }
  for (const op of raw) {
    if (op.type === 'equal') {
      flush()
      ops.push({ type: 'equal', old: op.o, new: op.j })
    } else if (op.type === 'delete') dels.push(op.o!)
    else ins.push(op.j!)
  }
  flush()
  return ops
}

export type LocalChange = {
  sid: string
  status: 'unchanged' | 'edited' | 'added' | 'deleted' | 'moved'
  old_text?: string
  new_text?: string
  similarity?: number
}

export function diffProseLocal(oldText: string, newText: string, artifactId: string): LocalChange[] {
  const oldF = flatten(oldText)
  const newF = flatten(newText)
  const prefix = artifactId ? `${artifactId}:` : ''
  const ops = align(oldF, newF)

  // "moved": equal-hash sentence whose paragraph offset differs from modal.
  const offsets = ops
    .filter((o) => o.type === 'equal')
    .map((o) => newF[o.new!].para - oldF[o.old!].para)
  const counts = new Map<number, number>()
  for (const o of offsets) counts.set(o, (counts.get(o) ?? 0) + 1)
  let modal = 0
  let bestC = 0
  for (const [o, c] of counts) {
    if (c > bestC || (c === bestC && Math.abs(o) < Math.abs(modal))) {
      modal = o
      bestC = c
    }
  }

  const changes: LocalChange[] = []
  for (const op of ops) {
    if (op.type === 'equal') {
      const o = oldF[op.old!]
      const nw = newF[op.new!]
      const moved = nw.para - o.para !== modal
      changes.push({
        sid: `${prefix}${o.para}:${o.sent}`,
        status: moved ? 'moved' : 'unchanged',
        old_text: o.text,
        new_text: nw.text,
        similarity: 1,
      })
    } else if (op.type === 'edit') {
      const o = oldF[op.old!]
      changes.push({
        sid: `${prefix}${o.para}:${o.sent}`,
        status: 'edited',
        old_text: o.text,
        new_text: newF[op.new!].text,
        similarity: op.sim,
      })
    } else if (op.type === 'delete') {
      const o = oldF[op.old!]
      changes.push({ sid: `${prefix}${o.para}:${o.sent}`, status: 'deleted', old_text: o.text })
    } else {
      const nw = newF[op.new!]
      changes.push({ sid: `${prefix}${nw.para}:${nw.sent}`, status: 'added', new_text: nw.text })
    }
  }
  return changes
}
