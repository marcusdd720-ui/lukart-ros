# Repository Governance

This document defines the repository-level governance target for `main`. It complements the engineering and CASE operating standards; it does not replace product or CASE semantics.

## Fail-closed rule

A pull request may merge only when the exact current head SHA satisfies every required check and every enforced review rule. A PASS for an older SHA is historical evidence only. `PR merged` does not imply `main post-merge validated`.

## Main branch

`main` must be protected by an active GitHub ruleset that, to the extent supported by the repository plan and GitHub feature set:

- requires pull requests for changes to `main`;
- blocks deletion and non-fast-forward updates;
- blocks force pushes and uncontrolled bypass actors;
- requires strict update-before-merge status checks;
- requires all review threads to be resolved;
- dismisses stale approvals after a new push;
- requires approval of the last push;
- requires at least one independent approving review for ordinary changes;
- requires CODEOWNER review for critical boundaries;
- requires two independent approvals for critical changes when the GitHub ruleset architecture can enforce this without ambiguous or path-unsafe behavior.

Self-approval alone is not sufficient independent review. Any break-glass bypass must be explicit, narrowly scoped, auditable, and documented before use.

## Critical ownership boundaries

CODEOWNERS must explicitly cover at least:

- canonical CASE ledger and lifecycle state;
- external-action execution, receipt, idempotency and recovery;
- legal-effect and response classification/delta contracts;
- closure/reopen and authority/approval contracts;
- security, validation and policy configuration;
- GitHub Actions workflows and repository governance files;
- regression tests for the critical invariants above.

A real, confirmed repository owner or team must be used. Never invent a CODEOWNER identity.

## Required validation contexts

The protected branch ruleset must require the concrete check contexts produced by the critical workflows, not merely workflow display names. At minimum the repository currently treats the following contexts as critical:

- `quality-gate (3.11)`
- `quality-gate (3.12)`
- `quality-gate (3.13)`
- `quality-gate (3.14)`
- `gate`
- `orchestrate`
- `audit`
- `smoke-test`
- `program-gate`
- `enterprise-gate`
- `codeql`

Supported runtime versions and required contexts must be re-audited whenever the CI matrix changes. A new supported runtime must not silently remain optional.

## Supply chain and workflow permissions

Critical workflows must use pinned third-party GitHub Actions, frozen or locked dependencies where supported, least-privilege permissions, secret scanning, dependency-boundary checks, CodeQL, and provenance/SBOM controls when available. Untrusted pull-request code must not receive write-capable credentials or secrets.

## Post-merge validation

After every critical merge, validate the actual resulting `main` SHA. Required post-merge evidence includes the critical CI matrix, security/CodeQL, architecture, enterprise hardening, production validation, smoke, replay/recovery/durable-storage, supply-chain, privacy/confidentiality, and long-range/revalidation gates applicable to the repository.

A failed post-merge gate is a production defect. Remediation must use a new branch and pull request under the same governance rules; do not bypass protection to make `main` green.

## Governance drift

Repository settings, CODEOWNERS and required contexts must be periodically compared with this policy. Any mismatch is a governance defect and must remain visible until remediated. Policy text is not a substitute for actual GitHub ruleset enforcement.
