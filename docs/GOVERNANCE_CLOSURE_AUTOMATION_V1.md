# GOV-AUTO-01 — Automated Governance Closure PR Preparation v1

Status: `CLOSED / ENGINEERING PASS`
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

GOV-AUTO-01 adds a bounded worker that prepares a closure PR only after it can reconstruct
fail-closed live evidence for the exact implementation merge. Capability is deliberately
split: the existing LUKART ROS GitHub App performs live evidence reads plus generated-branch
content writes, while the ephemeral workflow `GITHUB_TOKEN` is scoped only to the final
pull-request mutation.

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
15. creates a dedicated closure branch with the existing GitHub App;
16. writes the evidence and disables that stage's preparation target on the closure branch
    with the existing GitHub App;
17. opens a normal closure PR using only the job-scoped `GITHUB_TOKEN` with
    `pull-requests: write` and `contents: read`.

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

## 4. Split capability model

The first real post-merge dogfood proved that the existing LUKART ROS GitHub App can collect
live evidence, create the generated branch and write the evidence/disabled target, but its
installed permission set rejects `POST /pulls` with `403 Resource not accessible by
integration`. The repair therefore does not silently broaden the App or introduce a PAT.

Instead, capabilities are split by operation:

- **GitHub App:** Actions/evidence reads and Contents write for the generated closure branch;
- **workflow `GITHUB_TOKEN`:** `contents: read` plus `pull-requests: write`, used only for
  the final `POST /pulls` request;
- **no token:** merge, release, administration, secrets mutation, Product/CCL/Gold mutation
  or certification authority.

The scoped PR token must be present explicitly as `LUKART_ROS_CLOSURE_PR_TOKEN`; absence
fails closed before the pull-request request. The token is job-scoped/ephemeral and is not
persisted in repository state or generated evidence.

Repository/platform policy remains authoritative. If GitHub policy refuses Actions-created
pull requests or places the generated PR in a validation state that cannot traverse the
required exact-SHA gate, preparation is not treated as PASS and must be repaired or require
an explicit authorization change. The worker never bypasses such policy.

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
- inability to create the branch/evidence with the GitHub App;
- missing scoped closure-PR token;
- inability to create the closure PR under effective repository/platform policy.

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

### Broaden the existing GitHub App to Pull requests write

Not selected for the repair. The installed App capability boundary was observed directly and
changing it would require a separate authorization/configuration operation. The stage can
remain least-privilege without that change.

### Workflow `GITHUB_TOKEN` for all mutations

Rejected. It would unnecessarily replace the already working GitHub App content boundary and
increase coupling to workflow-token recursion semantics.

### Split App contents + scoped workflow PR mutation

Selected after dogfood evidence. It preserves the existing App for evidence/content work and
uses the shortest-lived available token only for the one capability the App demonstrably
lacks. Platform policy is still fail-closed and ordinary exact-SHA validation remains
mandatory.

### External SaaS/bot or PAT

Rejected. Both add avoidable credentials/provider trust surface for a capability available
inside GitHub Actions.

## 10. Validation and closure contract

GOV-AUTO-01 itself is not CLOSED until all of the following are proven:

- focused/adversarial unit tests PASS;
- existing GOV-01 and GitHub App client regressions PASS;
- Ruff/MyPy PASS;
- repository security/policy/full regression workflows PASS;
- exact implementation PR head is unchanged and all workflows are terminal SUCCESS;
- guarded implementation merge succeeds;
- resulting implementation `main` completes all post-merge workflows successfully;
- the preparation workflow **dogfoods itself** and opens the GOV-AUTO-01 closure PR from
  live GitHub evidence;
- the generated evidence exactly binds the validated implementation head/merge/baseline;
- the generated closure PR completes its own exact-head validation;
- canonical roadmap/Master Plan/this contract are updated on that same closure PR;
- guarded closure merge succeeds;
- resulting `main` completes post-merge validation;
- `v1.0.1` identity remains unchanged and no unintended release is published.

The first implementation merge may be followed by a repair PR when post-merge dogfood finds
a repairable integration defect. In that case only the repaired exact SHA and its subsequent
validation may support closure; the failed dogfood remains historical evidence and is not
reinterpreted as PASS.

No automated run can replace independent review where a later stage explicitly requires it.

## 11. Canonical closure evidence

GOV-AUTO-01 closed on the final repaired implementation line, not on either superseded
failed dogfood attempt.

- final implementation PR: `#181`;
- validated implementation head: `5119b0a7a199de1611f717afd2474fd877655514`;
- guarded implementation merge: `e2808ea3df7cd89a6161af328dbcc377ec914eb4`;
- final implementation exact-head CI: `14/14 SUCCESS`;
- implementation post-merge core: all required workflows terminal `SUCCESS` before closure
  preparation, including Stage Gate and `MVROS v1 Release`;
- successful self-dogfood workflow: run `34239_068144`, attempt `2` (underscore is a
  presentation separator for the repository PII gate; machine evidence retains run ID
  `34239068144`);
- generated closure PR: `#182`, created by `github-actions[bot]`;
- generated evidence:
  `evidence/governance_closure/gov-auto-01/e2808ea3df7cd89a6161af328dbcc377ec914eb4.json`;
- evidence identity:
  `38b686547103344597794a4df5d24928d08e4ca5d4961e8262650ed384fbc50b`;
- evidence result: `PREPARED_NOT_CLOSED` and authority `closure-preparation-only`;
- immutable baseline tag object:
  `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`;
- immutable baseline target commit:
  `802013c4d0e53dc12306a97e1877ebba86af64a7`;
- latest release observed during evidence collection: `v1.0.1`;
- next approved stage: `OPR-01`.

The first post-merge dogfood failed because the installed GitHub App lacked PR creation
permission. A least-privilege repair split branch/evidence writes from the final PR mutation.
A later dogfood then reached `POST /pulls` but GitHub repository policy refused Actions-created
PRs. After the repository setting **Allow GitHub Actions to create and approve pull requests**
was explicitly enabled, the exact same fail-closed path succeeded without broadening Product,
merge, release, CCL, Gold or certification authority.

The generated evidence intentionally remains `PREPARED_NOT_CLOSED`: it proves preparation,
not trust promotion. Stage closure still depends on this PR's own exact-head validation,
guarded merge and resulting-main post-merge validation. The `CLOSED / ENGINEERING PASS`
status in this canonical contract becomes effective only when those final closure gates are
successfully completed.