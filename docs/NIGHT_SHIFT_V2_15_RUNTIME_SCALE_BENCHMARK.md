# Night Shift V2-15 — Runtime Scale Benchmark

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

V2-15 evaluates DBOS and Temporal as future scale-runtime candidates without changing runtime authority.

Canonical sequence:

`authoritative runtime profile -> exact profile digest -> independent benchmark samples -> requirement evaluation -> READY_FOR_HUMAN or BLOCKED`

## Benchmark boundary

- candidates are exactly DBOS and Temporal;
- automatic runtime promotion is forbidden;
- each candidate must have a concrete adapter;
- runtime profile evidence must already be VALIDATED;
- every sample is bound to the exact runtime profile digest;
- sample identities must be unique;
- minimum sample count is enforced per runtime;
- stale or unknown profile bindings fail closed;
- unmet observed requirements reject that runtime;
- benchmark output is advisory evidence only.

## Evidence semantics

A READY_FOR_HUMAN result does not select, install, enable, or promote a runtime. It only means at least one candidate has complete benchmark evidence for the requested requirements and can be reviewed by a human.

A BLOCKED result is required when candidate evidence is incomplete or no runtime satisfies the scale requirements.

Duplicated sample identity is invalid because repeated observations must not inflate evidence count.

## Authority boundary

V2-15 does not:

- install DBOS or Temporal;
- create a new runtime adapter;
- claim benchmark evidence that was not observed;
- promote DOCUMENTED evidence to VALIDATED;
- change the Night Shift runtime automatically;
- enable external or unattended production publication;
- treat benchmark readiness as production certification.

Planned != Implemented != Validated != Certified.
Evidence Before Conclusion.
