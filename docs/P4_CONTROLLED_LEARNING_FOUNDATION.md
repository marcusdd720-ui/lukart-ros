# P4 — Controlled Learning Foundation

Status: IMPLEMENTED / release validation pending

## Decision need

P3 made reasoning results measurable and produced traceable KQM failure records. P4 creates the
first controlled path from a measured failure to an improvement candidate without granting the
learning layer authority to mutate trusted Product state.

The P4 loop is:

`Measured Failure -> Failure Corpus -> Learning Candidate -> Bounded Experiment -> KQM Delta -> Promotion Decision`

A positive promotion decision means only `ELIGIBLE_FOR_PROMOTION`. It is not a write operation,
model deployment, rule replacement, prompt replacement, or certification event.

## P4.1 — Measured Failure contract

`learning.models.MeasuredFailure` is immutable and records:

- source KQM family;
- source corpus and version;
- split;
- evaluator version;
- source Git SHA;
- case id and failure code;
- expected and actual values;
- source result SHA-256 digest;
- source report SHA-256 digest.

Raw model output or an unmeasured production observation is not a valid `MeasuredFailure`.

## P4.2 — Failure Corpus

`failure_corpus_from_reasoning` converts only traceable `ReasoningKQMReport` failures into a
versioned Failure Corpus. Every failure must have a corresponding deterministic result digest.

Locked evaluation is fail-closed: a report from `locked_evaluation`, or a report marked as
having executed locked evaluation, raises `LockedLearningSourceError` and cannot become learning
input.

## P4.3 — Learning Candidate

A `LearningCandidate` is a hypothesis, not trusted knowledge. It binds to the digest of one
measured failure and explicitly declares:

- target component;
- change kind;
- problem statement;
- hypothesis;
- measurable success criteria.

Candidate identity is deterministic for the same measured failure and hypothesis.

## P4.4 — Bounded Experiment contract

An `ExperimentContract` binds the candidate digest to:

- baseline revision;
- distinct candidate revision;
- sandbox id;
- allowed benchmark splits;
- metric guardrails;
- maximum run budget.

Only `development` and `validation` are valid learning experiment splits. `locked_evaluation`
and arbitrary production/test split names are rejected.

## P4.5 — Metric integrity

Metric values and guardrail tolerances must be finite. `NaN` and infinity are invalid because
they could otherwise bypass comparison semantics.

Experiment measurements require unique metric names. Promotion requires every contracted
metric to exist in both baseline and candidate measurements.

## P4.6 — Promotion Gate

`PromotionGate` is fail-closed and returns one of:

- `ELIGIBLE_FOR_PROMOTION` — at least one guarded metric improves and none exceeds its allowed
  regression;
- `REJECTED` — contract binding, revision binding, run budget, required metrics, or guardrails
  fail;
- `INCONCLUSIVE` — the candidate produces no measured improvement and no forbidden regression.

The gate returns an immutable decision artifact. It exposes no API for changing canonical
knowledge, Product code, prompts, rules, routing, models, agent certification, or release state.

## P4.7 — Provenance correction

P4 versions the Reasoning KQM evaluator separately from the Reasoning Engine. A learning failure
therefore records both the engine version and evaluator provenance rather than treating them as
the same component.

## P4.8 — Factory/Product boundary

`learning/` is Product runtime logic and is included in the runtime dependency-boundary gate.
It must not import `factory` implementation modules. Factory remains responsible for building,
testing, validating, and releasing the Product.

## Security and epistemic invariants

P4 preserves these invariants:

1. no raw production outcome becomes trusted learning truth;
2. no locked evaluation data becomes tuning input;
3. no hypothesis becomes canonical knowledge merely because it was generated;
4. no experiment may silently change its baseline, candidate revision, or run budget;
5. no metric regression beyond a declared guardrail may be promoted;
6. no positive experiment result directly mutates production state;
7. all material learning artifacts are immutable and digest-bound where source contracts allow;
8. engineering PASS is not analytical certification.

## Non-goals

P4 does not:

- generate repairs automatically;
- train or fine-tune models;
- distill Cases into agent training packages;
- mutate prompts/rules/retrieval/model weights;
- select production agents automatically;
- execute locked evaluation;
- claim that the current reasoning Gold candidate is production truth;
- implement semantic Self-Healing or dependency-aware Change Propagation.

Those capabilities require later programs and their own evidence.

## Definition of Done

P4 becomes COMPLETE only when:

1. controlled-learning unit and adversarial boundary tests pass;
2. full Ruff/MyPy/pytest and repository gates pass;
3. Architectural Audit passes;
4. GitHub App Smoke Test and its dispatched Stage Gate pass on the exact feature head;
5. the exact validated head is merged to `main`;
6. post-merge CI, Architectural Audit, Stage Orchestrator, Smoke, and dispatched Stage Gate pass;
7. SSoT records P4 completion without claiming P5 teaching/distillation is implemented.
