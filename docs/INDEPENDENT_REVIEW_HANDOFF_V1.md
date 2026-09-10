# IRH-01 — Independent Review Handoff & Reviewer Provenance v1

Status: **ENGINEERING IN PROGRESS — EXTERNAL REVIEW NOT PERFORMED**  
Handoff state after successful IRR package verification: `AWAITING_EXTERNAL_REVIEW`  
Repository independent-review state: `NOT_INDEPENDENTLY_REVIEWED`

## Purpose and authority boundary

IRH-01 is the transport, content-binding and provenance-verification boundary between the
closed IRR-01 readiness package and evidence that may later be returned by a real external
reviewer. It is verification-only. It does not select a reviewer, create reviewer identity,
establish reviewer independence, generate reviewer findings or outcomes, sign on behalf of a
reviewer, certify LUKART ROS, or convert repository CI into independent-review evidence.

A successful IRH-01 engineering run may prove that a returned artifact is bound to one exact
IRR handoff and that its signed statement verifies under an externally pinned CRY-01 trust-set
identity. That result is origin/integrity/provenance evidence only. It is not a repository-
generated independent-review PASS and is not certification.

The repository must remain fail closed when real external evidence is absent. In that state the
strongest status is exactly:

`AWAITING_EXTERNAL_REVIEW / NOT_INDEPENDENTLY_REVIEWED`

## Handoff binding

`IndependentReviewHandoffV1` can be created only from an IRR-01 ZIP that first passes
`verify_review_package_v1()`. The handoff then binds:

- source repository `marcusdd720-ui/lukart-ros`;
- IRR scope `IRR-01/v1`;
- exact lowercase 40-character source Git SHA;
- exact content-addressed IRR package basename;
- exact IRR package SHA-256;
- fixed pending external-review and independent-review statuses;
- content-addressed `handoff_identity`.

Changing the source SHA, package name, package bytes/digest, status, scope or authority changes
or invalidates the handoff identity.

## Reviewer-provided evidence

A real reviewer must create the review artifact and review statement outside repository
automation. The v1 returned-evidence contract contains:

1. the exact `IndependentReviewHandoffV1` received for review;
2. `ReviewerProvenanceV1` with reviewer identifier, organization, role and the explicit
   declaration `REVIEWER_DECLARED_INDEPENDENT`;
3. `ReviewArtifactIdentityV1` binding a safe basename, declared media type, SHA-256 and byte
   size of the actual returned review artifact;
4. reviewer-declared outcome: `PASS`, `PASS_WITH_FINDINGS`, `FAIL` or `ABSTAIN`;
5. `review_completed_at`;
6. content-addressed `statement_identity`;
7. an existing Enterprise `SignedAttestation` over the statement.

The review artifact is treated as opaque bytes for integrity verification. Its v1 maximum size
is 32 MiB. The signed media type is metadata; it does not cause the verifier to parse or trust
the semantic content of PDF, Markdown, text or another format.

## Exact signature and trust contract

IRH-01 reuses the existing Enterprise/CRY-01 authority instead of introducing a second
signature or trust system. For accepted returned evidence:

- attestation purpose MUST be `SECURITY_REVIEW`;
- attestation `subject_digest` MUST equal the exact `statement_identity`;
- attestation payload MUST equal the canonical review-statement body;
- `reviewer_id` MUST equal the attestation `key_id`;
- the key MUST exist in the supplied `CryptoTrustSetV1` and allow `SECURITY_REVIEW`;
- revoked, unsupported, not-yet-active or post-retirement keys fail closed according to
  CRY-01;
- attestation validity and Ed25519 signature verification remain delegated to the existing
  Enterprise verifier;
- the caller MUST independently pin `expected_trust_set_digest`; repository state does not
  silently choose a trusted reviewer key;
- reviewer private-key material remains outside repository state and outside IRH-01.

A cryptographically valid signature proves control of a key accepted by the pinned trust set
and binding to the signed bytes. It does not by itself prove organizational independence,
professional competence, completeness of review, or correctness of the review outcome.
`REVIEWER_DECLARED_INDEPENDENT` is deliberately represented as a reviewer declaration, not a
system-certified fact.

## Machine verification result

If all byte, identity, handoff, temporal, trust-set, purpose and signature checks pass, IRH-01
may emit:

`VERIFIED_EXTERNAL_REVIEW_EVIDENCE`

along with the reviewer-declared outcome and:

`REVIEWER_DECLARED_INDEPENDENCE_NOT_SYSTEM_CERTIFIED`

The verifier deliberately preserves repository `independent_review_status` as
`NOT_INDEPENDENTLY_REVIEWED` and `automation_can_certify=false`. Promotion to any stronger
external governance claim requires genuine evidence plus a separately authorized governance
assessment; IRH-01 itself cannot perform that promotion.

## Adversarial requirements

The v1 verification boundary rejects at least:

- cross-handoff/cross-package replay;
- review artifact byte tampering;
- review artifact filename substitution and path traversal;
- altered signed outcome or statement content;
- reviewer identifier / signing-key mismatch;
- wrong externally pinned trust-set identity;
- revoked or untrusted reviewer key;
- non-`SECURITY_REVIEW` purpose;
- expired or temporally inconsistent attestations;
- unknown schema fields and malformed/noncanonical identities.

## CLI

Create a handoff from a verified IRR-01 package:

```bash
python scripts/independent_review_handoff.py create-handoff \
  --package dist/independent-review/IRR-01-v1-<commit>-<sha256>.zip \
  --output dist/independent-review/IRH-01-handoff.json
```

Verify a real returned submission only when the external reviewer has supplied the artifact,
statement/attestation and the independently selected trust-set inputs:

```bash
python scripts/independent_review_handoff.py verify \
  --handoff IRH-01-handoff.json \
  --submission external-review-evidence.json \
  --artifact external-review-report.pdf \
  --trust-set reviewer-trust-set.json \
  --expected-trust-set-digest <sha256> \
  --now <unix-seconds>
```

IRH-01 intentionally provides no CLI command that creates reviewer provenance, chooses a trust
key, generates a reviewer private key, signs a review or fabricates a review outcome.

## Test-fixture boundary

Unit tests may generate ephemeral Ed25519 keys and synthetic review statements solely to test
the verifier. Such fixture signatures, fixture reviewer names and fixture outcomes are not
external evidence, are not independent review, and MUST NOT be used to change repository
review/certification status.

## Engineering closure criteria

IRH-01 may be marked `CLOSED / ENGINEERING PASS` only after its fixed implementation,
focused/adversarial tests, full regression/security, fresh exact-candidate-SHA CI, guarded
merge, resulting-main validation and release guard all pass. Engineering closure does not
require or imply that a real external review has occurred. Unless genuine externally produced
evidence is separately available, the post-closure external state remains exactly:

`AWAITING_EXTERNAL_REVIEW / NOT_INDEPENDENTLY_REVIEWED`
