# P5 — Agent Teaching & Distillation

Status: VALIDATED IMPLEMENTATION / FINAL MERGE GATE PENDING

## Decision need

P4 can turn a measured KQM failure into a bounded improvement candidate and an immutable
promotion-eligibility decision. P5 must convert only controlled, independently approved learning
material into a versioned teaching artifact for a specific agent contract, while preventing raw
Case output, locked evaluation, or an unreviewed hypothesis from becoming training truth.

The P5 loop is:

`Approved Gold/Failure Example + Eligible P4 Candidate -> Teaching Package -> Candidate Agent Contract -> Recertification -> Release Eligibility`

P5 is a Product capability. It does not grant Factory code or a model permission to rewrite a
production agent automatically.

## P5.1 — Teaching Example manifest

`TeachingExample` is an immutable manifest. It stores source and content digests plus evidence
digests rather than copying raw Case payload into the learning layer.

Supported example classes:

- `GOLD` — a controlled corpus example;
- `FAILURE` — an example derived from an exact `MeasuredFailure` digest.

Only `development` and `validation` are valid teaching splits. `locked_evaluation`, production,
and arbitrary test split names are rejected fail-closed.

## P5.2 — Independent Teaching Approval

Every teaching example must have exactly one `TeachingApproval` before distillation. The approval
binds to the exact example digest and records reviewer identity, outcome, rationale, and evidence
reference.

Reviewer identities `system`, `automated`, and `factory` are forbidden. Distillation requires an
independent `PASS`; `FAIL` and `PENDING` examples cannot enter an agent teaching package.

## P5.3 — P4 promotion binding

A teaching package can be distilled only when:

1. the Experiment Contract is bound to the exact Learning Candidate digest;
2. the experiment target matches the candidate target;
3. the Promotion Decision is bound to the exact Experiment Contract digest;
4. the Promotion Decision is `ELIGIBLE_FOR_PROMOTION`;
5. the candidate change kind is appropriate for agent teaching.

P5 accepts `PROMPT`, `RETRIEVAL`, `RULE`, and `MODEL` candidate kinds. `CODE`, `POLICY`, and
`ROUTING` are rejected because they require distinct engineering or governance promotion paths.

## P5.4 — Agent Teaching Package

`AgentTeachingPackage` is an immutable, semantically versioned manifest bound to:

- target Agent ID, name, version, and Agent Contract SHA-256;
- target component and change kind;
- Learning Candidate SHA-256;
- Experiment Contract SHA-256;
- Promotion Decision SHA-256;
- ordered teaching example SHA-256 digests;
- ordered independent approval SHA-256 digests;
- explicit teaching instruction.

Package identity and digest are deterministic. The package contains no `apply`, `promote`, or
mutation operation.

## P5.5 — Mandatory agent recertification

`AgentTeachingReleaseGate` binds release eligibility to certification of the exact taught agent
contract.

Outcomes:

- `ELIGIBLE_FOR_RELEASE` — exact agent name, version, and contract digest match and certification
  status is `CERTIFIED`;
- `PENDING_RECERTIFICATION` — the exact contract is known but not yet certified;
- `REJECTED` — agent identity/contract mismatch or certification is rejected.

A successful P4 experiment therefore cannot release a taught agent by itself.

## Security and epistemic invariants

P5 preserves these invariants:

1. raw unchecked Case output is never automatically teaching truth;
2. locked evaluation cannot become teaching/tuning input;
3. every teaching example requires evidence digests and independent approval;
4. generated hypotheses remain candidates until P4 measurement and promotion gates pass;
5. a teaching package is bound to one exact candidate, experiment, decision, and agent contract;
6. teaching artifacts are immutable manifests, not self-modification authority;
7. agent release requires recertification of the exact taught contract;
8. engineering PASS is not analytical or domain certification.

## Feature validation evidence

Implementation head `c887edf5030f4012b85e4949fcc6200c38352217` passed:

- CI Foundation on Python 3.11, 3.12, and 3.13;
- Ruff, MyPy, pytest, repository audit, PII/confidentiality gate, and dependency boundary;
- Architectural Audit 1.0;
- GitHub App Smoke Test;
- smoke-dispatched Stage Gate #219.

This SSoT update creates a newer feature head. The exact final docs+code head must pass the same
merge gates before merge. P5 remains incomplete until merge and post-merge validation succeed.

## Non-goals

P5 does not:

- fine-tune a model automatically;
- rewrite prompts, retrieval, rules, or model weights in production;
- ingest raw private production Cases as training truth;
- use locked evaluation as teaching material;
- certify a domain corpus automatically;
- select production agents automatically;
- implement semantic Self-Healing or dependency-aware Change Propagation.

## Definition of Done

P5 becomes COMPLETE only when:

1. teaching/distillation unit and adversarial boundary tests pass;
2. full Ruff/MyPy/pytest and repository gates pass;
3. Architectural Audit passes;
4. GitHub App Smoke Test and its dispatched Stage Gate pass on the exact feature head;
5. the exact validated head is merged to `main`;
6. post-merge CI, Architectural Audit, Stage Orchestrator, Smoke, and dispatched Stage Gate pass;
7. SSoT records P5 completion without claiming P6 semantic self-healing is implemented.
