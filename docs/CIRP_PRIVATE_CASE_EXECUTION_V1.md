# CIRP-P04 — Private Case Execution Surface v1

CIRP-P04 is the Post-v1 Product execution surface that composes the already existing
CIRP-P02 private evidence intake with CIRP-P03 governed canonical runtime in one
fail-closed local call.

`docs/WORKING_PRINCIPLES.md` remains the sole canonical living engineering standard.
This document is a stage contract only and creates no competing engineering authority.

## Problem

Before CIRP-P04, the verified private intake adapter and governed runtime existed as
separate Product surfaces. A private-case caller had to compose those boundaries
manually. That increased the risk of bypassing governance or producing operational
results without one explicit execution proof.

## Contract

`core.cirp.run_private_case(...)`:

1. loads only the verified private evidence projection through the existing P02 adapter;
2. binds the selected verified evidence subset to a fresh CIRP run identity;
3. preserves explicit `evaluation_time`, configuration identity and optional event/model
   identity;
4. executes the bound request only through `GovernedCanonicalCIRPRuntime`;
5. therefore requires exact rule-pack approval and freshness governance whenever rule
   packs are present;
6. returns the governed CIRP result plus a deterministic privacy-minimized execution
   receipt.

The receipt contains only digests for:

- bound CIRP run identity;
- final CIRP report;
- canonical CIRP replay manifest;
- optional rule-pack governance receipt;
- optional governed replay manifest.

Governance receipt and governed replay identity are an atomic pair. Partial governance
binding is contract-invalid.

## Privacy and authority boundaries

CIRP-P04 does **not**:

- read plaintext evidence directly;
- publish private case documents or case data to GitHub/CI;
- write Canonical Case Ledger history;
- create, fetch or update law;
- approve a rule pack;
- weaken P03 freshness governance;
- create a second Product truth authority;
- render DOCX/PDF filings;
- sign, send, file or submit anything externally;
- claim legal, professional, independent, security or regulatory certification;
- turn synthetic public CI into real-case validation evidence.

Canonical Case Ledger remains the sole authoritative writable case-history SSOT.
Public repository tests use synthetic fixtures only. Real-case documents and operational
case data remain local-only.

## Validation expectations

Engineering closure requires the normal canonical pipeline from
`docs/WORKING_PRINCIPLES.md`: focused/adversarial tests, full regression, lint/type
checks, security/policy gates, exact-candidate CI, guarded merge and independent
post-merge validation of the resulting `main` SHA.

A real-case run is a separate operational event and must be reported only when actual
private-case evidence has been processed locally. Repository CI alone is not evidence of
a real-case execution.
