# CASE-TESTY — Canonical Regression Suite

Status: **ACTIVE CANONICAL TEST SOT**  
Schema: `lukart.case-regression-suite.v1`  
Bootstrap base: `main@53c13d91bb8b7d7c612bf4f152884de6d4d8c02b`

This file is the single repository source of truth for the CASE-TESTY batch regression inventory.
It does not replace `docs/WORKING_PRINCIPLES.md`; it only declares which synthetic CASE-TESTY
batch scenarios must be executed by the canonical regression runner.

Bootstrap scope is evidence-bound to the executable P0 regression contract that already existed on
the bootstrap base. Historical chat-only or unattached regression-suite content is not reconstructed
or silently imported.

Rules:

- every automated batch case MUST appear exactly once under `TESTY BATCHOWE`;
- every batch row MUST map to an existing `tests/*.py` pytest node;
- the runner MUST execute every declared batch row exactly once and in declared order;
- missing, duplicate, malformed or extra batch execution is fail-closed and cannot produce PASS;
- the report MUST bind to the SHA-256 digest of this file;
- `TESTY RĘCZNE / PRODUCT SMOKE` is never executed by the automated batch runner;
- fixtures remain synthetic; real CASE data, identifiers or documents are forbidden here;
- adding or removing a batch row is a material regression-scope change and requires normal PR/CI review.

## TESTY BATCHOWE

| ID | Pytest node | Description |
|---|---|---|
| CASE-BATCH-001 | tests/case/test_case_ledger_isolation.py | CASE cognitive/privacy isolation and no cross-CASE fact transfer |
| CASE-BATCH-002 | tests/security/test_tenant_case_isolation.py | Tenant and CASE isolation security boundary |
| CASE-BATCH-003 | tests/case/test_cirp_preflight_lifecycle.py | CIRP preflight and lifecycle status semantics |
| CASE-BATCH-004 | tests/case/test_external_action_lifecycle.py | External-action receipt and SENT/RECEIVED lifecycle semantics |
| CASE-BATCH-005 | tests/case/test_cirp_evidence_semantics.py | FACT/CLAIM/UNKNOWN evidence semantics and no-evidence-no-fact rule |
| CASE-BATCH-006 | tests/test_stage_gate_fail_closed.py | Fail-closed stage-gate behavior |
| CASE-BATCH-007 | tests/case/test_case_ledger_integrity.py | Canonical Case Ledger integrity and authoritative-history invariants |
| CASE-BATCH-008 | tests/case/test_p4_enterprise_regression_hardening.py | P4 lifecycle, deadline, authority, topology, renderer, privacy-canary and Red Team operational invariants |

## TESTY RĘCZNE / PRODUCT SMOKE

This section is intentionally non-executable in CI. Manual/product-smoke scenarios are repository-backed synthetic product checks and MUST NOT change automated batch completeness.

| ID | Authority | Synthetic stimulus | Acceptance criteria |
|---|---|---|---|
| CASE-MANUAL-001 | `docs/PRIVATE_CASE_OPERATING_STANDARD.md` §3.1, §13 | `LUKART ROS — NEW CASE: SYNTHETIC-MANUAL-001. CIRP REAL CASE RUN.` | Short trigger is accepted without requiring the full standard; scope and decision need are established first; privacy boundary is preserved; execution continues only to the current evidence ceiling. |
| CASE-MANUAL-002 | `docs/PRIVATE_CASE_OPERATING_STANDARD.md` §3.2, §13 | Existing synthetic CASE plus `LUKART ROS — CASE SYNTHETIC-MANUAL-002 — CONTINUE.` and one new synthetic event | Authorized current CASE state is reconstructed; only delta analysis is performed for the new event; analysis is not restarted from zero; no facts are imported from another CASE; `UNKNOWN` / `UNRESOLVED` state remains visible. |
