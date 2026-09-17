# Connector R3.2 event-substep experiment

This isolated source tree implements the registered first execution stop at N2.
It freezes the R3.1 law, audits the existing control API, validates the event
detector at N1, and runs the V1/R3 × fixed/event-aware single-connector
factorial at N2.  N3–N9 are deliberately not executed without a separate
review and authorization.

All generated artifacts are written to sibling `connector_r3_2_*` directories
under `revision_2026`.  Existing R3.1, V2, model, Koopman, data, and result
trees are read-only inputs.

