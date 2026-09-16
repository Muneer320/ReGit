import assert from 'node:assert/strict'
import test from 'node:test'
import * as Y from 'yjs'
import { simpleDiff } from '../src/lib/ybinding.ts'

for (const [before, after] of [
  ['Initial shared research.', 'Shared café research.\nclaim: Shared live finding.'],
  ['', 'First text.'], ['Delete everything.', ''], ['same', 'same'],
  ['one two three', 'one changed three'], ['tail', 'prefix tail'], ['head', 'head suffix'],
  ['🌍 result', '🌎 result'], ['Text 🧪 done', 'Text 🧬 done'],
]) {
  test(`textarea replacement ${JSON.stringify(before)} → ${JSON.stringify(after)}`, () => {
    const document = new Y.Doc()
    const text = document.getText('content')
    text.insert(0, before)
    const delta = simpleDiff(before, after, after.length)
    document.transact(() => { text.delete(delta.index, delta.deleteLen); text.insert(delta.index, delta.insert) })
    assert.equal(text.toString(), after)
    document.destroy()
  })
}
