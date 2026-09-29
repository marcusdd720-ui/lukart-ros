# Night Shift V2-18 — Runtime Adapter Admission Boundary

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

V2-18 closes the gap between documented future runtime profiles and a future
signed adapter-binding change.

Canonical flow:

`concrete adapter artifact -> exact content identities -> exact repository SHA -> conformance runs -> READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE or BLOCKED`

This stage does not install DBOS or Temporal and does not mutate the runtime
matrix or executor adapter registry.

## Admission requirements

- candidates remain exactly DBOS and Temporal;
- canonical placeholder adapter identities `future_*` remain fail-closed;
- a concrete adapter artifact must have a non-placeholder adapter name;
- adapter source identity is content-addressed;
- dependency-lock identity is content-addressed;
- artifact and conformance evidence are bound to an exact repository SHA;
- test/synthetic/demo evidence cannot satisfy either artifact or conformance admission;
- at least three distinct conformance runs are required per runtime;
- conformance run identities must be globally unique;
- conformance evidence digests must be unique;
- every required capability declared by the runtime profile must pass;
- stale artifact bindings and stale repository bindings fail closed.

## Authority boundary

`READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE` is not a runtime promotion and is
not a VALIDATED runtime state.

V2-18 does not:

- write `NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml`;
- write `NIGHT_SHIFT_EXECUTOR_ADAPTERS_V1.yaml`;
- install DBOS or Temporal;
- expose a new runtime implementation to execution;
- select a runtime;
- increase runtime or publication authority;
- enable unattended production publication.

The current canonical state remains BLOCKED because DBOS and Temporal still use
placeholder adapter identities and no canonical concrete adapter artifacts are
present.

A later separately reviewed and signed change is required before any adapter
binding or runtime-matrix mutation.

Evidence Before Conclusion.
Planned != Implemented != Validated != Certified.
Factory != Product.
