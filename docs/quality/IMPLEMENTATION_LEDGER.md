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
- `BLOCKED` — a release-blocking defect prevents verification.
- `REJECTED` — the proposed change was tested and deliberately not adopted.

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
| Ground Truth Corpus | PLANNED | locked evaluation corpus |
| KQM | PLANNED | evaluator + measured corpus |
| IAA | PLANNED | independent annotation agreement |

## Operating rule

No new research/architecture phase may be declared complete until the ledger
status is upgraded using repository and execution evidence. A later document
must not silently convert `PLANNED` or `IMPLEMENTED` into `VERIFIED`.
