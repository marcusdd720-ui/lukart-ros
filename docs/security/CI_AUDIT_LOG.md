# CI Audit Log

## 2026-08-23 — CI integrity correction

The base hardening predecessor used a placeholder CI job that emitted a success message without executing the project test suite.

Current policy:
- Ruff;
- MyPy;
- Pytest;
- repository integrity audit;
- PII/confidentiality gate;
- Python 3.11–3.13 matrix.

Historical green statuses from the placeholder period are process metadata only and are not evidence that the corresponding code passed the current engineering suite.
