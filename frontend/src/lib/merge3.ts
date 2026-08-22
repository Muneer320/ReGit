// Client-side 3-way prose merge — demo fallback mirroring
// backend/src/core/merge/three_way.py's decision table (merge-spec.md):
//   unchanged both        -> keep base
//   one side changed      -> take that side
//   both changed, same    -> convergent, take ours
//   both changed, diff    -> CONFLICT (incl. delete-vs-modify)
//   both delete           -> convergent removal
//   same-anchor inserts   -> keep both (ours then theirs), informational flag
//
// Conflicts carry git-style marker blocks in mergedText keyed by sid, so a
// resolution replaces its marker block unambiguously (composeResolvedText).

const SENT_SPLIT = /(?<=[.!?])\s+(?=[A-Z0-9"'(])/

export function splitParagraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0)
}

export function splitSentences(paragraph: string): string[] {
  return paragraph
    .trim()
    .split(SENT_SPLIT)
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

export function normalize(sentence: string): string {
  return sentence
    .toLowerCase()
    .replace(/[^\w\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

type Flat = { para: number; sent: number; text: string }[]

function flatten(text: string): Flat {
  const out: Flat = []
  splitParagraphs(text).forEach((p, pi) => {
    splitSentences(p).forEach((s, si) => out.push({ para: pi, sent: si, text: s }))
  })
  return out
}

interface AlignOp {
  type: 'equal' | 'edit' | 'delete' | 'insert'
  old?: number
  new?: number
}

/** Sentence-level alignment (LCS over normalized sentences). */
function align(oldF: Flat, newF: Flat): AlignOp[] {
  const oh = oldF.map((s) => normalize(s.text))
  const nh = newF.map((s) => normalize(s.text))
  const n = oh.length
  const m = nh.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      dp[i][j] =
        oh[i - 1] === nh[j - 1]
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }
  // Raw ops backtracked, then delete/insert runs paired into edits when their
  // raw texts are similar enough (>= 0.6 char-bigram ratio, like difflib).
  type RawOp = { type: 'equal' | 'delete' | 'insert'; o?: number; n2?: number }
  const raw: RawOp[] = []
  let i = n
  let j = m
  while (i > 0 && j > 0) {
    if (oh[i - 1] === nh[j - 1]) {
      raw.push({ type: 'equal', o: i - 1, n2: j - 1 })
      i--
      j--
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      raw.push({ type: 'delete', o: i - 1 })
      i--
    } else {
      raw.push({ type: 'insert', n2: j - 1 })
      j--
    }
  }
  while (i > 0) raw.push({ type: 'delete', o: --i })
  while (j > 0) raw.push({ type: 'insert', n2: --j })
  raw.reverse()

  const ratio = (a: string, b: string): number => {
    if (a === b) return 1
    const grams = (s: string) => {
      const set = new Set<string>()
      for (let k = 0; k < s.length - 1; k++) set.add(s.slice(k, k + 2))
      return set
    }
    const ga = grams(a)
    const gb = grams(b)
    let inter = 0
    ga.forEach((g) => {
      if (gb.has(g)) inter++
    })
    return (2 * inter) / (ga.size + gb.size || 1)
  }

  const ops: AlignOp[] = []
  let dels: number[] = []
  let ins: number[] = []
  const flush = () => {
    const used = new Set<number>()
    const pairs = new Map<number, number>() // newIdx -> oldIdx
    for (const nj of ins) {
      let best = -1
      let bestR = 0.6
      for (const oi of dels) {
        if (used.has(oi)) continue
        const r = ratio(oldF[oi].text, newF[nj].text)
        if (r > bestR) {
          best = oi
          bestR = r
        }
      }
      if (best >= 0) {
        used.add(best)
        pairs.set(nj, best)
      }
    }
    for (const oi of dels) {
      const partner = [...pairs.entries()].find(([, o]) => o === oi)
      if (partner) ops.push({ type: 'edit', old: oi, new: partner[0] })
      else ops.push({ type: 'delete', old: oi })
    }
    for (const nj of ins) if (!pairs.has(nj)) ops.push({ type: 'insert', new: nj })
    dels = []
    ins = []
  }
  for (const op of raw) {
    if (op.type === 'equal') {
      flush()
      ops.push({ type: 'equal', old: op.o, new: op.n2 })
    } else if (op.type === 'delete') dels.push(op.o!)
    else ins.push(op.n2!)
  }
  flush()
  return ops
}

/** Per-base-sentence changes + same-anchor insert buckets for one side. */
function sideOps(baseF: Flat, sideF: Flat) {
  const change = new Map<number, { kind: 'equal' | 'edit' | 'delete'; text?: string }>()
  const inserts = new Map<number, string[]>() // anchor (base idx) -> inserted texts
  let lastBase = 0
  for (const op of align(baseF, sideF)) {
    if (op.type === 'equal') change.set(op.old!, { kind: 'equal' })
    else if (op.type === 'edit')
      change.set(op.old!, { kind: 'edit', text: sideF[op.new!].text })
    else if (op.type === 'delete') change.set(op.old!, { kind: 'delete' })
    else {
      inserts.set(lastBase, [...(inserts.get(lastBase) ?? []), sideF[op.new!].text])
      continue
    }
    lastBase = op.old! + 1
  }
  return { change, inserts }
}

export interface Merge3Conflict {
  sid: string
  base_text: string
  ours_text: string
  theirs_text: string
}

export interface Merge3Result {
  mergedText: string
  conflicts: Merge3Conflict[]
  state: 'clean' | 'conflicts'
  insertOverlaps: { sid: string; ours_text: string; theirs_text: string }[]
  stats: { kept: number; takenOurs: number; takenTheirs: number; conflicts: number }
}

export function mergeProse(baseText: string, oursText: string, theirsText: string): Merge3Result {
  const baseF = flatten(baseText)
  const oursF = flatten(oursText)
  const theirsF = flatten(theirsText)
  const A = sideOps(baseF, oursF)
  const B = sideOps(baseF, theirsF)

  type Item = { text: string; para: number; conflictSid?: string }
  const items: Item[] = []
  const conflicts: Merge3Conflict[] = []
  const insertOverlaps: Merge3Result['insertOverlaps'] = []
  const stats = { kept: 0, takenOurs: 0, takenTheirs: 0, conflicts: 0 }

  const pushInserts = (anchor: number) => {
    const a = A.inserts.get(anchor) ?? []
    const b = B.inserts.get(anchor) ?? []
    a.forEach((t) => items.push({ text: t, para: Number.MAX_SAFE_INTEGER }))
    b.forEach((t) => items.push({ text: t, para: Number.MAX_SAFE_INTEGER }))
    if (a.length > 0 && b.length > 0) {
      insertOverlaps.push({
        sid: `${anchor}:ins`,
        ours_text: a.join(' '),
        theirs_text: b.join(' '),
      })
    }
  }

  for (let k = 0; k < baseF.length; k++) {
    pushInserts(k)
    const ca = A.change.get(k)
    const cb = B.change.get(k)
    const bs = baseF[k]
    const aChanged = ca && ca.kind !== 'equal'
    const bChanged = cb && cb.kind !== 'equal'
    if (!aChanged && !bChanged) {
      items.push({ text: bs.text, para: bs.para })
      stats.kept++
    } else if (aChanged && !bChanged) {
      const t = ca!.kind === 'edit' ? ca!.text! : ''
      items.push({ text: t, para: bs.para })
      stats.takenOurs++
    } else if (!aChanged && bChanged) {
      const t = cb!.kind === 'edit' ? cb!.text! : ''
      items.push({ text: t, para: bs.para })
      stats.takenTheirs++
    } else {
      const at = ca!.kind === 'edit' ? ca!.text! : ''
      const bt = cb!.kind === 'edit' ? cb!.text! : ''
      if (normalize(at) === normalize(bt)) {
        items.push({ text: at, para: bs.para }) // convergent
        stats.kept++
      } else {
        const sid = `cnf_${k}`
        conflicts.push({
          sid,
          base_text: bs.text,
          ours_text: at,
          theirs_text: bt,
        })
        stats.conflicts++
        items.push({ text: '', para: bs.para, conflictSid: sid })
      }
    }
  }
  pushInserts(baseF.length)

  // Compose text: group items into paragraph blocks (blank line between
  // blocks); sentences inside a block join with spaces; conflict slots render
  // as git-style marker blocks keyed by sid.
  type Part = string | Merge3Conflict
  const blocks: Part[][] = []
  let lastPara: number | null = null

  const pushMarker = (c: Merge3Conflict) => {
    if (blocks.length === 0 || typeof lastPara === 'number') blocks.push([])
    blocks[blocks.length - 1].push(c)
    lastPara = null // next sentence starts a fresh visual slot after markers
  }
  const pushSentence = (text: string, para: number) => {
    if (
      blocks.length === 0 ||
      lastPara === null ||
      (para !== Number.MAX_SAFE_INTEGER && para !== lastPara)
    ) {
      blocks.push([text])
    } else {
      blocks[blocks.length - 1].push(text)
    }
    lastPara = para === Number.MAX_SAFE_INTEGER ? lastPara : para
  }

  for (const it of items) {
    if (it.conflictSid) {
      pushMarker(conflicts.find((x) => x.sid === it.conflictSid)!)
    } else {
      pushSentence(it.text, it.para)
    }
  }

  const markerLines = (c: Merge3Conflict) =>
    [`<<<<<<< ours ${c.sid}`, c.ours_text, '=======', c.theirs_text, `>>>>>>> theirs ${c.sid}`]

  const renderBlock = (parts: Part[]): string => {
    const lines: string[] = []
    let cur = ''
    for (const p of parts) {
      if (typeof p === 'string') {
        cur = cur ? `${cur} ${p}` : p
      } else {
        if (cur) {
          lines.push(cur)
          cur = ''
        }
        lines.push(...markerLines(p))
      }
    }
    if (cur) lines.push(cur)
    return lines.join('\n')
  }

  const mergedText =
    blocks.map(renderBlock).join('\n\n').replace(/\n{3,}/g, '\n\n') + '\n'
  return {
    mergedText,
    conflicts,
    state: conflicts.length > 0 ? 'conflicts' : 'clean',
    insertOverlaps,
    stats,
  }
}

/** Replace a conflict's marker block with the resolved text (lifecycle step 4). */
export function composeResolvedText(
  mergedText: string,
  resolutions: { conflict_id: string; resolved_text: string }[],
): string {
  let out = mergedText
  for (const r of resolutions) {
    const re = new RegExp(
      `<<<<<<< ours ${r.conflict_id}\\n[\\s\\S]*?>>>>>>> theirs ${r.conflict_id}`,
    )
    out = out.replace(re, r.resolved_text)
  }
  return out.replace(/\n{3,}/g, '\n\n')
}
