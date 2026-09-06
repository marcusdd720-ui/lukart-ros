# Security Policy

## Supported security baseline

The immutable `v1.0.1` release remains a historical certified baseline. Active security hardening
is performed on Post-v1 development branches and must not rewrite historical release evidence.

## Reporting a vulnerability

Do not place real client/case data, credentials, tokens, private keys, medical data, financial data,
PESEL-like identifiers or other sensitive evidence in a public issue.

For repository defects that can be demonstrated using synthetic data, open a GitHub issue with the
minimum reproducible example and mark it as a security-related defect. For sensitive vulnerabilities,
use a private/security reporting channel configured for the repository before sharing exploit details.

## Security invariants

- Agents/plugins are untrusted execution workers and are never epistemic authorities.
- External `TRUSTED` analytical state requires explicit verified authorization/attestation.
- Secrets and private signing keys must never be committed to the repository.
- Locked Gold/certification/release artifacts are immutable.
- Missing security evidence fails closed.
- Telemetry must redact sensitive values before export.
- Release tags are never moved to manufacture a successful release.

## Severity handling

Critical findings include unauthorized trusted-state promotion, tenant/case isolation bypass,
provenance forgery, private-key exposure, arbitrary code execution across an isolation boundary,
release/supply-chain compromise and silent corruption of evidence lineage.

A critical finding blocks Enterprise Candidate status until fixed, regression-tested and represented
in the adversarial/failure corpus where safe to do so.

## Disclosure discipline

Security engineering PASS is not a claim of penetration-test completion, independent review,
regulatory compliance or external certification. Those claims require their own evidence.