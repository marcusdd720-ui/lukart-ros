# Night Shift V2-07 — Controlled Mutation Canary

Status: VALIDATED STAGING CANDIDATE  
Recorded: 2026-09-28

## Objective

V2-07 is the first controlled step beyond read-only Shadow Night Shift.

It proves that Night Shift can perform a real mutation while preserving the existing
governance boundary:

- local-only;
- isolated task worktree;
- exact base SHA;
- R0/R1 only;
- AutonomyEnvelope required;
- durable authority budget required;
- lease and fencing token required;
- full VerificationQuorum required;
- all policy-defined failure-injection scenarios must have passing evidence;
- mutation scope and line/file budgets enforced;
- execution receipt content-addressed;
- rollback of the task worktree and branch verified;
- no push;
- no merge;
- no external publication;
- no unattended production promotion.

`ELIGIBLE_AUTO` in this stage means eligibility under policy, not permission to
publish the candidate outside the isolated local canary.

## Failure-injection prerequisite

The required scenario list is read from
`docs/execution_profiles/NIGHT_SHIFT_POLICY_V2.yaml`.

V2-07 fails closed if any required scenario is missing, duplicated, or failed.

The evidence manifest is
`docs/execution_profiles/NIGHT_SHIFT_FAILURE_EVIDENCE_V1.yaml`.

Required scenarios:

1. worker termination;
2. scheduler restart;
3. duplicate event;
4. stale worker resume;
5. network loss during push;
6. concurrent branch advance;
7. disk pressure;
8. corrupted receipt;
9. reviewer timeout.

For V2-07, network publication is structurally disabled. Therefore the
network-loss-during-push surface is eliminated rather than tolerated.

## Canary execution

Repository-owned command:

`python scripts/night_shift_controlled_canary.py`

The command creates a temporary synthetic Git repository, creates an isolated
Night Shift worktree from an exact SHA, performs one bounded text mutation,
creates a local commit, builds an execution receipt and then removes the
worktree and task branch.

The operator repository and any public remote are not mutated by the canary.

Expected proof:

- output SHA differs from input SHA inside the isolated canary;
- promotion state is `ELIGIBLE_AUTO`;
- `published=false`;
- rollback verification is true;
- failure-injection gate is complete;
- receipt digest is present.

## Promotion boundary

This stage does **not** enable unattended publication.

`night_shift.unattended_promotion_enabled` remains `false`.

The next autonomy increase requires independent evidence from repeated
controlled canary runs before any repository-owned R0 publication can be
considered.

Planned != Implemented != Validated != Certified.  
Evidence Before Conclusion.


## Validation evidence

Local validation before staging freeze:

- focused V2-07 tests: PASS;
- full Night Shift test set: PASS across 30 test files;
- Ruff: PASS;
- Mypy Linux target: PASS across 853 source files;
- repository audit: PASS;
- PII/confidentiality gate: PASS;
- secret scanning: PASS;
- repository-owned controlled canary CLI: PASS;
- observed canary promotion state: `ELIGIBLE_AUTO`;
- observed canary publication: `false`;
- observed rollback verification: `true`;
- observed failure-injection scenarios: 9/9 present and passing.
