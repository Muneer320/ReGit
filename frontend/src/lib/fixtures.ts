// Demo fixtures. scripts/fixtures/merge/*.md verbatim (merge-spec.md fixture
// set: both sides edit sentence 2 differently -> exactly one conflict card)
// plus a research-prose seed document for the workspace/search demo.

export const FIXTURE_BASE = `Gradient descent diverges when the learning rate exceeds the local curvature bound. We observed loss spikes at lr=0.1 on the quadratic benchmark.

claim: Learning rate 0.1 causes divergence on the quadratic benchmark.

The instability disappears with lr=0.01 across all seeds. Adam mitigates but does not eliminate the spikes.
`

export const FIXTURE_OURS = `Gradient descent diverges when the learning rate exceeds the local curvature bound. We observed loss spikes at lr=0.1 on the quadratic benchmark and at lr=0.05 on deeper models.

claim: Learning rate 0.1 causes divergence on the quadratic benchmark.

The instability disappears with lr=0.01 across all seeds. Adam mitigates but does not eliminate the spikes.
`

export const FIXTURE_THEIRS = `Gradient descent diverges when the learning rate exceeds the local curvature bound. We observed oscillations, not spikes, at lr=0.1 on the quadratic benchmark.

claim: Learning rate 0.1 causes divergence on the quadratic benchmark.

The instability disappears with lr=0.01 across all seeds. Adam mitigates but does not eliminate the spikes.
`

/** Seed artifact used by "Load demo data" (workspace + search corpus). */
export const DEMO_DOC_TITLE = 'optimization-notes.md'
export const DEMO_DOC_V1 = `# Optimization Notes

## Learning-rate stability

Gradient descent diverges when the learning rate exceeds the local curvature bound. We observed loss spikes at lr=0.1 on the quadratic benchmark.

claim: Learning rate 0.1 causes divergence on the quadratic benchmark.

The instability disappears with lr=0.01 across all seeds. Adam mitigates but does not eliminate the spikes.

## Convergence theory

For convex objectives the convergence rate of plain gradient descent is O(1/k). Momentum methods accelerate this to O(1/k^2) under strong convexity assumptions.

claim: Momentum achieves O(1/k^2) convergence on strongly convex objectives.

Nesterov's accelerated gradient remains the reference method for smooth convex problems.

## Surface-code context

Quantum error correction uses surface-code approaches to reduce logical error rates. The threshold theorem guarantees that below a critical physical error rate, increasing code distance suppresses logical errors exponentially.

claim: Surface codes suppress logical errors exponentially below the threshold error rate.

Recent experiments demonstrate distance-7 surface codes outperforming repetition codes on superconducting hardware.
`

/** A plausible "second direction" edit committed on a feature branch. */
export const DEMO_DOC_V2 = `# Optimization Notes

## Learning-rate stability

Gradient descent diverges when the learning rate exceeds the local curvature bound. We observed loss spikes at lr=0.1 on the quadratic benchmark and at lr=0.05 on deeper transformer models.

claim: Learning rate 0.1 causes divergence on the quadratic benchmark.

The instability disappears with lr=0.01 across all seeds. Adam mitigates but does not eliminate the spikes. Warmup schedules remove the remaining transient spikes in practice.

## Convergence theory

For convex objectives the convergence rate of plain gradient descent is O(1/k). Momentum methods accelerate this to O(1/k^2) under strong convexity assumptions.

claim: Momentum achieves O(1/k^2) convergence on strongly convex objectives.

Nesterov's accelerated gradient remains the reference method for smooth convex problems.

## Surface-code context

Quantum error correction uses surface-code approaches to reduce logical error rates. The threshold theorem guarantees that below a critical physical error rate, increasing code distance suppresses logical errors exponentially.

claim: Surface codes suppress logical errors exponentially below the threshold error rate.

Recent experiments demonstrate distance-7 surface codes outperforming repetition codes on superconducting hardware.
`
