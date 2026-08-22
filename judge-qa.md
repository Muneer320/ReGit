# Judge Q&A — 24 questions (15-sec / 60-sec / deep)

**Q1. Why isn't this just Git?**
15s: Git versions lines of bytes; we version typed research artifacts with canonical identity, sentence-level merge, and provenance edges — things git's object model can't represent.
60s: Four concrete gaps: line-diff noise on prose reflow; byte-identity lies on chat re-exports (we canonicalize first — same conversation, same hash); no claim→source entity; no corpus-level temporal query. We kept git's good ideas — content addressing, merkle commits, DAG, refs — and rebuilt the semantics around research artifacts.
Deep: walk the commit-hash preimage, show the canonical chat form, show sentence_index lineage.

**Q2. Why isn't this just Notion/Overleaf?**
15s: Those are editors with history; this is a version-control model — content-addressed immutable DAG, 3-way merge semantics, provenance queries — with an editor attached.
60s: Emphasize immutability (triggers+hashes), merge-base finding, conflict records as data, and that our history is tamper-evident and verifiable (`gr verify`), which collaborative editors don't offer.
Deep: contrast op-log-only systems (state reconstruction) vs our snapshot DAG; discuss what each can answer.

**Q3. Why CRDT over OT?**
15s: Convergence without a central transform authority, plus free presence/undo; OT would make ordering and transform correctness our proof obligation.
60s: OT needs correct transform functions for every op pair and a sequenced server; CRDT (Yjs family) gives commutative, idempotent ops — out-of-order and duplicate delivery are safe, which our property test proves by shuffling op logs.
Deep: discuss eg-walker (OT/CRDT hybrid, JS-only) and why we rejected custom CRDT (interleaving anomalies, unprovable in 13h).

**Q4. Why pycrdt/Yjs over Automerge?**
15s: Only Yjs has a maintained, production-proven Python binding — pycrdt, built for Jupyter's real-time collaboration; Automerge has no maintained Python binding for v2.
60s: Our engine is Python (PDF, chat parsing, embeddings). pycrdt is Yrs (Rust Yjs port) with Jupyter pedigree; browser yjs is wire-compatible. Automerge's paper story is great; its Python story is stale 1.x wrappers.
Deep: memory/model tradeoffs (Yjs GC/tombstones vs Automerge op log), awareness protocol, UndoManager.

**Q5. How do you merge prose?**
15s: Sentence-level 3-way: align base→ours and base→theirs with our LCS engine, then a per-sentence decision table; divergent same-sentence edits become conflict records.
60s: Walk the decision table on the fixture: disjoint edits auto-merge; identical edits converge silently; divergent edits produce a conflict card with base/ours/theirs; resolution becomes a 2-parent commit.
Deep: alignment stability, 0.7 edit threshold, insert-at-same-anchor ordering, why word-level diff3 was rejected.

**Q6. How do you detect semantic conflicts — e.g., contradictory claims in different sentences?**
15s: We don't claim to. We detect *textual* divergence at claim granularity; cross-sentence contradiction detection is LLM territory we deliberately excluded from correctness paths.
60s: Explain the honesty boundary: deterministic structural conflicts now; semantic contradiction detection is a named next-build with an LLM assist that *proposes*, humans dispose.
Deep: discuss why deterministic claims beat unsourced LLM claims under adversarial judging.

**Q7. How do you handle PDFs?**
15s: pypdf text extraction into a page→paragraph structure; that's the versioned canonical form; OCR is out of scope per the brief.
60s: Show the JSON structure, page-scoped diff spans, graceful 422 on image-only PDFs.
Deep: canonicalization choices, chunking for retrieval, extraction-failure handling.

**Q8. How is provenance preserved?**
15s: Typed edges written at ingest/commit: source→artifact→version→commit→claim; plus per-sentence lineage from the diff engine.
60s: Demo the claim query chain; explain sentinel-declared claims (deterministic) + automatic sentence lineage; chunk metadata carries introduced-in-commit into every search hit.
Deep: edge invariants across merge (claims never silently dropped), why LLM extraction was rejected.

**Q9. What happens when two researchers disagree?**
15s: They branch, diverge, and merge — divergent same-claim edits surface as conflict cards with both texts and the base; resolution is explicit and becomes a merge commit.
60s: Walk S5 of the demo; emphasize nothing is silently discarded (invariant 6, delete-vs-modify → conflict).
Deep: discuss social-vs-technical conflicts; why CRDT typing-time "conflicts" are a different (absorbed) class.

**Q10. What about offline editing?**
15s: Ops are idempotent and order-independent; a disconnected client buffers ops and state-vector sync heals on reconnect; server persists ops before broadcast so crash recovery is replay.
60s: Show the op log + replay script; explain yjs two-step sync.
Deep: persistence format, room rebuild from head+log, edge cases (long offline divergence → next-commit attribution).

**Q11. Server crashes mid-edit?**
15s: Rooms rebuild deterministically from branch head + persisted op log; demo shows kill -9 → restart → text intact.
60s: Walk the recovery path and the persist-before-broadcast ordering.
Deep: fsync posture (SQLite synchronous=FULL), what could still be lost (unflushed last frame) and why that's acceptable.

**Q12. What guarantees consistency?**
15s: Three layers: content addressing (integrity), CRDT math (convergence), CAS refs (no lost branch updates) — each independently testable, and tested.
60s: Point at invariant suite: hash recompute, shuffled-op convergence property test, CAS 409 test.
Deep: discuss what we do NOT guarantee (no distributed multi-server consistency — single-node by design, scale-up path named).

**Q13. What exactly is immutable here?**
15s: Blobs, trees, commits — enforced by content addressing AND SQL triggers; only branch refs mutate, via compare-and-swap.
60s: Show trigger DDL, show tampered-blob detection in `gr verify`.
Deep: why immutable history matters for research (unrewriteable record), GC policy, legal/audit angle.

**Q14. Why content addressing?**
15s: Identity = content: dedup for free, tamper evidence for free, reproducible commits, and canonicalization-before-hash gives semantic identity for volatile exports.
60s: Show the chat re-export → same id demo beat.
Deep: hash preimage format, versioning of the scheme (gr-obj-v1 tag), SHA-256 collision stance.

**Q15. Complexity of your diff?**
15s: LCS over sentence hashes is O(n·m) with n,m = sentence counts — trivial at document scale; tree-sitter parse is linear.
60s: Numbers from perf smoke: 5k-sentence doc < 2s; discuss why sentence granularity beats line granularity for prose signal.
Deep: Myers vs LCS choice, move detection, alignment stability under heavy edit.

**Q16. What happens at 100k artifacts?**
15s: Not our demo scale; the honest answer: Postgres+pgvector, S3 blob store, Redis-backed CRDT sync, stateless API replicas — the design separates storage so the path is real.
60s: Walk the scale-up mapping component by component; note SQLite/Chroma embedded limits.
Deep: index sharding, op-log compaction, packfile analog.

**Q17. What changes for production?**
15s: Real auth+WS authz, multi-instance sync, Postgres, S3, OCR pipeline, richer claim extraction, audit mode.
60s: Prioritized list with what we'd keep exactly as-is (object model, alignment engine, merge semantics).
Deep: threat model (path traversal, malicious uploads, prompt injection from imported content) — see security section of README.

**Q18. What part is AI-generated?**
15s: Boilerplate — scaffolding, parsers, UI components, tests — under human-owned specs; every algorithm you just saw is deterministic code Muneer can whiteboard. The only runtime LLM is one labeled summary line, if it's there at all.
60s: Point at ownership matrix + ADR-14; explain the agent protocol (implement→test→adversarial→explain).
Deep: discuss verification strategy for agent code (invariant tests as the gate).

**Q19. Hardest engineering problem?**
15s: The sentence alignment engine being simultaneously right for diff, merge, and reindex — one primitive, three consumers, zero tolerance for nondeterminism.
60s: Concrete war story: threshold choice (0.7), convergent-edit rule, insert anchoring.
Deep: alternatives weighed, failure modes, test strategy.

**Q20. Why is your semantic diff meaningful — not just repackaged difflib?**
15s: It's structure-aware alignment with lineage: sentences keep identity across edits and moves, and that lineage feeds merge decisions and retrieval reindexing — difflib gives you text hunks, not identity.
60s: Show a moved paragraph detected as `moved`, an edit preserving sid lineage, and the chunk-level consequence.
Deep: sid scheme, hash normalization, where difflib IS used (similarity ratio only) and why that's honest.

**Q21. Is your CRDT "real" or a broadcast shim?**
15s: Real: pycrdt docs, yjs sync protocol with state vectors, persisted op log; proof = the shuffle-replay convergence property test, run live if you want.
60s: Explain why a shim fails (out-of-order/duplicate ops), show protocol frames.
Deep: room lifecycle, memory model, compaction story.

**Q22. Why not use git internally and layer semantics on top?**
15s: Because the semantic layer needs canonical identity and typed objects at the storage level — layered on git, every commit would still be a lie of byte identity, and we'd inherit line-diff as the merge substrate.
60s: The four wrapper-trap failures; what we borrowed deliberately (merkle DAG, refs, 3-way structure).
Deep: migration path (fast-export) if interop is ever required.

**Q23. How does retrieval avoid being a RAG chatbot?**
15s: No answer synthesis at all — cited evidence with version and provenance filters; the pipeline is query→keyword∪vector→version/provenance filter→rerank→citations.
60s: Run the as_of_commit demo; show delta reindex on a commit (only changed chunks re-embedded).
Deep: rerank weights, time-travel semantics via ancestry sets, honest limits.

**Q24. What did you cut and why?**
15s: Visual provenance graph, word-level diff3, multi-agent editing, OCR — cut to protect the two mandated moments and the invariant suite.
60s: Show the tier list (mvp-target-stretch.md) and the cut-offs we hit/missed honestly.
Deep: what each cut item would cost and what it would buy.
