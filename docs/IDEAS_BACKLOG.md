# LUKART ROS — Deferred Ideas Backlog

Status: non-authoritative parking lot for deferred ideas.
Canonical engineering standard remains `docs/WORKING_PRINCIPLES.md`.
Live implementation state remains GitHub `main` / active roadmap.
Items in this file are `PLANNED/DEFERRED` only and MUST NOT be treated as implemented, validated, certified, or release-authorized.

## IDEA-001 — Privacy-First Provider-Agnostic Preservation Fabric

Status: `DEFERRED`
Recorded: `2026-09-09`
Revisit not before: `2027-03-09`
Owner decision: do not use Amazon/AWS for real LUKART case data at this stage.

### Problem / motivation

Preserve case/replay artifacts outside the primary machine and GitHub without making any cloud provider a Product/CCL authority and without exposing plaintext case content to that provider.

### Target concept

- provider-independent storage contract under the existing `ArtifactEscrowBackendV1` / replay boundaries;
- mandatory client-side encryption before any sensitive bytes leave the trusted device;
- provider receives opaque ciphertext only; encryption keys remain outside provider storage and outside GitHub;
- no PII/case names/sygnatures in provider object keys or ordinary metadata;
- separate plaintext artifact identity and ciphertext object identity;
- at least one encrypted offline recovery copy on independent media;
- at least one external immutable/WORM provider with independently verifiable retention/version evidence;
- real restore/replay drill required before any `PRESERVED` claim;
- provider-specific evidence adapters remain replaceable and must not become a competing SSOT;
- future multi-provider mode may add a second independent European provider when risk, scale, SLA/RPO/RTO, client obligations, or cost justify it;
- AWS implementation already present in the repository may remain as dormant compatibility code, but Amazon is excluded from active real-data storage unless a future explicit business decision reverses that policy.

### Candidate provider direction for future review

Re-evaluate available European/privacy-aligned providers and no-cost/low-cost options at review time. Backblaze B2 was explored as a technically interesting S3-compatible WORM/Object-Lock candidate, but no provider is approved by this backlog entry and no account/storage deployment is authorized by it.

### Acceptance criteria for future activation

Before promotion from `DEFERRED` to an active stage, require fresh evidence on provider terms, jurisdiction/data handling, pricing, Object Lock/WORM semantics, version identity, API-verifiable retention, credential model, export/recovery path, portability, provider lock-in, deletion/retention controls, and client-side encryption/key-recovery design.

The future implementation should follow the canonical pipeline and fail closed. No plaintext case data may be uploaded during evaluation; synthetic artifacts must be used until the full privacy/security path is validated.
