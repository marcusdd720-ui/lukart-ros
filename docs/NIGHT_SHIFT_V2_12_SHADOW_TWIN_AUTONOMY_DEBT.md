# Night Shift V2-12 — Shadow Twin + Autonomy Debt

Status: VALIDATED STAGING CANDIDATE  
Recorded: 2026-09-28

## Objective

V2-12 converts shadow mode from a reporting convention into a deterministic,
content-addressed control that calibrates autonomous execution against observed outcomes.

Canonical rule:

`predict before execution -> observe actual result -> compare exact identity -> account divergence -> gate autonomy`

Shadow evidence does not create policy authority. It can only reduce or preserve the
autonomy already allowed by the existing AutonomyEnvelope and promotion policy.

## Shadow Twin contract

Every prediction binds:

- task ID;
- repository;
- exact subject Git SHA;
- exact LiveStateSnapshot digest;
- exact TaskCapsule digest;
- exact policy digest;
- executor class;
- expected terminal state;
- prediction time;
- prediction expiry.

Every observation binds the same identity dimensions plus the actual executor class
and actual terminal state.

Calibration fails closed when:

- task/repository/SHA/state/task/policy identity differs;
- observation predates prediction;
- observation is made after prediction expiry.

## Divergence classes

V2-12 distinguishes:

- `EXACT_MATCH` -> debt delta -1;
- `EXECUTOR_DIVERGENCE` -> debt delta +1;
- `TERMINAL_DIVERGENCE` -> debt delta +2;
- `EXECUTOR_AND_TERMINAL_DIVERGENCE` -> debt delta +3.

Debt never falls below zero.

The debt model is deliberately conservative about terminal-state divergence because
an executor-path difference with the same result is less severe than a result mismatch.

## Autonomy Debt Ledger

The ledger is repository- and policy-bound and content-addressed.

Controls:

- opening debt cannot be negative;
- duplicate calibration evidence is rejected;
- foreign repository calibration is rejected;
- foreign policy calibration is rejected;
- debt value is derived deterministically from ordered evidence;
- sample count is derived from accounted calibration events;
- the downgrade threshold is explicit;
- minimum shadow samples for AUTO are explicit.

An exact shadow match may retire one unit of accumulated debt but never reduces the
ledger below zero.

## Promotion clearance

A ShadowPromotionClearance binds:

- repository;
- exact subject SHA;
- exact TaskCapsule digest;
- exact autonomy-debt ledger digest;
- debt value;
- downgrade threshold;
- sample count;
- minimum sample threshold;
- issuance time;
- expiry time.

AUTO/PREAUTHORIZED promotion now requires an independently supplied expected
autonomy-debt ledger digest. A clearance with a missing or mismatched ledger authority
fails closed.

This prevents a manually constructed clearance with attractive debt/sample values from
being accepted merely because its own fields are internally consistent.

Promotion behavior:

- missing clearance -> READY_FOR_HUMAN;
- insufficient samples -> READY_FOR_HUMAN;
- debt at or above threshold -> READY_FOR_HUMAN;
- expired clearance -> BLOCKED;
- repository/SHA/task mismatch -> BLOCKED;
- missing expected ledger authority -> BLOCKED;
- ledger digest mismatch -> BLOCKED.

## Controlled canary integration

The repository-owned controlled canary:

1. creates deterministic shadow predictions;
2. records matching observations;
3. updates the autonomy-debt ledger;
4. issues clearance from that exact ledger;
5. passes the exact ledger digest separately as promotion authority evidence;
6. performs cryptographically verified promotion evaluation;
7. remains local-only and unpublished.

Observed successful canary behavior must continue to satisfy:

- `ELIGIBLE_AUTO`;
- `published=false`;
- rollback verified;
- cryptographic verification PASS;
- shadow sample count >= minimum;
- debt below downgrade threshold.

## Authority boundary

V2-12 does not enable unattended production publication.

`night_shift.unattended_promotion_enabled` remains false.

The Shadow Twin and Autonomy Debt subsystem may not:

- expand TaskCapsule scope;
- override the AutonomyEnvelope;
- override risk-class policy;
- bypass cryptographic verification;
- bypass exact-SHA verification;
- mutate product/case truth;
- claim a production-certified durable external ledger authority.

The expected ledger digest is now mandatory for promotion, but production-grade
durable external ledger custody/certification is not claimed by V2-12.

## Next boundary

The next autonomy stage should focus on durable shadow/debt authority and measured
multi-run operational evidence before any increase in publication authority.

Planned != Implemented != Validated != Certified.  
Evidence Before Conclusion.


## Validation evidence

Local validation before staging freeze:

- focused Shadow Twin / promotion / canary tests: PASS;
- shadow identity mismatch regressions: PASS;
- prediction temporal-order regressions: PASS;
- duplicate calibration rejection: PASS;
- foreign repository/policy calibration rejection: PASS;
- minimum-sample promotion downgrade: PASS;
- autonomy-debt threshold downgrade: PASS;
- clearance expiry rejection: PASS;
- missing ledger authority rejection: PASS;
- forged/mismatched ledger digest rejection: PASS;
- controlled canary Shadow Twin integration: PASS;
- full Night Shift test set: PASS across 33 test files;
- Ruff: PASS;
- Mypy Linux target: PASS across 861 source files;
- repository audit: PASS;
- PII/confidentiality gate: PASS;
- secret scanning: PASS.
