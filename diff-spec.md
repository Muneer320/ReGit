# Diff Spec (LOCKED)

Owner: Muneer. Implements ADR-04. ALL differs emit the same Change schema (data-model.md). Determinism is contractual: same inputs → byte-identical JSON (pytest asserts exact output on fixtures).

## Prose (md/txt) — sentence/paragraph alignment
1. Paragraph split on blank lines; sentence split by deterministic regex splitter (documented crude abbreviations behavior).
2. Normalize: lowercase, strip punctuation, collapse whitespace → SHA1-16 hash per sentence.
3. LCS alignment (own Myers, ~60 LOC) over hash sequences.
4. Classification: equal hash → `unchanged`; aligned + ratio(raw) ≥ 0.7 → `edited`; else `deleted`+`added`. Paragraph moved → `moved` (same sid, new position).
5. Output: ordered `[Change]`; sid = `artifact:para:sent` at the FROM commit (added sentences get sid at the TO commit with status added).

## Code — tree-sitter function-level
1. Parse both versions (tree-sitter-python).
2. Extract function/class nodes: qualified name, param signature, byte span.
3. Match by signature → unchanged: no entry. Token-stream differs → `modified` with Myers line hunks of the body only.
4. Unmatched: `added`/`removed`; signature-similarity match (same params, similar body ≥0.6) → `renamed`.
5. Non-Python files: line-diff fallback, kind=`line`.

## Chat — message/turn level
Align canonical message lists by (ordinal, role); hash text; emit edited/added/deleted per message; `{span: "msg:12:assistant"}`.

## PDF — page/paragraph structural
Per page: paragraph blocks via blank-line split; prose alignment within page; span = `page:paraidx:sentidx`. Page added/removed reported.

## API + rendering
- `GET /diff?artifact_id&from&to` → `{kind, changes}`.
- UI: prose = two-pane colored alignment (green add, red del, amber edited); code = function cards with hunks; chat/pdf = list of change rows.
- Demo: `scripts/demo_semantic_diff.py` prints JSON + human rendering for fixtures (prose pair + code pair) in <1s.

## Non-goals
No word-level intra-sentence alignment in the structural diff (UI may highlight within an edited sentence, decorative). No cross-artifact diff (named next-build). No LLM paraphrase.
