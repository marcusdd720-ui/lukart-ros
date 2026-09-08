# GOV-01 — Governance Closure Consistency v1

Status: `CLOSED / ENGINEERING PASS`
Authority: governance verification only
Depends on: `PVE-01 CLOSED / ENGINEERING PASS`
Live repository SSOT: GitHub
Implementation PR: `#166`
Validated PR head: `07256f90282de080a19bca32d40c28fe10406ac5`
Implementation merge: `main @ 54245df8f834661c9d36a522e46952a20a095c0f`
Next approved stage: `KQM-03`

## Problem

Earlier closure work exposed a concrete governance drift failure mode: implementation and
exact-SHA CI could already be closed while `MASTER_PLAN.md` or the active roadmap remained
stale. Repository text must describe verified state accurately, but it must not become a
competing authority for live PR, SHA, CI, merge, tag or release state.

GOV-01 therefore validates a canonical closure declaration against an independently observed
live-evidence snapshot. The verifier has no network or mutation capability; acquisition of
live GitHub evidence remains an execution-time step outside the pure contract.

## Decision

`core/governance_closure_v1.py` defines three immutable data contracts:

- `GovernanceLiveSnapshotV1` — externally observed PR/merge/CI/baseline evidence;
- `GovernanceClosureRecordV1` — the closure declaration governance intends to record;
- `GovernanceConsistencyReportV1` — content-addressed proof that the two agree under the v1
  contract.

The report means only `CONSISTENT`. It is not Product truth, release authorization,
certification or independent review.

## Fixed workflow contract

GOV-01 v1 requires exactly the repository's eleven PR validation workflows:

1. Architectural Audit 1.0
2. CI Foundation
3. Enterprise CodeQL
4. Enterprise Hardcore Gate
5. GitHub App Smoke Test
6. P2 Semantic Intelligence
7. P3 Hardcore Hardening
8. Post-v1 v1.1
9. Production Validation Program
10. Stage Gate
11. Stage Orchestrator

The caller cannot remove a workflow to manufacture PASS. Missing, duplicate, extra or
non-success workflow evidence fails closed. A future workflow contract requires an explicit
new version rather than silently changing v1 semantics.

## Identity and ancestry

The live snapshot and closure record bind:

- stage ID;
- implementation PR number;
- validated PR-head SHA;
- resulting merge SHA;
- direct merge-parent identities sufficient to prove the validated head participated in the
  merge;
- exact required PR workflow evidence;
- post-merge success/non-success counts;
- immutable historical baseline tag-object identity;
- immutable baseline target-commit identity.

Git object IDs must be canonical lowercase 40-character hex. The validated head must appear
as a direct merge parent in the supplied live snapshot. A moved head, stale merge identity or
baseline drift fails closed.

## Authority boundary

GOV-01 deliberately does not call GitHub itself. The live snapshot must originate from an
external GitHub read performed at closure time. This keeps the boundary explicit:

`GitHub live state -> evidence snapshot -> GOV-01 verifier -> consistency report`

`MASTER_PLAN.md` and roadmap declarations are compared against evidence; they are never used
to manufacture the evidence snapshot that validates them.

GOV-01 has no:

- CCL write path;
- Product epistemic or Gold authority;
- network client;
- merge or release mutation capability;
- CI bypass;
- independent-review or certification authority.

## Fail-closed conditions

At minimum GOV-01 rejects:

- unsupported schema;
- malformed Git SHA;
- missing, duplicate or unexpected required workflow;
- failed/cancelled required workflow;
- any non-success post-merge state in the closure snapshot;
- validated head absent from merge parents;
- stage or PR mismatch;
- stale validated-head or merge SHA;
- historical baseline tag-object drift;
- historical baseline target-commit drift;
- a closure that reactivates the same stage as its next stage.

No partial PASS report is produced.

## Validation plan

Focused and adversarial tests cover deterministic happy-path verification, fixed-registry
reduction attempts, duplicate/failed workflows, post-merge non-success, moved head,
stale/cross-stage substitutions, merge mismatch, baseline drift, malformed identity and
unknown schema.

Closure requires full repository regression, lint/type/security/policy gates, all required
workflows on one exact PR-head SHA, guarded unchanged-head merge, terminal resulting-main
validation, baseline/release side-effect checks and canonical governance evidence.

Engineering closure will not assert independent external certification.

## Exact live closure evidence

Observed GitHub state used for GOV-01 closure:

- implementation PR: `#166`;
- validated PR head: `07256f90282de080a19bca32d40c28fe10406ac5`;
- base at merge: `3a5f57e113bae8cca57d4e5d7f9f8d8b4620bd21`;
- resulting merge: `54245df8f834661c9d36a522e46952a20a095c0f`;
- merge parents: `3a5f57e113bae8cca57d4e5d7f9f8d8b4620bd21`,
  `07256f90282de080a19bca32d40c28fe10406ac5`;
- required PR workflows: `11/11 SUCCESS`;
- post-merge workflows: `9 SUCCESS`, `0 non-success`;
- historical `v1.0.1` tag object:
  `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`;
- historical `v1.0.1` target commit:
  `802013c4d0e53dc12306a97e1877ebba86af64a7`;
- no new release was published as part of GOV-01 closure;
- next approved stage: `KQM-03`.

Content-addressed GOV-01 verification identities for that exact externally observed snapshot:

- live snapshot identity:
  `6d48def33e722e413a37d8fa8992bf9b305b2ac0d601400b76af7838a478e175`;
- closure record identity:
  `7da55b77321466b968d3d1c033bc6e0bd2a63a96b8f7b05d911582bf581cfe23`;
- consistency report identity:
  `1108992adad36b901667281eecf2a142e7490193f948d07c17d8a6226c3e9536`;
- result: `CONSISTENT`;
- authority: `governance-verification-only`.

This closure records engineering evidence only and does not claim independent external
certification.