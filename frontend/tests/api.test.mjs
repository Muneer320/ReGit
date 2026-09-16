import assert from 'node:assert/strict'
import test from 'node:test'
import { api } from '../src/lib/api.ts'

globalThis.localStorage = {getItem: () => null}
globalThis.sessionStorage = {getItem: () => null}

test('backend failures remain errors for merge, diff and search', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({error: {code: 'NOT_IMPLEMENTED', message: 'Unsupported artifact type.'}}), {status: 501})
    for (const action of [() => api.merge('one', 'main', 'feature'), () => api.diff('one', 'a', 'b'), () => api.search('research')]) {
      await assert.rejects(action(), error => error.status === 501 && error.message === 'Unsupported artifact type.')
    }
    globalThis.fetch = async () => { throw new Error('offline') }
    await assert.rejects(api.listArtifacts(), error => error.code === 'NETWORK')
  } finally { globalThis.fetch = original }
})
