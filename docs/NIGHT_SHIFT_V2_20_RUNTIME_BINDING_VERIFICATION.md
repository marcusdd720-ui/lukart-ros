# Night Shift V2-20 — Runtime Binding Verification

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

Verify the V2-19 cryptographic proposal signature under the pinned trust set, then
verify that observed DBOS and Temporal bindings match that exact signed proposal and
come from one coherent adapter-registry snapshot and one coherent runtime-matrix
snapshot.

V2-20 is read-only. READY_FOR_SHADOW_ACTIVATION_PLAN does not activate a runtime.

## Fail-closed rules

- DBOS and Temporal observations are both required;
- proposal candidate digest must match exactly;
- binding identity, profile digest and adapter artifact digest must match exactly;
- registry snapshot must be coherent across both candidates;
- runtime matrix snapshot must be coherent across both candidates;
- test/synthetic/demo evidence is rejected;
- automatic registry/matrix mutation and runtime activation remain disabled.

Evidence Before Conclusion.
