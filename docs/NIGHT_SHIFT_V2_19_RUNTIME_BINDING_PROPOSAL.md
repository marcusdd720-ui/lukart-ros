# Night Shift V2-19 — Runtime Binding Proposal

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

Convert V2-18 adapter admission evidence into a deterministic, content-addressed
binding proposal for DBOS and Temporal.

The stage is advisory only. READY_FOR_HUMAN_SIGNATURE means the proposal is complete
enough for a cryptographic SECURITY_REVIEW attestation under a pinned trust set.
The attestation binds the exact proposal digest and repository SHA. V2-19 does not
mutate the adapter registry, runtime matrix, or activate a runtime.

## Fail-closed rules

- exact repository SHA must match V2-18 admission;
- DBOS and Temporal profiles must be unique and complete;
- every admission candidate must be READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE;
- profile digest must exactly match the admitted profile digest;
- concrete adapter artifact digest is mandatory;
- placeholder adapters are rejected;
- automatic registry mutation is disabled;
- automatic matrix mutation is disabled;
- automatic runtime activation is disabled.

Planned != Implemented != Validated != Certified.
Evidence Before Conclusion.
