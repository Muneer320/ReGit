Gradient descent diverges when the learning rate exceeds the local curvature bound. We observed loss spikes at lr=0.1 on the quadratic benchmark.

claim: Learning rate 0.1 causes divergence on the quadratic benchmark.

The instability disappears with lr=0.01 across all seeds. Adam mitigates but does not eliminate the spikes.
