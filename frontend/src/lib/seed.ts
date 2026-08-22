// One-click demo seeding against the REAL backend: creates the scripted
// merge-conflict scene (merge-spec.md fixtures) and a research-notes artifact
// for history/diff/search scenes. Safe to re-run (idempotent-ish: it always
// creates fresh artifacts, but content addressing dedups identical commits).

import { api, registryRegister } from './api'
import { DEMO_DOC_TITLE, DEMO_DOC_V1, DEMO_DOC_V2, FIXTURE_BASE, FIXTURE_OURS, FIXTURE_THEIRS } from './fixtures'

export interface SeedResult {
  notesId: string
  mergeId: string
}

export async function seedDemoData(): Promise<SeedResult> {
  // Scene A: research notes (history, diff, search corpus).
  const notes = await api.createArtifact({ kind: 'md', title: DEMO_DOC_TITLE, content: DEMO_DOC_V1 })
  await api.createBranch({ artifact_id: notes.artifact_id, name: 'review-branch' })
  await api.commit(notes.artifact_id, {
    branch: 'review-branch',
    content: DEMO_DOC_V2,
    message: 'expand learning-rate findings, add warmup observation',
  })

  // Scene B: the scripted conflict (fixtures base/ours/theirs).
  const mrg = await api.createArtifact({ kind: 'md', title: 'lr-stability.md', content: FIXTURE_BASE })
  const aid = mrg.artifact_id
  await api.createBranch({ artifact_id: aid, name: 'research-branch' })
  // ours edits sentence 2 one way on main…
  const mainHead = await api.listBranches(aid).then((bs) => bs.find((b) => b.name === 'main')?.head_commit_id)
  await api.commit(aid, { branch: 'main', content: FIXTURE_OURS, message: 'ours: add deeper-model spikes at lr=0.05' })
  // …theirs edits it differently on research-branch.
  await api.commit(aid, { branch: 'research-branch', content: FIXTURE_THEIRS, message: 'theirs: reinterpret spikes as oscillations' })
  void mainHead

  registryRegister([
    { id: notes.artifact_id, title: DEMO_DOC_TITLE, kind: 'md', created_at: new Date().toISOString(), source_filename: 'notes.md' },
    { id: aid, title: 'lr-stability.md', kind: 'md', created_at: new Date().toISOString(), source_filename: 'base.md' },
  ])

  return { notesId: notes.artifact_id, mergeId: aid }
}
