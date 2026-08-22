# ADR-04: Diff Strategy (per artifact type)

- **Status: LOCKED** · Owner: Muneer (alignment engine), AI (chat/pdf adapters)

## Context / Problem
"Semantic human-readable diff, not byte diff" is 35%-pillar-critical and one of the two mandated demo moments. One algorithm cannot serve prose, code, chat, and PDFs.

## Decision: dispatch by artifact kind; one shared alignment primitive for prose-family

### Prose (md/txt): custom LCS over normalized sentence hashes
- Pipeline: split paragraphs (blank lines) → split sentences (hand-rolled deterministic regex splitter, ~40 LOC) → normalize (lowercase, strip punctuation, collapse whitespace) → hash (SHA1-16 of normalized form).
- Align: own LCS/Myers over hash sequences (~60 LOC, deterministic, no difflib autojunk).
- Classify aligned pairs: equal hash → unchanged; else `SequenceMatcher.ratio()` on raw text ≥ **0.7** → `edited` (keeps lineage); else delete+insert.
- Output: `[{sid, status: unchanged|edited|added|deleted|moved, old_text?, new_text?}]`; `sid = artifact:para_idx:sent_idx` at that commit.

### Code: tree-sitter function-level
- `tree-sitter` 0.26.x + `tree-sitter-python` wheels (precompiled, verified mature).
- Extract function/class nodes w/ byte spans + structural signature (name+params). Match by signature → equal token streams: no entry; different: Myers line-diff of function body only. Rename = signature-similarity match → `renamed` entry. Non-Python languages: line-diff fallback.
- Output entries `{kind: added|removed|modified|renamed, name, hunks}`.

### Chat (canonical message list): message/turn-level
- Align by (ordinal, role); compare text hashes; report added/removed/edited messages; never diff raw export JSON.

### PDF: page→paragraph structural
- Per page: blank-line paragraph blocks; prose alignment per page; report page-scoped paragraph changes.

## Why (runner-up: difflib.SequenceMatcher everywhere)
Decisive tradeoff: the alignment engine is shared by diff AND 3-way merge AND retrieval delta-reindex. Owning ~100 deterministic LOC that all three consume is the highest-ROI code in the project and is whiteboard-defensible; "we called difflib" is not. Tree-sitter for code because stdlib `ast` cannot distinguish formatting churn from logic change and judges expect the tool by name.

## Risks
Sentence splitter edge cases (abbreviations) — accepted crudeness, deterministic and documented. Tree-sitter only for Python at demo — flagged as scope.

## Reversibility
High: per-kind dispatch means any single differ can be swapped (e.g., add difflib fast path) without touching others.

## Consequences
- `core/diff/align.py` is THE shared primitive; `diff-spec.md` fixes exact output schemas; pytest asserts exact JSON on fixtures (determinism is a demo requirement).
