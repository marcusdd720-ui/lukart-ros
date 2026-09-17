# SIGNED AUTHORING HARDENING — EXECUTION PROFILE

Status: Active bounded execution profile  
Authority: `docs/WORKING_PRINCIPLES.md`  
Scope: automated repository authoring / publication paths

This profile is non-authoritative. It does not create a second engineering standard.
If it conflicts with `docs/WORKING_PRINCIPLES.md`, the canonical standard wins.

## Purpose

Apply the canonical privileged-authoring invariants to a concrete automated
authoring path without coupling the project to one AI model, Git provider,
workflow runner, or user interface.

## Execution sequence

`Live state → operation scope → expected head → prepare → secret-free validation → immutable manifest → re-check authoritative head → atomic publication → post-write verification → exact-revision CI evidence → receipt → closure`

## Required controls

1. Verify live repository/project identity, branch/ref, PR/change request and
   exact base revision before result-affecting work.
2. Bind the operation to a stable `operation_id`, exact expected head,
   allowlisted paths and operation type.
3. Run validation without signing/write credentials.
4. Produce a canonical manifest/digest after validation and publish exactly
   those bytes.
5. Publish the complete change as one logical revision/commit where the provider
   supports it; use provider-side compare-and-swap / expected-head semantics.
6. Treat only an explicit not-found response as resource absence. Authorization,
   rate-limit, server, malformed-response and transport failures remain errors.
7. After timeout or ambiguous write, reconcile actual state before retry or
   cleanup. Never blind-delete evidence or refs.
8. Do not force-push, write directly to protected branches or merge without
   separate authorization.
9. After publication independently verify:
   - verified signature/attestation when required;
   - exact parent/base;
   - exact tree/content digest;
   - exact diff/path allowlist;
   - resulting branch/ref head;
   - PR/change-request head;
   - required CI/checks for the exact resulting revision.
10. Never downgrade to unsigned, unverified or weaker publication.
11. Emit a structured receipt containing operation identity, input revision,
    validated digest, resulting revision and current CI state.

## Failure semantics

Use explicit failure classes where practical:

- `AUTHORIZATION_DENIED`
- `POLICY_VIOLATION`
- `BASE_REVISION_DRIFT`
- `VALIDATION_FAILED`
- `PUBLISH_FAILED`
- `PUBLISH_AMBIGUOUS`
- `SIGNATURE_INVALID`
- `PARENT_MISMATCH`
- `TREE_MISMATCH`
- `REF_MISMATCH`
- `CI_FAILED`
- `CI_TIMEOUT`
- `OPERATION_STALE`

Unknown trust-boundary state fails closed.

## Long-horizon rule

Provider-specific adapters are replaceable. Stable behavior belongs in the
internal operation contract, policy, validation, publication and evidence
layers. Do not make prompts, AI models, workflow syntax or provider APIs the
source of authorization or truth.