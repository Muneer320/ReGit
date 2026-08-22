# Git for Research — Enhanced Execution Brief

## 0. Situation
13-hour overnight hackathon. Team of 2 humans (Muneer = Systems/Arch, Amrit = Product/Integration) + AI agents doing the bulk of implementation. The win condition is NOT feature count — it is **demonstrated technical depth under the UI**: judges look for a real version-control model, immutable history, non-trivial diff/merge, actual concurrency, provenance, defensible retrieval, and conflict handling that isn't "git + an LLM wrapper."

## 1. Authoritative Problem Statement (from PDF — 13h, "Git for Research")
Core scope, all 4 pillars mandatory (minimal level ok for eligibility):
- **A. Ingestion** — ≥3 artifact types: Markdown/plaintext, LLM chat exports (ChatGPT conversations.json + Claude-specific schema — DO NOT assume identical formats), PDFs (text-extractable; OCR = stretch). Codebases (git repo or zip) = 4th, strongly encouraged.
- **B. Versioning Engine (technical core, 35%)** — discrete commits per artifact; SEMANTIC human-readable diff (sentence/paragraph for prose, AST/tree-sitter for code) not byte-diff; branching (fork a research thread/document); merging OR at minimum surfacing merge conflicts.
- **C. Concurrent Context Layer (20%)** — multiple users same workspace simultaneously: live presence (who's viewing/editing) + real conflict scenarios.

Out of scope: full auth (mock users fine), production OCR, building a vector DB from scratch (use pgvector/Chroma/Qdrant), polished UI.

Stretch goals (pick max 1–2, go deep): 3-way merge for prose w/ conflict UI; provenance graph (claim→source chat/PDF/commit); cross-artifact diff (PDF claim change propagates into citing doc); blame view; time-travel query (answer as corpus at past commit); multi-agent editing (LLM agent opens own branch, edits, submits for human merge review).

Suggested approach: content-addressed storage (hashed blobs + commit DAG); CRDT (Yjs/Automerge) or OT log for shared docs; AST/semantic diff (tree-sitter) for code, sentence/paragraph for prose; embeddings + vector store chunked by artifact type; parse ChatGPT + Claude differently.

**Evaluation weights:** versioning 35% | concurrency 20% | ingestion 15% | retrieval 15% | stretch ambition 10% | demo clarity 5%. Judges will first ask to see: (1) a live merge conflict, (2) a live semantic diff.

**Deliverables:** working repo + README; 5-min live demo (ingest ≥2 artifact types, one branch/merge scenario, one corpus query); one paragraph on what you'd build next.

## 2. Implicit Requirements (my inference — flag as assumptions)
- "Semantic diff" implies structure-aware diffing: prose at sentence/id-paragraph-level with alignment (not naive line diff), code at AST level.
- "Immutable history" implies content-addressed/merkle-like store where a commit hash is a full snapshot fingerprint; no in-place mutation.
- "Concurrent context layer" implies an order-preserving transport: CRDT or OT, with presence/awareness events.
- "Retrieval" quality implies chunking strategy differs by artifact type + the query surface must span the corpus, not just one doc.
- Judges probing "beyond git+LLM wrapper" implies we should distinguish our model (research-artifact object graph vs code file tree) and cite WHY a pure git model is insufficient for prose/chat/provenance.
- Live merge conflict demo must be deterministic and scriptable (3-way base/ours/theirs with a reliably colliding region), not flaky.

## 3. Strategic Decisions (what NOT to build first)
1. **No full auth.** Mock user ids, per-user capability passed in, presence keyed by id. Zero time on it.
2. **No DIY vector DB.** Use pgvector or Qdrant/Chroma. Pick ONE, pin it.
3. **No production OCR.** Skip or one fallback via marker/pdf text. Don't build a pipeline.
4. **UI = functional only.** Terminal-ish/SPA with clear affordances. Judges score the engine.
5. **Pick exactly ONE deep stretch.** Recommendation candidate: **provenance graph** AND/OR **3-way prose merge**. Decide early; do not gold-plate 3.
6. Pick the language we're fastest in for the versioning engine; don't over-engineer abstractions before committing exists.

## 4. Decision questions the agent MUST answer concretely (with tradeoffs)
1. Versioning primitive: real git (gitpython, subprocess) vs homemade DAG of hashed blobs. Tradeoffs: effort, control over semantic-object model, immutability guarantees, demo credibility. Give a hard recommendation + why a naive "just wrap git" fails the "beyond git+LLM" test for research artifacts.
2. Concurrency: which CRDT lib (Yjs vs Automerge) vs OT log. Node vs Python constraint. Latency/undo/presence support. Recommend one.
3. Diff: tree-sitter for code (which bindings), sentence-alignment algorithm for prose (difflib? gensim? a custom LCS-on-sentences?). What's cheap to demo well.
4. Retrieval: pgvector vs Chroma vs Qdrant; chunk strategy per artifact type; how semantic diff feeds retrieval.
5. Storage: SQLite vs Postgres; how the commit DAG is persisted; how blob content-addressing works.

## 5. 13-Hour Execution Plan (schedule to hit)
- Hr 0–1: finalize architecture from agent output; pick formats; scaffold repo.
- Hr 1–5: versioning engine core (commit model, diff, branch). MUST be working & demoable.
- Hr 5–8: ingestion parsers (md, ChatGPT json, Claude export, PDF text) + concurrent context layer (presence + CRDT).
- Hr 8–11: retrieval/query surface + merge conflict handling.
- Hr 11–12: integration, bug fixes (race conditions, bad abstraction review).
- Hr 12–13: demo prep, scripted live conflict + semantic diff, judge Q/A prep, README + one-paragraph next-build.

## 6. Deliverable from THIS run
Produce a **concrete, buildable architecture + technology recommendation + starter execution plan** — not a survey. For every major decision, state: recommendation, the runner-up, and the decisive tradeoff. Call out any requirement ambiguity and where an assumption is being made. Keep it actionable: the team should be able to start writing code immediately from your output.