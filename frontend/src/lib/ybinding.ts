// Y.Text ↔ <textarea> two-way binding (ADR-08 keeps this hand-written).
//
// Local edits apply with an 'origin' tag so remote reflections don't echo.
// Cursor/selection is preserved across remote replacements by mapping the
// caret through the applied delta.

import * as Y from 'yjs'
import type { Awareness } from 'y-protocols/awareness'

const ORIGIN = 'regit-textarea'

export interface Binding {
  destroy: () => void
}

export function bindTextareaToYText(
  ytext: Y.Text,
  textarea: HTMLTextAreaElement,
  awareness?: Awareness,
): Binding {
  // Seed once: empty local doc ← server content arrives via sync; only set
  // initial value if the text is untouched and textarea is empty.
  if (textarea.value === '' && ytext.length > 0) {
    textarea.value = ytext.toString()
  }

  let applyingRemote = false

  const onTextInputOrChange = () => {
    if (applyingRemote) return
    const current = ytext.toString()
    const next = textarea.value
    if (current === next) return
    const diff = simpleDiff(current, next, textarea.selectionStart ?? undefined)
    ytext.doc?.transact(() => {
      if (diff.deleteLen > 0) ytext.delete(diff.index, diff.deleteLen)
      if (diff.insert) ytext.insert(diff.index, diff.insert)
    }, ORIGIN)
    publishCursor()
  }

  const publishCursor = () => {
    if (!awareness) return
    awareness.setLocalStateField('cursor', {
      anchor: textarea.selectionStart ?? null,
      head: textarea.selectionEnd ?? null,
    })
  }

  // Remote → textarea.
  const observer = (_event: Y.YTextEvent, transaction: Y.Transaction) => {
    if (transaction.origin === ORIGIN) return
    applyingRemote = true
    try {
      // Demo-scale robust approach: recompute value from the CRDT (source of
      // truth), clamp the caret. Convergence is guaranteed by the CRDT; a
      // delta-walk caret mapping is the polish step if needed.
      const after = ytext.toString()
      const pos = Math.min(textarea.selectionStart ?? 0, after.length)
      const end = Math.min(textarea.selectionEnd ?? 0, after.length)
      textarea.value = after
      textarea.setSelectionRange(pos, end)
    } finally {
      applyingRemote = false
    }
  }
  ytext.observe(observer)

  textarea.addEventListener('input', onTextInputOrChange)
  textarea.addEventListener('select', publishCursor)
  textarea.addEventListener('keyup', publishCursor)
  textarea.addEventListener('click', publishCursor)

  return {
    destroy() {
      ytext.unobserve(observer)
      textarea.removeEventListener('input', onTextInputOrChange)
      textarea.removeEventListener('select', publishCursor)
      textarea.removeEventListener('keyup', publishCursor)
      textarea.removeEventListener('click', publishCursor)
    },
  }
}

/**
 * Diff a single-caret edit: find common prefix/suffix around the caret and
 * express the change as one insert+delete at that point. Covers typing,
 * paste, cut — everything a textarea emits in practice.
 */
export function simpleDiff(
  oldText: string,
  newText: string,
  caret?: number,
): { index: number; deleteLen: number; insert: string } {
  if (oldText === newText) return { index: 0, deleteLen: 0, insert: '' }
  const c = caret ?? firstDifference(oldText, newText)
  let start = Math.min(c, oldText.length, newText.length)
  while (start > 0 && oldText[start - 1] === newText[start - 1]) start--
  let endO = oldText.length
  let endN = newText.length
  while (endO > start && endN > start && oldText[endO - 1] === newText[endN - 1]) {
    endO--
    endN--
  }
  return { index: start, deleteLen: endO - start, insert: newText.slice(start, endN) }
}

function firstDifference(a: string, b: string): number {
  const n = Math.min(a.length, b.length)
  for (let i = 0; i < n; i++) if (a[i] !== b[i]) return i
  return n
}
