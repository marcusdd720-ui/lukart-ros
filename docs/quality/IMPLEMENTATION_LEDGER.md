# Implementation Ledger — LukArt ROS

This ledger is the control-plane safeguard against plan/repository drift.

## Rule

A planned change is **not implemented** until all of the following are true:

1. the intended file exists on the target branch;
2. the implementation is exercised by an automated test or CI check where applicable;
3. the relevant CI workflow has executed on the target commit;
4. the observed result is recorded as `PASS`, `FAIL`, or `PENDING`;
5. the change is linked to a commit/PR.

Chat discussion, a design document, or an AI-generated patch proposal is not
implementation evidence.

## Status vocabulary

- `PLANNED` — design approved, no implementation evidence yet;
- `IMPLEMENTED` — code exists, but CI evidence is not yet available;
- `VERIFIED` — implementation exists and automated verification passed;
- `BLOCKED` — implementation cannot proceed because a prerequisite failed;
- `PENDING` — measurement or verification is not yet available.

## Current hardening baseline

| Control | Status | Evidence |
|---|---|---|
| Python 3.11–3.13 CI matrix | IMPLEMENTED | `.github/workflows/ci.yml` |
| Project-wide Ruff/Pytest | IMPLEMENTED | `.github/workflows/ci.yml` |
| Project-wide repository audit | IMPLEMENTED | `scripts/repository_audit.py` |
| PII/confidentiality gate | IMPLEMENTED | `scripts/pii_scan.py` |
| Critical fact taxonomy | IMPLEMENTED | `docs/quality/critical_facts_schema.yaml` |
| Extraction Research Charter | IMPLEMENTED | `docs/research/RESEARCH_CHARTER_EXTRACTION_QUALITY_V1.md` |
| Provenance contract | IMPLEMENTED | `knowledge/provenance.py` |
| Ground Truth Corpus | PENDING | not yet built |
| KQM evaluator | PENDING | not yet built |
| Git history PII clearance | PENDING | history audit required |
| Hardening PR CI verification | PENDING | must pass on final head |

## Release rule

No item may be promoted from `IMPLEMENTED` to `VERIFIED` from chat inspection
alone. Verification must be tied to an actual repository state and CI result.
