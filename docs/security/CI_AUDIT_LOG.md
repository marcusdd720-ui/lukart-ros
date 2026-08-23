# CI Audit Log

## 2026-08-23 — CI integrity correction

### Finding

The base commit for hardening (`fc4e52a28c2516ff84179b082c5012a63168955a`) used
a placeholder CI job that only emitted a success message. It did not execute
the project's tests.

### Remediation

From the hardening branch, CI now executes:

- Ruff;
- Pytest;
- PII/confidentiality gate;
- Python 3.11, 3.12 and 3.13 matrix.

Ontology validation uses the same supported Python matrix and executes Ruff,
MyPy and Pytest.

### Trust interpretation

Historical green CI statuses before this correction must not be treated as
evidence that the corresponding code passed the current engineering test
suite. They are historical process metadata only.

A historical CI audit should be completed before a production release if the
release process relies on commit-level evidence from the pre-correction period.
