# Night Shift V2-21 — Runtime Shadow Activation Plan

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

Transform V2-20 verified runtime bindings into a bounded shadow-only activation plan.

This stage does not execute runtime work. It allocates at most one shadow task per
runtime and requires rollback for every execution.

## Authority boundary

- DBOS and Temporal only;
- one shadow task per runtime;
- shadow-only is mandatory;
- rollback is mandatory;
- production mutation is disabled;
- external publication is disabled;
- automatic promotion is disabled;
- READY_FOR_CONTROLLED_SHADOW_EXECUTION is not activation or certification.

Evidence Before Conclusion.
