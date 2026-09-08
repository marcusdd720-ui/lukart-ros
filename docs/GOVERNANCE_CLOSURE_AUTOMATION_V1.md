# GOV-AUTO-01 — Automated Governance Closure PR Preparation v1

Status: `ACTIVE / IMPLEMENTATION`
Authority: preparation/orchestration only
Canonical execution standard: `docs/WORKING_PRINCIPLES.md`
Canonical live state authority: GitHub
Existing governance consistency authority: `core/governance_closure_v1.py`
Next approved stage after closure: `OPR-01`

## 1. Problem

Post-v1 closure currently requires an engineer/agent to repeatedly collect the same live
GitHub evidence after an implementation merge: validated PR head, implementation merge,
required PR workflows, post-merge workflows, immutable baseline identity and release state.
That manual collection is correct but repetitive and creates avoidable transcription,
stale-SHA and evidence-mixing risk.

The improvement must automate only preparation. It must not turn automation into a new
governance authority and must not allow `Candidate -> CLOSED` without the existing
exact-SHA CI, guarded merge and post-merge validation chain.

## 2. Decision

GOV-AUTO-01 adds a bounded GitHub App worker that prepares a closure PR only after it can
reconstruct fail-closed live evidence for the exact implementation merge.

The worker:

1. runs after the existing `MVROS v1 Release` guard completes successfully on `main`
   or through an explicit recovery `workflow_dispatch`;
2. checks out the exact source merge SHA from that run;
3. reads `config/closure_preparation_target.json`;
4. skips without mutation when the target is disabled;
5. requires live `main` to still equal the exact implementation merge SHA;
6. requires the configured implementation PR to be merged at that exact merge SHA;
7. requires the validated PR head to be a direct merge parent;
8. requires every observed exact-head PR workflow to be terminal `success`;
9. requires the fixed GOV-01 workflow registry to be present;
10. requires every observed post-merge workflow, excluding the preparation run itself,
    to be terminal `success`;
11. requires the fixed post-merge core, including Stage Gate and release guard, to exist;
12. verifies the immutable `v1.0.1` annotated tag target and latest release state;
13. delegates governance consistency verification to `core/governance_closure_v1.py`;
14. emits content-addressed machine-readable evidence;
15. creates a dedicated closure branch;
16. writes the evidence and disables that stage's preparation target on the closure branch;
17. opens a normal closure PR through the existing LUKART ROS GitHub App.

The generated PR is explicitly marked:

`PREPARED / NOT CLOSED`

## 3. Authority boundary

The automation has **no merge authority** and no authority to:

- claim `CLOSED / ENGINEERING PASS`;
- weaken, skip or reinterpret CI;
- bypass exact-head validation;
- change the implementation merge identity;
- publish or move a release/tag;
- modify Product, CCL, Gold or epistemic truth;
- manufacture independent review or certification;
- silently update arbitrary governance prose.

The closure PR still requires stage-specific canonical documentation updates, complete
exact-head CI, a head/base drift check, guarded exact-head merge and post-merge validation.

## 4. Why GitHub App instead of `GITHUB_TOKEN`

A pull request opened by the repository GitHub App is intended to enter the ordinary PR
validation path. The worker does not use the workflow `GITHUB_TOKEN` as a fallback mutation
authority because platform anti-recursion rules can prevent ordinary downstream workflow
events from being created by that token. A missing GitHub App write capability fails closed
instead of silently creating a weaker validation path.

Required App capabilities for live preparation are intentionally narrow:

- Actions read for workflow evidence;
- Contents write for one generated closure branch;
- Pull requests write for opening the closure PR.

No administration, secrets mutation or release permission is required by this worker.

## 5. Target contract and recursion control

`config/closure_preparation_target.json` is an orchestration target, not closure truth.

For an implementation stage it declares:

- schema;
- enabled flag;
- exact stage ID;
- next approved stage;
- implementation PR number;
- architecture-contract path.

The implementation PR enables its own target. The generated closure PR changes only the
target flag from `true` to `false` before opening the PR. Therefore the eventual closure
merge does not recursively prepare another closure PR for the already closed stage.

A future stage opts into automation by replacing the target with its own exact stage/PR/next
stage data in that stage's implementation PR.

## 6. Evidence contract

`ClosurePreparationEvidenceV1` is deterministic and content-addressed. It binds:

- stage and next-stage identities;
- implementation PR;
- validated implementation head SHA;
- implementation merge SHA and direct parents;
- all observed exact-head PR workflow run IDs/names/events/outcomes;
- all observed post-merge workflow run IDs/names/events/outcomes;
- immutable baseline annotated-tag object and target commit;
- latest release tag;
- GOV-01 live-snapshot identity;
- GOV-01 consistency-report identity;
- explicit authority `closure-preparation-only`;
- result `PREPARED_NOT_CLOSED`.

The evidence identity is SHA-256 over canonical JSON. Dynamic wall-clock timestamps are not
part of the identity.

## 7. Failure semantics

Preparation fails closed on, among other conditions:

- malformed stage or Git identity;
- disabled target passed into collection;
- live-main drift;
- unmerged or substituted implementation PR;
- merge/head mismatch;
- missing merge parent;
- missing canonical PR workflow;
- any observed non-success PR workflow;
- missing required post-merge workflow;
- any observed non-success post-merge workflow;
- baseline tag/target drift;
- latest-release drift;
- malformed GitHub API responses;
- inability to create the branch/evidence/PR with the GitHub App.

Pending or not-yet-created required post-merge evidence is polled within a bounded timeout.
A terminal failed/cancelled/skipped workflow is not retried into PASS by this worker.

## 8. Recovery and idempotency boundary

Each preparation run creates a run-identity-qualified branch:

`closure/<stage>-<merge-prefix>-r<run-id>-a<run-attempt>`

This avoids unsafe overwrite of evidence from a partially failed prior preparation attempt.
A failed attempt never mutates `main`; its branch/PR is ordinary recoverable GitHub state.
No generated branch is treated as closure evidence until its PR completes the normal
validation/merge/post-merge lifecycle.

## 9. Alternatives considered

### Fully automatic closure and merge

Rejected. It would collapse preparation, validation and trust promotion into one capability
and increase blast radius.

### Workflow `GITHUB_TOKEN` PR creation

Rejected as the primary mutation path. Platform event-recursion semantics can prevent the
generated PR from traversing the same ordinary workflow path expected from normal changes.

### External SaaS/bot

Rejected. It adds provider lock-in, credentials and an unnecessary external trust surface.

### Existing GitHub App + GOV-01 verifier

Selected. It reuses current authenticated infrastructure and the existing consistency
contract, adds no competing governance truth source and remains auditable/recoverable.

## 10. Validation and closure contract

GOV-AUTO-01 itself is not CLOSED until all of the following are proven:

- focused/adversarial unit tests PASS;
- existing GOV-01 and GitHub App client regressions PASS;
- Ruff/MyPy PASS;
- repository security/policy/full regression workflows PASS;
- exact implementation PR head is unchanged and all workflows are terminal SUCCESS;
- guarded implementation merge succeeds;
- resulting implementation `main` completes all post-merge workflows successfully;
- the newly installed preparation workflow **dogfoods itself** and opens the
  GOV-AUTO-01 closure PR from live GitHub evidence;
- the generated evidence exactly binds the implementation head/merge/baseline;
- the generated closure PR completes its own exact-head validation;
- canonical roadmap/Master Plan/this contract are updated on that same closure PR;
- guarded closure merge succeeds;
- resulting `main` completes post-merge validation;
- `v1.0.1` identity remains unchanged and no unintended release is published.

No automated run can replace independent review where a later stage explicitly requires it.
