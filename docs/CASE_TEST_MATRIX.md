# CASE-TESTY Requirement → Test Matrix

Status: P1 closure map for synthetic CASE-TESTY only.

This document does not create a new Product truth authority. It maps the existing CASE-TESTY Definition of Done to repository-native executable evidence.

| Program item | Requirement | Executable evidence | Required profile / gate |
| --- | --- | --- | --- |
| P1 Golden CASE suite | Synthetic golden CASE must be deterministic, content-addressed and replay-verifiable | `tests/golden/test_case_golden.py` + `tests/fixtures/case_testy/synthetic_case.json` | FULL, FORENSIC via full regression |
| P1 Regression suite | Repository regression must execute without silent omission | full `pytest` in `FULL`, `POST-MERGE`, `FORENSIC` | FULL / POST-MERGE / FORENSIC |
| P1 Adversarial CASE suite | Adversarial Gold paths must execute | `tests/test_adversarial_gold.py` | FORENSIC `adversarial-gold` + full regression |
| P1 CASE security suite | CASE/tenant isolation and security regressions must execute | `tests/security/` | FORENSIC `security` + FULL |
| P1 PII/confidentiality | CASE-TESTY fixtures must be explicitly synthetic and reject obvious personal identifiers | `tests/security/test_case_pii_boundaries.py` | FULL / FORENSIC |
| P1 Synthetic fixtures | Test fixtures are synthetic-only and isolated from real CASE data | `tests/fixtures/case_testy/synthetic_case.json` + PII boundary tests | FULL / FORENSIC |
| P1 Requirement traceability | Required CASE-TESTY controls have an explicit test/evidence mapping | this matrix | repository review + FULL |
| P1 Machine-readable report | Each profile emits structured exact-SHA evidence | `factory/quality/test_profiles.py`, `factory/quality/test_report.py` | PR gate / POST-MERGE / FORENSIC |
| P1 Report JSON Schema | Report wire contract is externally described and versioned | `schemas/case_test_report.schema.json`, `tests/profiles/test_case_testy_p1_contracts.py` | FULL |
| P1 Reproducibility metadata | Report binds repository/ref/profile and exact git/checkout SHA | `factory/quality/test_profiles.py`, report validator | PR gate / POST-MERGE / FORENSIC |
| P1 Exact SHA evidence | Moving refs cannot substitute for candidate/merge SHA | CASE-TESTY workflows and report validator | PR gate / POST-MERGE / FORENSIC |
| P1 Deterministic rerun | Identical semantic inputs/results produce identical report semantics apart from wall-clock fields | `tests/profiles/test_case_testy_p1_contracts.py` | FULL / FORENSIC |
| P1 Failure artifact preservation | Report validation still runs and artifact upload is attempted after profile failure; missing files fail | `case-testy-pr-gate.yml`, workflow contract tests | PR gate |
| P1 CI summary/reporting | Terminal profile/report status is machine-readable and retained as Actions artifact | CASE-TESTY workflows + artifacts | PR gate / POST-MERGE / FORENSIC |
| P1 Profile documentation | FAST, PR, FULL, FORENSIC and POST-MERGE scope is executable and test-covered | `factory/quality/test_profiles.py`, `tests/profiles/test_case_testy_workflows.py` | FULL |

## Closure rule

A row is `VALIDATED` only after the relevant executable evidence has completed successfully on the exact candidate SHA, and after merge any required POST-MERGE / FORENSIC evidence is bound to the exact resulting `main` SHA. Presence of a file or workflow is only `IMPLEMENTED` until real execution evidence exists.

P2 is not opened by this matrix. P2 is generated only by the second-order gap analysis after all required P1 rows are validated or explicitly not required.
