# ReGit — AUTHORITATIVE Operating Brief (13h hackathon)

Team: Muneer = Principal Systems Engineer / Technical Lead · Amrit = Product & Integration Engineer. AI agents = implementation multiplier. Humans own engineering judgment, architecture, validation, and the ability to explain the system to judges.

ORGANIZING PRINCIPLES (from the problem statement + brief):
- Win = demonstrated technical depth under the UI, NOT feature count. Judges look for: a real version-control model, meaningful immutable history, non-trivial diff/merge semantics, actual concurrent editing, structured research provenance, defensible retrieval, thoughtful conflict handling, decisions beyond "Git + an LLM wrapper."
- The two things judges ask to see FIRST: a live merge conflict + a live semantic diff. Both MUST be deterministic and scriptable.
- Define the system as "what if Git had been designed for research instead of source code?" — NOT "we put documents in Git and added AI search."
- Humans own the hardest engineering. AI aggressively handles boilerplate/CRUD/parsers/tests/UI/adapters/plumbing. Never let an agent implement a technically critical subsystem without producing an explanation Muneer can understand and defend.

## SOURCE PROBLEM STATEMENT (subject line = manual, from PDF, 13h)
All 4 pillars mandatory (minimal level ok for eligibility):
- **A. Ingestion** — ≥3 artifact types: Markdown/plaintext, LLM chat exports (ChatGPT conversations.json + Claude-specific schema — DO NOT assume identical schemas), PDFs (text-extractable; OCR = stretch), codebases (4th, strongly encouraged). Preserve structure; do NOT flatten to a giant string.
- **B. Versioning core (35%)** — discrete commits per artifact; SEMANTIC human-readable diff (not byte diff); branching (fork a research thread/doc); merging OR at minimum surfacing merge conflicts.
- **C. Concurrent context layer (20%)** — multiple users same workspace: live presence + real conflict scenarios.
Out of scope: full auth (mock users fine), production OCR, building a vector DB from scratch (use pgvector/Chroma/Qdrant), polished UI.
Stretch (pick max 1–2 deep): 3-way prose merge w/ conflict UI; provenance graph; cross-artifact diff; blame; time-travel query; multi-agent editing.
Eval weights: versioning 35 | concurrency 20 | ingestion 15 | retrieval 15 | stretch 10 | demo 5.
Deliverables: working repo + README; 5-min demo (ingest ≥2 types, one branch/merge, one corpus query); one-paragraph next-build.

## THE BRIEF'S TWO FIRST ACTIONS
1. **RECON, DO NOT CODE YET.** Understand the deeper problem: Why does Git work so well for code? Why does research behave differently? Why are research artifacts heterogeneous? Why are linear doc histories insufficient? Why do semantic changes matter? Why is provenance important? Why does collaboration get hard? What information does conventional VCS destroy? No shallow "research is fragmented" answers.
2. **REVERSE-ENGINEER THE JUDGING.** For every criterion: what judges want / minimum impl / strong impl / killer demo. For every feature ask: "how do we prove this works in under 30 seconds?" Don't optimize invisible engineering unless it supports something demonstrable.

## COMPETITIVE DIFFERENTIATION
Explain the "GitHub wrapper trap" (upload → git repo → LLM search → pretty UI is insufficient). Define minimum depth for "this is actually a research-native VCS." Identify 3–5 killer technical differentiators — these become the demo's center.

## DEEP RESEARCH AREAS (before locking architecture)
- **VCS:** git object model, content-addressed storage, DAG history, snapshots, commits, branches, merge bases, packfiles (conceptually), immutability. Adopt what fits, deliberately simplify the rest.
- **CRDT/OT:** compare at minimum Yjs, Automerge, eg-walker/Eg-walker, Diamond Types, OT, custom minimal CRDT. Cover: convergence, operation model, conflict semantics, memory, persistence, offline, WebSocket integration, TipTap/ProseMirror compat, complexity, maturity, known issues. Do NOT pick Yjs just because it's popular — pick on the actual technical reason.
- **Diff:** Myers, patience, histogram, sentence-level LCS, word-level diff, AST diff, semantic diff, embedding similarity, move detection. Different artifact types → different diff strategies: prose = sentence/paragraph-aware; code = line/token/AST-aware; chat = message/turn-aware; structured = structural. Don't force one algorithm on everything.
- **Merge:** base/left/right→merge. How is merge base found, changes represented, non-conflicting edits merge, conflicts detected, can some auto-resolve, how are conflict markers represented, how users resolve, how result becomes a commit. One of the highest-value areas.
- **Content addressing:** SHA-256, Merkle structures, dedup, integrity verification. Decide blob/tree/commit vs a simplified research-native object hierarchy.
- **Provenance (potential strongest differentiator):** model source → imported artifact → artifact version → commit → research claim → derived artifact. Answer: "where did this claim come from?", "what did the researcher know at commit X?", "which sources influenced this document?" Treat as first-class technical primitive, not metadata.
- **Retrieval:** BM25, vector, embeddings, hybrid, graph, temporal, provenance filtering, reranking. Ideal pipeline: query → keyword → vector → version/provenance filter → graph relations → rerank → cited result. NOT a useless RAG chatbot — retrieval must understand research history.
- **Ingestion:** exact formats for Markdown, plain text, PDF, ChatGPT exports, Claude exports, code, structured docs. Preserve structure.

## ARCHITECTURE
Produce final architecture. Reference diagram (do NOT assume correct — change if research says so): Frontend ↔ (REST/WebSocket) ↔ Backend {Artifact, Version, Diff, Merge, Sync, Retrieval, Ingestion, Provenance Engines} → {Object Store, Metadata DB, Search Index}.

## ADRs (13 required, every one influences implementation, no paperwork)
Object model, content addressing, version graph, diff algorithm, merge algorithm, CRDT/OT, backend, frontend, database/storage, realtime protocol, retrieval, provenance, deployment, AI integration. Each: Context, Problem, Alternatives, Comparison, Decision, Why, Risks, Reversibility, Implementation consequences.

## SYSTEM DATA MODEL — exact schemas for:
Blob, Tree, Commit, Branch, Artifact, ArtifactVersion, Workspace, Change, Diff, Merge, Conflict, CRDTOperation, ResearchSource, Claim, ProvenanceEdge, Embedding, SearchResult. Define fields, IDs, relationships, invariants, serialization, persistence. Version graph explicit.

## CORE INVARIANTS (become automated tests — never break)
1. Content integrity: object_id == SHA256(canonical_content).
2. Commit immutability: once a commit exists, its contents cannot change.
3. Branch semantics: a branch is a mutable reference to an immutable commit.
4. Convergence: two clients receiving the same valid CRDT ops reach equivalent state.
5. Provenance: every retrieved research claim is traceable to an underlying artifact/version/source.
6. Merge: a merge must never silently discard incompatible changes.

## API CONTRACT (define before implementation)
POST /artifacts, GET /artifacts/:id, DELETE /artifacts/:id, POST /artifacts/:id/commit, GET /artifacts/:id/history, POST /branches, GET /branches, POST /checkout, GET /diff, POST /merge, POST /ingest, POST /search, WS /collaborate/:artifact_id. Each: request, response, errors, validation, concurrency behavior, idempotency.

## REALTIME PROTOCOL — exact definition
Client A op → Server {validate, persist, broadcast} → Client B. Define: operation IDs, client IDs, clocks/version vectors, ordering, ack, reconnect, duplicate ops, out-of-order ops, persistence, conflict behavior.

## IMPLEMENTATION STRATEGY — parallel workstreams, not sequential
- **A (Muneer):** version engine, object model, diff, merge, CRDT architecture, provenance semantics, critical correctness tests.
- **B (Amrit):** frontend, workspace, artifact views, diff UI, collaboration UI, ingestion flow, search UI, demo prep.
- **C (AI agents):** API scaffolding, DB setup, parsers, WebSocket plumbing, frontend components, tests, fixtures, integration, deployment.

MUNEER'S WORK MUST BE HARD — assign the technically difficult work (distributed systems, algorithms, data structures, consistency, concurrency, merge semantics, provenance, retrieval architecture, performance, correctness) to Muneer; agents build supporting infrastructure around his decisions. Do not reduce him to "reviewer." He must be able to explain everything on a whiteboard — simplify/document/test/study anything he can't.

## AGENT CODING PROTOCOL
Per subsystem agent: State design → Implement → Run tests → Adversarial testing → Explain → Report {Implemented, Files changed, Tests, Known limitations, Potential bugs, Technical decisions, Human review required}. Never claim success just because code compiles.

## TESTING STRATEGY — disproportionate focus on the hard parts
- Versioning: identical/changed/large/binary/duplicate/corrupted content, ancestry, branches.
- Diff: insert/delete/replace, paragraph+sentence movement, reorder, large.
- Merge: same change, independent, same-line, overlapping, delete-vs-modify, move-vs-modify, multiple + nested conflicts.
- CRDT: A edits, B edits, concurrent, A disconnect/B continue/A reconnect, out-of-order, duplicate op.
- Provenance: source→artifact→version→claim chain intact across branch+merge.
Adversarial tests keyed to the invariants.

## PERFORMANCE — measure, don't guess
Benchmark: commit/diff/merge latency, object storage overhead, retrieval latency, concurrent edit propagation. Find the bottleneck that could become a judge question. Don't waste hours on insignificant things.

## MVP / TARGET / STRETCH (every feature in exactly one tier)
- MVP: if everything goes wrong this MUST work.
- TARGET: expected demonstrated after ~10h.
- STRETCH: only if core stable. If stretch threatens MVP → CUT IT.

## 12-HOUR EXECUTION PLAN (modify after dependency analysis)
0–1 arch/UX skeleton/repo setup → 1–3 version engine/frontend/API+parsers, first commit → 3–5 diff/merge/diff UI/integration, real diff → 5–7 CRDT/collab UI/sync, live collab → 7–9 provenance+retrieval/search UX/retrieval impl, research query → 9–10 hardening/E2E/tests, stable → 10–11 judge testing/demo prep/bug fix, demo-ready → 11–12 final validation/presentation/freeze → submission.

## HARD CUT-OFFS
T+2h core artifact/version model works · T+4h diff works · T+6h merge works · T+7h collaboration works · T+9h retrieval/provenance works · T+10h feature freeze · T+11h only bug fixes · T+12h demo. Miss a deadline → downgrade/remove. No emotional attachment to code.

## DEMO DESIGN — a technical story, NOT "here's our dashboard"
8 scenes: Research (import paper/ChatGPT/notes/code/PDF → structured artifacts) → Versioning (modify, commit, history) → Semantic diff (meaningful change, semantic not raw line diff) → Branching (two research directions) → Merge (genuine conflict, resolve it) → Collaboration (two users edit simultaneously, convergence) → Provenance ("where did this claim come from?" trace chain) → Temporal research ("what did we know at this point?", version-aware retrieval) — climax.

## JUDGE Q&A — at least 20 difficult questions
Why isn't this just Git/Notion? Why CRDT vs OT vs Git itself? How do you merge prose? Detect semantic conflicts? Handle PDFs? Preserve provenance? What happens when two researchers disagree / offline / server crashes? What guarantees consistency? What is immutable? Why content addressing? Complexity of diff? At 100k artifacts? What changes for production? What part is AI-generated? Hardest engineering problem? Each answer: 15-sec, 60-sec, deep versions.

## FAILURE MODE ANALYSIS — ≥15 modes
Each: Failure, Probability, Impact, Detection, Mitigation, Fallback, Demo strategy. Pay attention to: CRDT integration failure, merge corruption, WebSocket instability, parser incompatibility, embedding API failure, DB failure, deployment failure, frontend/backend mismatch, race conditions, corrupted object store, time running out.

## OBSERVABILITY — lightweight
Structured logs, operation IDs, commit IDs, artifact IDs, request timing, sync/merge events, errors. Debugging speed > production-grade observability.

## DEMO FALLBACKS
Realtime fails → deterministic offline CRDT replay. Embeddings fail → BM25/keyword. PDF parse fails → prepared extracted text. Deployment fails → local demo. Frontend breaks → API/CLI demo. Merge UI breaks → CLI/API merge demo. System stays demonstrable even if one layer dies.

## DOCUMENTATION — only what helps execution
/docs: architecture, decisions, data-model, versioning, diff, merge, collaboration, provenance, retrieval, ingestion, demo, judge-qa, known-limitations. No beautiful-doc rabbit holes; code + working demos first.

## REPOSITORY STRUCTURE (modify as appropriate)
backend/{api, core/{objects,versioning,diff,merge,collaboration}, ingestion, retrieval, provenance} · frontend/ · tests/{unit, integration, concurrency, adversarial} · docs/ · scripts/

## SECURITY & DATA SAFETY
Consider: arbitrary file uploads, path traversal, malicious files, prompt injection from imported research, secrets in artifacts, API key exposure, untrusted doc content, WebSocket authorization. Document what is actually protected vs deliberately out of scope. Don't fake a security story.

## AI USAGE POLICY
Divide into AI-generated implementation (boilerplate, adapters, tests, parsers, UI, repetitive APIs) vs Human-owned reasoning (architecture, distributed systems, merge semantics, data model, correctness, tradeoffs, limitations). Humans own engineering; AI accelerates execution.

## CONTINUOUS COURSE CORRECTION — every milestone report
CURRENT STATUS {Working, Broken, Risky, Behind/Ahead schedule} · MVP/Target/Stretch · Critical path/bottleneck · Next 60 min for Muneer/Amrit/Agents · Features to CUT / PROTECT. Don't continue blindly if the plan is failing.

## FINAL TECHNICAL REVIEW — hostile, three judge personas (distributed systems, research/AI, software eng). Attack: fake CRDT, fake version control, meaningless semantic diff, RAG bolted onto Git, provenance that isn't, race conditions, inconsistent state, silent data loss, unsupported claims, misleading demo. Fix highest-risk problems.

## FINAL OUTPUT
A Executive Summary · B Problem Analysis · C Competitive/Technical Differentiation · D Research Report w/ sources · E Architecture · F ADRs · G Data Model · H API Spec · I Versioning Spec · J Diff Spec · K Merge Spec · L Collaboration Spec · M Provenance Spec · N Retrieval Spec · O Ingestion Spec · P 12h Implementation Plan · Q Team Ownership Matrix · R Testing Plan · S Demo Script · T Judge Q&A (≥20) · U Failure Playbook · V Post-Hackathon Architecture.

## DEFINITION OF DONE
Core: artifacts ingested, immutable versions, DAG commits, branches, diffs, 3-way merge, conflicts representable, collaboration, provenance, version/provenance-aware retrieval, survives realistic failures. Technical: invariants tested, adversarial concurrency + merge tests, data integrity validated, core reviewed by Muneer, Muneer can explain all algorithms. Demo: clean dataset, repeatable, backup path, 5-min narrative, judge Q&A, depth visible.

## FINAL PRINCIPLE
"Someone asked: what if Git had been designed for research instead of source code?" — not "we put documents in Git and added AI search." That distinction is the entire game. Ruthless scope, ambitious depth, aggressive delegation, hardest decisions stay with Muneer, Amrit drives integration/quality/testing/demo. At hour 12: a smaller system that genuinely works, not a larger one that exists mostly in Markdown.

## STRICT PROTOCOL FOR THIS RUN — READ BEFORE ACTING
This is higher priority than anything else in this file.
1. Perform RECON first, do NOT code yet. Inspect the supplied problem statement and any current repository/project state.
2. Extract requirements (organizer / research / assumptions / strategic decisions — keep them clearly separated; do not silently invent requirements).
3. Research the hardest architectural uncertainties (CRDT choice, merge base + 3-way, content addressing, provenance as primitive, retrieval pipeline, per-artifact diff). Use web research for validation; cite tool/library maturity.
4. Produce the recommended architecture + full ownership plan (Muneer/Amrit/AI) + identify the critical path.
5. Write the decision artifacts to disk as markdown under /home/foaly/ReGit/: ADRs, data-model, api-contract, realtime-protocol, versioning/diff/merge/collaboration/provenance/retrieval/ingestion specs, 12h-execution-plan, ownership-matrix, testing-plan, demo-script, judge-qa, failure-playbook, architecture.md.
6. For EVERY major decision state: recommendation, runner-up, decisive tradeoff.
7. Do NOT write 30,000 words and declare victory. Production is decisions + working skeleton stubs where feasible. But the PRIMARY deliverable of THIS run is the locked architecture + ownership plan + critical path + starting codebase scaffold, because the humans must review architecture before heavy implementation.
8. Verify you actually wrote each file (stat it) before reporting done. Report: files written, the critical path, the Muneer vs Amrit vs AI split, and the top 3 unknowns that need human decisions right now.