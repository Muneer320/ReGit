# Research Notebook — Optimizer Instability & Surface Codes

## Setting

We want an understanding, not just a fix, of training instability in deep
networks and the resource story of error-corrected quantum computing. The goal
is a single document that unifies what we learned from the simulation logs, the
LLM conversations, and the literature.

## Learning-rate divergence

Gradient descent diverges when the learning rate exceeds the local curvature
bound. We observed loss spikes at lr=0.1 on the quadratic benchmark with plain
SGD. The instability disappears with lr=0.01 across all seeds.

Adam mitigates but does not eliminate the spikes. Because Adam normalises the
per-parameter step, the effective step size is bounded even when the global
curvature is large, which is why the loss stays finite at lr=0.1. However, with
weight decay the coupling between decay and momentum can reintroduce the
instability at moderate decoupled-decay values.

A linear warmup from 0.01 to 0.1 over 200 steps removed the early spikes and
reached a lower final loss than any constant schedule, across batch sizes 64 to
512. This suggests the practical rule is warmup plus a conservative global lr,
not relying on the optimizer to absorb the divergence.

## Towards logical qubits

The surface code threshold sits near 1% under the code-capacity depolarising
model, but drops to roughly 0.4-0.6% under circuit-level noise. A neural decoder
can close the gap to the optimal threshold but does not raise the threshold
itself, because the threshold is a property of the code and the noise model.

The dominant cost for a 2048-bit Shor run at p=0.001 is the magic-state factory
and lattice-surgery routing, which scale faster than the logical data qubits.
Reducing factory overhead, either by better distillation or by using fewer
larger code patches, is the biggest lever in current resource estimates.

## Open questions

1. Does decoupled weight decay change the effective stability bound for Adam?
2. Can a warmup schedule generalise to transformer training at scale?
3. What is the crossover code distance where distillation overhead exceeds
   logical-data-qubit overhead?