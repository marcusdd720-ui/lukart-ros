# Implementation Ledger

This ledger is the project's control against plan/repository drift.

## Rule

A statement in a conversation, PDF, plan, issue, or review is not evidence that
an implementation exists.

A change becomes `VERIFIED` only when all of the following are true:

1. the implementation exists in the repository;
2. the relevant automated test or control exists;
3. the control has actually executed;
4. the observed result is recorded by the execution system;
5. the implementation is present in the commit under review;
6. no unresolved release blocker remains for that item.

## Statuses

- `PLANNED` — desired change is defined but not implemented.
- `IMPLEMENTED` — code/configuration exists, but execution evidence is missing.
- `VERIFIED` — implementation and execution evidence agree.
- `BLOCKED` — a release-blocking defect prevents verification or promotion.
- `REJECTED` — the proposed candidate was tested and deliberately not adopted/promoted.

## Current hardening baseline

| Control | Status | Evidence required for VERIFIED |
|---|---|---|
| Python 3.11–3.13 matrix | IMPLEMENTED | successful CI matrix |
| Project-wide Ruff | IMPLEMENTED | successful CI job |
| Project-wide MyPy | IMPLEMENTED | successful CI job |
| Project-wide Pytest | IMPLEMENTED | successful CI job |
| Repository integrity audit | IMPLEMENTED | successful CI job |
| PII/confidentiality gate | IMPLEMENTED | successful CI job |
| Stale static quality reports removed | IMPLEMENTED | repository inspection |
| Git-history PII audit | PLANNED | documented history review |
| Gold corpus candidate | IMPLEMENTED | candidate corpus + deterministic split + schema validation |
| Independent gold corpus review/freeze | PLANNED | external review evidence + immutable frozen version |
| KQM evaluator + reproducible baseline | VERIFIED | development/validation metrics executed in CI |
| Production KQM release gate | BLOCKED | independent corpus review/freeze + authorized locked evaluation |
| IAA | PLANNED | independent annotation agreement |

## Agent Layer P0

| Control | Status | Execution evidence |
|---|---|---|
| `AGENTS.md` v2 enterprise operating contract | VERIFIED | PR #27 + CI/Audit/Smoke PASS + merge |
| Safe GitHub permission policy | VERIFIED | reads allowed; writes require approval |
| Agent Step Contract | VERIFIED | contract tests + CI/Audit/Smoke PASS |
| Agent Registry | VERIFIED | registry/version tests + CI/Audit/Smoke PASS |
| Agent Runner / Validation Gate | VERIFIED | fail-closed runner tests + CI/Audit/Smoke PASS |
| `ReferenceFactAgent v1.0.0` runtime | VERIFIED | controlled runtime/provenance test + CI/Audit/Smoke PASS |
| Agent Evaluation / Certification framework | VERIFIED | threshold/review/fingerprint tests + CI/Audit/Smoke PASS |
| Agent -> KQM vertical slice | VERIFIED | development + validation measurement executed in CI |
| Locked-evaluation protection | VERIFIED | P0 vertical slice does not execute locked split |
| `ReferenceFactAgent v1.0.0` quality certification | REJECTED | validation P=0.50, R=0.30, F1=0.375, critical recall=0.214286, critical fact loss=11 |

## P0 measurement evidence

The first controlled agent baseline uses `extraction-gold-v1`, whose status remains
`candidate_pending_independent_review` / `not_reviewed`.

Development result:

- TP=18, FP=20, FN=42;
- precision=0.473684, recall=0.300000, F1=0.367347;
- critical recall=0.190476;
- critical fact loss=34;
- provenance completeness=1.000000.

Validation result:

- TP=6, FP=6, FN=14;
- precision=0.500000, recall=0.300000, F1=0.375000;
- critical recall=0.214286;
- critical fact loss=11;
- provenance completeness=1.000000.

The low analytical metrics do not invalidate the Agent Layer. They are evidence that
the measurement/certification boundary is working: a technically valid and fully
traceable agent is not promoted when analytical quality is below policy thresholds.

The locked evaluation split was not executed.

## Operating rule

No new research/architecture phase may be declared complete until the ledger
status is upgraded using repository and execution evidence. A later document
must not silently convert `PLANNED` or `IMPLEMENTED` into `VERIFIED`.

`VERIFIED` infrastructure does not imply `CERTIFIED` analytical quality. Promotion
requires the explicit quality and independent-review gates defined by the relevant
policy.
