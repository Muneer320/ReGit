# ADR-14: AI integration

- **Status: LOCKED** · Owner: Muneer (policy) · Amrit (enforcement in demo narrative)

## Decision
**No LLM in any correctness path. AI is used exactly two ways:**

1. **Build-time AI (agents):** boilerplate — API scaffolding from ../specs/api-contract.md, parsers, UI components, tests, fixtures, docs plumbing. Every agent-produced subsystem ships with an explanation Muneer can defend (per the AGENT CODING PROTOCOL: design → implement → test → adversarial test → explain → report).
2. **Run-time LLM: decorative only, optional, flagged.** At most a one-line natural-language diff summary in the diff view, clearly labeled "AI-generated summary", rendered alongside (never instead of) the deterministic structural diff. Built only in the H11 buffer if everything is green. Any API-key/network failure hides the label line; the demo is unchanged.

## Why (runner-up: LLM semantic diff / RAG answers)
Decisive tradeoff: LLM-in-the-path is the wrapper trap. It is nondeterministic (breaks our exact-output tests), unverifiable under hostile questioning, and destroys the "research-native VCS" story — the entire win condition is depth the LLM can't fake. Judges asking "what part is AI-generated?" get a crisp, honest answer: "the boilerplate and, if you see it, that one labeled summary line. Every diff, merge, version, and citation you see is a deterministic algorithm we can walk through."

## Human-owned vs AI-owned (enforced by ../planning/ownership-matrix.md)
- Human (Muneer): object model, hashing/canonicalization, DAG/merge-base, alignment engine, 3-way merge, CRDT integration semantics, provenance semantics, invariants.
- Human (Amrit): integration, UI composition, E2E flows, testing strategy execution, demo.
- AI: everything else mechanical, always with tests + explanation.

## Risks
Agent code that "compiles" but violates invariants → invariant tests are the gate; no merge without green. Explanation debt → Muneer reviews core modules against docs/ specs before H10.

## Consequences
../demo/judge-qa.md includes the "what did AI do?" answer; README has an AI-usage section mirroring this ADR.
