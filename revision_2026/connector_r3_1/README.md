# Connector R3.1 evidence-repair workspace

This is an isolated post-R2 protocol revision. It does not overwrite the historical
`connector_r3` source or `connector_r3_results` evidence.

R3.1 keeps the R3 force law and the train-only frozen smoothing width unchanged. It
repairs the evidence chain by auditing train contact-speed support, activating the
damping energy test, sweeping contact sampling phase, and then checking whether the
frozen smoothing zone is resolvable at the 2 ms plant step.

The 12/15 kN values remain unverified numerical diagnostic thresholds, not measured
physical strength limits. Development and confirm data are forbidden throughout this
stage.

