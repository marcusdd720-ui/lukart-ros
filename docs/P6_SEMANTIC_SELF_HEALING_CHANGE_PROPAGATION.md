# P6 — Semantic Self-Healing & Change Propagation

Status: IMPLEMENTED / VALIDATION PENDING

## Decision need

Factory already contains deterministic operational self-healing primitives for stage failures,
including log classification, formatting-safe Ruff repair, and safe rollback. P6 must not duplicate
that mechanism. It must add a Product-level semantic control plane that can answer:

1. what measured KQM failure occurred and what evidence supports a root-cause diagnosis;
2. which Product component is implicated;
3. which downstream components require revalidation;
4. whether selective revalidation is justified by a completeness-certified dependency graph;
5. whether a proposed repair is still an ordinary P4 Learning Candidate rather than a mutation
   authority;
6. whether the repair was replayed and measured on a genuinely fresh SHA;
7. whether the repair may continue through the existing P4 promotion/release path.

The P6 v1 loop is:

`Measured Failure -> Semantic Diagnosis -> Impact Graph -> Revalidation Plan -> P4 Learning Candidate -> Experiment -> Fresh-SHA Replay/KQM Evidence -> P4 Promotion Decision -> P6 Readiness`

P6 is fail-closed. It never patches, commits, merges, deploys, or promotes Product state.

## P6.1 — Evidence-bound semantic diagnosis

`SemanticFailureDiagnoser` uses curated exact-match `DiagnosisRule` contracts keyed by
`LearningSource + failure_code`. A diagnosis is bound to the exact `MeasuredFailure.digest()` and
always carries the KQM result/report digests as evidence.

If no curated rule matches, the result is `INCONCLUSIVE` with `UNKNOWN` root cause and no guessed
target component. Ambiguous duplicate mappings are rejected at diagnoser construction time.

## P6.2 — Explicit dependency graph

`ComponentDependencyGraph` is an immutable directed acyclic graph of Product components and the
validators required for each component. Edges mean semantic downstream impact, not import syntax.

A graph may declare `complete=True` only with a SHA-256 completeness-evidence artifact. Unknown
components, duplicate edges, self-dependencies, and cycles are rejected.

This is intentionally separate from repository import analysis. Code imports are useful evidence,
but they are not equivalent to semantic Product dependencies.

## P6.3 — Selective vs broad revalidation

`plan_revalidation()` permits `SELECTIVE` propagation only when:

- semantic diagnosis is conclusive;
- diagnosed target exists in the graph;
- graph declares completeness and carries completeness evidence.

The selective plan contains the changed component plus its full transitive downstream closure and
the union of their declared validators.

Any inconclusive diagnosis, missing component, or incomplete graph produces
`BROAD_REVALIDATION_REQUIRED` and schedules validators for every declared component. P6 therefore
never represents `run all` as dependency-aware selective validation.

## P6.4 — Repair candidate generation

`repair_candidate_from_diagnosis()` reuses the existing P4 `LearningCandidate` contract. It only
accepts a diagnosis bound to the exact measured failure and uses the diagnosed component as the
candidate target.

P6 introduces no parallel repair-candidate type and no direct code/prompt/model mutation API.

## P6.5 — Fresh-SHA replay and KQM evidence

`FreshShaValidationEvidence` requires:

- different valid baseline and repair commit SHAs;
- exact candidate and revalidation-plan digests;
- Case Replay records bound to those exact revisions;
- explicit expected replay drift that exactly matches observed replay drift;
- KQM result and report SHA-256 digests;
- proof that every planned validator executed;
- an explicit subset of validators that passed.

Unexpected replay drift is rejected rather than silently accepted.

## P6.6 — Existing promotion path remains authoritative

`SemanticSelfHealingGate` can return only:

- `READY_FOR_EXISTING_PROMOTION`;
- `REJECTED`.

Readiness requires all of the following exact bindings:

1. Experiment Contract -> Learning Candidate digest;
2. Experiment target -> candidate target;
3. P4 Promotion Decision -> exact Experiment Contract digest;
4. P4 status -> `ELIGIBLE_FOR_PROMOTION`;
5. Fresh-SHA evidence -> exact candidate and revalidation plan;
6. Experiment baseline/candidate revisions -> exact baseline/repair SHAs;
7. every planned validator -> executed and PASS.

A P6 READY decision is not deployment authority. It only proves that the repair may continue
through already-governed promotion/release mechanisms.

## Security and epistemic invariants

1. no diagnosis without measured failure provenance;
2. no guessed semantic root cause when a rule is absent;
3. no selective propagation from an incomplete graph;
4. no repair candidate outside the existing P4 hypothesis contract;
5. no same-SHA validation masquerading as repair verification;
6. no undeclared replay drift;
7. no missing planned validator hidden by unrelated PASS results;
8. no P6 bypass around P4 PromotionGate;
9. locked evaluation remains prohibited as learning/repair experiment input by P4;
10. Product runtime does not import Factory modules.

## Relationship to existing Factory self-healing

`factory/self_healing.py` remains the operational lifecycle mechanism for concrete CI/stage
failures. P6 does not replace it and does not import it. A future integration may allow Factory to
consume P6 readiness/impact artifacts, but the runtime/factory dependency boundary remains intact.

## Non-goals

P6 v1 does not:

- generate or apply source-code patches automatically;
- rewrite prompts, rules, routing, retrieval, or model weights automatically;
- push commits or merge pull requests;
- infer a semantic dependency graph from imports and call it complete;
- run locked evaluation for tuning;
- authorize production deployment;
- implement P7 autonomous self-learning or adversarial multi-agent verification.

## Definition of Done

P6 becomes COMPLETE only when:

1. semantic diagnosis, impact graph, repair-candidate, replay-evidence, and readiness-gate tests pass;
2. adversarial tests prove abstention, broad fallback, cycle rejection, fresh-SHA enforcement,
   replay-drift enforcement, full planned validation, P4 promotion binding, and locked-split safety;
3. full Ruff/MyPy/pytest and repository gates pass;
4. Architectural Audit passes;
5. GitHub App Smoke Test and its dispatched Stage Gate pass on the exact feature head;
6. exact validated feature head is merged to `main`;
7. post-merge CI, Architectural Audit, Stage Orchestrator, Smoke, and dispatched Stage Gate pass;
8. SSoT records P6 COMPLETE without claiming P7 is implemented.
