# Night Shift V2-11 — Causal Gate Graph

Status: VALIDATED STAGING CANDIDATE  
Recorded: 2026-09-28

## Objective

V2-11 makes failure causality a deterministic, evidence-bearing control rather than
a dashboard convention.

Canonical rule:

`FAIL_LOCAL(root) -> BLOCKED_BY(root) -> remediate root only`

The scheduler must not schedule downstream symptoms as independent remediation work.

## Reused foundation

V2-11 extends the existing Night Shift causal module. It does not introduce a second
graph database, second scheduler or competing state authority.

The graph is evidence. Policy remains authority.

## Graph contract

Every graph is canonical and content-addressed.

Required controls:

- unique gate IDs;
- `BLOCKED_BY` always carries a nonblank root-cause ID;
- a gate cannot block itself;
- the referenced root must exist in the same graph;
- the referenced root must be `FAIL_LOCAL`;
- graph ordering does not change graph identity;
- root impact sets are deterministic.

States such as `WAITING_EXTERNAL`, `POLICY_BLOCKED` or `UNKNOWN` cannot be
silently relabeled as local root causes.

## Remediation plan

The remediation plan is separately content-addressed and binds the exact graph digest.

The graph and remediation plan also bind the exact `state_snapshot_digest`. A causal
assessment from an older live-state snapshot therefore cannot be replayed as current
remediation evidence after repository/project state has changed.

For every `FAIL_LOCAL` root it records the exact downstream gate IDs blocked by that
root.

The plan exposes only local root failures as actionable IDs.

## Scheduler integration

`compile_root_cause_remediation_queue()` maps actionable root IDs to matching
`WorkItem.task_id` values.

Fail-closed controls:

- every actionable root requires a matching remediation task;
- duplicate task IDs are rejected;
- root remediation task must be READY;
- root remediation task cannot itself carry blockers;
- downstream `BLOCKED_BY` tasks are never returned as remediation work;
- ordering remains deterministic.

This is deliberately separate from the normal portfolio queue. V2-11 does not change
general task priority or resource budgets; it only prevents symptom fan-out during
failure remediation.

## Authority boundary

The Causal Gate Graph may not:

- expand TaskCapsule scope;
- create promotion authority;
- override AutonomyEnvelope;
- convert external/policy/unknown states into local failures;
- mutate Canonical Case Ledger or Product truth.

## V2-12 boundary

Shadow Twin and Autonomy Debt remain V2-12.

V2-11 only establishes deterministic causal failure identity and root-cause-first
remediation.

Planned != Implemented != Validated != Certified.  
Evidence Before Conclusion.


## Validation evidence

Local validation before staging freeze:

- focused causal graph and scheduler tests: PASS;
- duplicate gate-ID rejection: PASS;
- self-blocking rejection: PASS;
- missing/nonlocal root rejection: PASS;
- deterministic graph/remediation identity: PASS;
- invalid graph-digest rejection: PASS;
- invalid state-snapshot digest rejection: PASS;
- state-snapshot identity changes graph/remediation identity: PASS;
- stale causal graph replay boundary: PASS;
- downstream symptom exclusion from remediation queue: PASS;
- missing root remediation task rejection: PASS;
- blocked root remediation task rejection: PASS;
- full Night Shift test set: PASS across 33 test files;
- Ruff: PASS;
- Mypy Linux target: PASS across 861 source files;
- repository audit: PASS;
- PII/confidentiality gate: PASS;
- secret scanning: PASS.
