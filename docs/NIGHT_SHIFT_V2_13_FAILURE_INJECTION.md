# Night Shift V2-13 — Failure Injection

Status: VALIDATED STAGING CANDIDATE
Recorded: 2026-09-28

## Objective

V2-13 turns the Night Shift failure catalogue into executable, deterministic probes
whose results are represented as content-addressed evidence and must pass before the
controlled local canary can execute.

Canonical rule:

`inject failure -> observe recovery/fail-closed behavior -> bind evidence to exact execution identity -> require complete current report`

Accepted outcomes:

- `RECOVERED`;
- `FAILED_CLOSED`.

Rejected outcome:

- `UNSAFE`.

## Required scenarios

The current controlled suite executes all 11 required scenarios:

1. worker termination during edit;
2. worker termination during validation;
3. scheduler restart after dispatch;
4. duplicate event delivery;
5. stale worker resumption;
6. network loss during push;
7. delayed CI;
8. concurrent branch advance;
9. disk pressure;
10. corrupted execution receipt;
11. reviewer timeout.

Each scenario emits a content-addressed evidence item containing:

- scenario identity;
- outcome;
- evidence reference;
- evidence digest.

## Failure Injection Report

The report is content-addressed and binds:

- exact subject Git SHA;
- exact LiveStateSnapshot digest;
- exact TaskCapsule digest;
- exact policy digest;
- exact failure-suite profile digest;
- generation time;
- expiry time;
- the complete ordered evidence set.

The report fails closed when:

- a required scenario is missing;
- an unexpected scenario is present;
- a duplicate scenario is present;
- any required scenario is UNSAFE;
- policy identity differs;
- suite-profile identity differs;
- subject SHA differs;
- state snapshot differs;
- TaskCapsule differs;
- the report is from the future;
- the report is expired;
- the report digest differs from the expected authority digest.

## Pre-freeze independent review hardening

Independent review found a replay-evidence gap: V2-13 originally bound the report to
policy, suite profile, TTL, and report digest, but not to the exact execution candidate.

That allowed a valid recent report for another task/candidate under the same policy to
be replayed within its validity window.

Remediation requires exact binding to:

- `subject_sha`;
- `state_snapshot_digest`;
- `task_capsule_digest`.

Controlled canary now verifies those three identities against the current state/task
before any promotion or mutation can proceed.

## Probe semantics

The V2-13 probes exercise existing control mechanisms rather than simulating a PASS:

- fencing/CAS blocks stale workers after lease replacement;
- workflow journal replay recovers durable states after restart;
- duplicate delivery is idempotent;
- outbox identity prevents duplicate push actions after network interruption;
- delayed CI remains WAITING_EXTERNAL instead of promoting;
- concurrent branch advance is detected;
- simulated disk pressure leaves protected content unchanged;
- receipt corruption is detected by digest verification;
- reviewer timeout leaves the verification quorum incomplete.

An exception inside a probe is converted into `UNSAFE` evidence instead of being
silently treated as a passing result.

## Controlled canary integration

Before the controlled canary mutates its isolated worktree it requires:

- a complete failure-injection report;
- exact report digest authority;
- pinned failure-suite profile digest;
- current policy digest;
- matching subject SHA;
- matching state snapshot digest;
- matching TaskCapsule digest;
- fresh report;
- all required scenarios in RECOVERED or FAILED_CLOSED state.

The report is evidence, not policy authority.

## Authority boundary

V2-13 does not:

- enable unattended production publication;
- expand TaskCapsule scope;
- expand the AutonomyEnvelope;
- bypass cryptographic verification;
- bypass Shadow Twin / Autonomy Debt controls;
- convert UNSAFE into an allowed outcome;
- claim external chaos-infrastructure certification.

The current suite is deterministic and local/control-plane oriented. Production-scale
distributed fault injection remains outside V2-13.

Planned != Implemented != Validated != Certified.
Evidence Before Conclusion.


## Validation evidence

Local validation before staging freeze:

- focused failure-gate / failure-injection / canary tests: PASS;
- exact subject SHA replay rejection: PASS;
- exact state snapshot replay rejection: PASS;
- exact TaskCapsule replay rejection: PASS;
- missing scenario rejection: PASS;
- unexpected scenario rejection: PASS;
- duplicate scenario rejection: PASS;
- UNSAFE scenario rejection: PASS;
- policy/profile mismatch rejection: PASS;
- report digest authority mismatch rejection: PASS;
- expired report rejection: PASS;
- all 11 executable failure probes: PASS with no UNSAFE outcomes;
- controlled canary failure-report integration: PASS;
- full Night Shift test set: PASS across 33 test files;
- Ruff: PASS;
- Mypy Linux target: PASS;
- repository audit: PASS;
- PII/confidentiality gate: PASS;
- secret scanning: PASS.
