# Problem Analysis — why Git works for code and fails for research

## 1. Why Git works so well for code

Git's design assumptions happen to match the physics of source code:

- **Line granularity ≈ semantic granularity.** In code, a line is usually a complete statement; a changed line is usually a changed meaning. Myers line-diff noise is low because authors already structure meaning into lines and blocks.
- **Files are independent-ish.** Cross-file coupling exists but is mediated by the compiler/linker; the VCS can treat files as opaque byte sequences and still be useful.
- **Identity is stable.** A function lives at a path; paths change rarely. Content addressing + path-keyed trees is a natural fit.
- **Merges are mostly textual.** Two branches editing different functions touch different lines; textual 3-way merge resolves the overwhelming majority of real cases, and where it fails, conflict markers in a code file are themselves compilable-adjacent text a programmer can fix.
- **History questions are simple.** "Who wrote this line" (blame), "what changed" (diff), "when did it break" (bisect) — all answerable from line-granular snapshots.

Git works because the *representation* (lines of text in files) is close to the *domain semantics* (statements in modules).

## 2. Why research behaves differently

Research artifacts violate every one of those assumptions:

- **Prose's semantic unit is the sentence/claim, not the line.** Reflowing a paragraph (pure formatting) changes every line and zero meaning. Splitting one sentence into two changes one line into two and one claim into two. Line-diff cannot distinguish these — so it destroys the signal researchers actually care about: *which claims changed*.
- **Research artifacts are heterogeneous in kind, not just in content.** A ChatGPT export, a Claude export, a PDF, a markdown hypothesis, and a code experiment have different internal grammars (message trees w/ branching, JSONL blocks, page text layers, prose, ASTs). Hashing raw bytes conflates "re-exported the same conversation with new volatile ids/timestamps" with "the content changed." Byte identity ≠ semantic identity.
- **Provenance is the product.** In code, authorship is metadata. In research, the chain *source → extracted claim → document that cites it* IS the value. "Where did this claim come from?" is a first-order query, and no VCS models it.
- **Knowledge state is temporal.** Researchers ask "what did we believe at commit X?" — a query over the *corpus-as-of-a-point-in-history*, not over one file. Git can check out a tree but cannot answer corpus-level questions over a historical snapshot.
- **Collaboration conflict is semantic, not textual.** Two researchers editing different sentences of the same paragraph can still be in semantic conflict (contradictory claims); two editing the same sentence to convergent text are not in conflict at all. Line-level merge gets both cases wrong.

## 3. Why linear histories are insufficient

- Research is **exploratory branching by nature**: hypotheses fork, dead ends are abandoned but must remain addressable ("we tried this, here's why it failed"), and literature reviews proceed in parallel threads that later merge. A linear history forces exploration to either overwrite itself or live outside the system.
- A single artifact's history being linear (a doc has versions 1..N) is fine; a *workspace's* knowledge state is a DAG — multiple threads (branches) whose snapshots must be mergeable, and merges create 2-parent commits. Any model that can't represent "these two research directions were reconciled here" loses the most interesting event in the process.
- Chat exports themselves are trees (ChatGPT's mapping has parent/children branching). Flattening to linear loses retry/edit branches — which are often where the interesting reasoning happened.

## 4. What conventional VCS destroys

1. **Sentence identity.** Line-based storage has no stable handle on "this sentence, which moved from ¶2 to ¶5" — so blame, move detection, and per-claim history are unrecoverable.
2. **Canonical form of chats.** Byte-hashing ChatGPT JSON makes two identical conversations different objects (volatile ids, timestamps, key order). Either dedup fails (bloat, phantom commits) or diffs lie.
3. **Provenance edges.** "Claim C derives from message M in chat X, page 3 of PDF Y" — no object represents this; it lives (and dies) in the researcher's head.
4. **The temporal corpus.** Conventional VCS answers per-file history. It cannot answer "show me everything we knew about topic T as of commit X" without an external index — and external indexes are built on `main` only, so history-aware retrieval is impossible.
5. **Merge intent.** Textual conflict markers record THAT two edits collided, not WHAT each side meant. Sentence-level merge records the base/ours/theirs triple per claim, which is reviewable by a researcher, not just a programmer.

## 5. The GitHub-wrapper trap

The trap: upload files → put them in a git repo → embed them → LLM chat search → pretty UI. It demos well for 90 seconds and scores near zero on depth because:
- the "versioning" is git's line-diff on prose (noise) and byte-hash on chat exports (lies);
- the "retrieval" is vanilla RAG that knows nothing about versions, branches, or provenance — it cannot answer "what did we know at X";
- "concurrency" is absent or a last-write-wins save button;
- "merge conflict" is git's text markers, which the team didn't design and can't explain beyond git's own docs;
- every hard question ("how do you merge prose? why is this immutable? where did this claim come from?") has the answer "git/the LLM does it" — i.e., the team built nothing.

**Minimum depth to escape the trap:** (1) own object model with typed artifacts and content addressing; (2) a diff/merge algorithm per artifact type that the team can whiteboard; (3) retrieval that filters by version/provenance; (4) provenance as a queryable primitive; (5) real concurrent editing with convergence guarantees. We build all five (see architecture.md and killer differentiators in demo-script.md §0).
