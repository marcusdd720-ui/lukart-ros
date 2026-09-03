# P4 — Controlled Learning Foundation

Status: COMPLETE

P4 implementation was merged to `main` as `082358d28a336fa648e5cc05bb2a9d7a656c64af` after exact-head feature validation. Post-merge validation on that merge SHA passed CI Foundation on Python 3.11/3.12/3.13, Architectural Audit 1.0, Stage Orchestrator, GitHub App Smoke Test, and the smoke-dispatched Stage Gate.

## Decision need

P3 made reasoning results measurable and produced traceable KQM failure records. P4 creates the
first controlled path from a measured failure to an improvement candidate without granting the
learning layer authority to mutate trusted Product state.

The P4 loop is:

`Measured Failure -> Failure Corpus -> Learning Candidate -> Bounded Experiment -> KQM Delta -> Promotion Decision`

A positive promotion decision means only `ELIGIBLE_FOR_PROMOTION`. It is not a write operation,
model deployment, rule replacement, prompt replacement, or certification event.

## Delivered

- immutable `MeasuredFailure` with corpus/split/evaluator/source-SHA/result/report provenance;
- fail-closed Failure Corpus that rejects locked evaluation and malformed report digests;
- deterministic `LearningCandidate` separated from trusted knowledge;
- bounded `ExperimentContract` restricted to development/validation splits, distinct revisions,
  sandbox, metric guardrails, and run budget;
- finite metric checks and SHA-256 candidate/experiment digest validation;
- fail-closed `PromotionGate` with `ELIGIBLE_FOR_PROMOTION`, `REJECTED`, and `INCONCLUSIVE`;
- separate Reasoning KQM evaluator-version provenance;
- `learning/` package discovery and Product/Factory dependency boundary;
- adversarial tests covering provenance, locked data, malformed digests, revision binding,
  non-finite metrics, contract mismatch, run budget, and guardrail regression.

## Security and epistemic invariants

1. no raw production outcome becomes trusted learning truth;
2. no locked evaluation data becomes tuning input;
3. no hypothesis becomes canonical knowledge merely because it was generated;
4. no experiment may silently change its baseline, candidate revision, or run budget;
5. no metric regression beyond a declared guardrail may be promoted;
6. no positive experiment result directly mutates production state;
7. material provenance links are validated and digest-bound;
8. engineering PASS is not analytical certification.

## Validation evidence

Feature implementation head `434b97ce26c70b82f07cee5da5d1fd5de657fa21` passed CI Foundation,
Architectural Audit, GitHub App Smoke, and dispatched Stage Gate. Final feature head
`6727cd34be12f80a29499b70f7641eef7a42f0bc`, containing the validated SSoT update, passed the same exact-head gates and was merged without further branch changes.

Implementation merge `082358d28a336fa648e5cc05bb2a9d7a656c64af` then passed:

- CI Foundation — Python 3.11, 3.12, 3.13;
- Architectural Audit 1.0;
- Stage Orchestrator;
- GitHub App Smoke Test;
- smoke-dispatched Stage Gate.

Earlier failures were repaired on fresh SHAs: Ruff style/line-length findings and a PII scanner false positive caused by a hexadecimal-character literal. The PII gate was not weakened or bypassed.

## Non-goals preserved

P4 does not generate repairs automatically, train/fine-tune models, distill Cases into agent training packages, mutate prompts/rules/retrieval/model weights, automatically select production agents, execute locked evaluation, claim production reasoning certification, or implement semantic Self-Healing/Change Propagation.

Those remain later-program responsibilities.
