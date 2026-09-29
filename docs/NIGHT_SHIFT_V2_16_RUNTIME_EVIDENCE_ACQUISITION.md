# Night Shift V2-16 — Runtime Evidence Acquisition Gate

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

V2-16 defines the fail-closed boundary between DOCUMENTED runtime capability and evidence that may be submitted for human VALIDATED review.

The gate does not install, select, promote or certify DBOS or Temporal.

Canonical flow:

`documented profile -> concrete adapter -> exact-profile sample -> content-addressed run evidence -> acquisition gate -> READY_FOR_HUMAN_VALIDATION or BLOCKED`

## Required evidence

- candidates remain exactly DBOS and Temporal;
- adapter identity must be concrete and match the profile;
- adapter version must be explicit;
- every run binds the exact runtime profile digest;
- every run binds an exact V2-15 benchmark sample digest;
- run IDs are globally unique;
- the minimum threshold is three accepted runs per runtime and cannot be lowered by a caller;
- minimum evidence requires distinct sample digests;
- minimum evidence requires distinct artifact digests;
- environment identity is a lowercase SHA-256 content address;
- evidence artifact identity is a lowercase SHA-256 content address;
- `test:`, `synthetic:` and `demo:` evidence namespaces are mandatory forbidden prefixes and cannot be removed by a caller;
- synthetic runs are rejected explicitly;
- stale profile/sample binding fails closed.

## Authority boundary

`READY_FOR_HUMAN_VALIDATION` means only that the acquisition package is complete enough for independent human/repository review.

V2-16 does not:

- mutate `RuntimeProfile.evidence`;
- change DOCUMENTED to VALIDATED automatically;
- change runtime selection;
- change production authority;
- enable unattended publication;
- treat acquisition completeness as certification.

A later, separately reviewed and signed change is required before the canonical runtime matrix may claim VALIDATED evidence for DBOS or Temporal.

## Current expected state

With `future_dbos_adapter` and `future_temporal_adapter`, the canonical matrix must remain BLOCKED at V2-16. This is correct behavior, not a test failure.

Evidence Before Conclusion.
Planned != Implemented != Validated != Certified.
