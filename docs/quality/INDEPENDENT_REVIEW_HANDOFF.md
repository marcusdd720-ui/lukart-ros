# Independent Review Handoff

This handoff prepares the four external human gates without approving any of them.
Automation, bots, agents, system identities, the Factory, and the repository owner are not valid
independent reviewers for these gates.

The current frozen Product revision for the Step 16 / Step 18 review packages is
`4ebec450bd87f2c29cc890dbd02941c7af953710` (v1 RC release version `1.0.1`). Review-preparation
documentation commits made after that revision do not change the Product code under review.

## Step 1 / Issue #50 — extraction-gold-v1

- Review subject: `data/quality/extraction_gold_v1.json`
- Exact SHA-256: `8f184c7944393d4fe617b24f900754f1dd8957ee1a43a4a9c0144e15ddd26ee8`
- Template: `docs/quality/reviews/extraction_gold_v1_review.template.json`
- Human output: `docs/quality/reviews/extraction_gold_v1_review.json`
- The completed `reviewer_id` must equal the independent reviewer's exact GitHub login.
- After valid APPROVED review plus authenticated runtime provenance: allow deterministic corpus
  freeze and continue Step 1 -> Step 3.

## Step 5 / Issue #51 — reasoning-gold-v2

- Review subject: `data/quality/reasoning_gold_v2.json`
- Exact SHA-256: `b51956dc82264ab4ae6bb7a183efa926ae087fc52b8b074fbb6468dd08614851`
- Template: `docs/quality/reviews/reasoning_gold_v2_review.template.json`
- Human output: `docs/quality/reviews/reasoning_gold_v2_review.json`
- The completed `reviewer_id` must equal the independent reviewer's exact GitHub login.
- Locked evaluation must not be used for tuning.
- After valid APPROVED review plus authenticated runtime provenance: allow deterministic corpus
  freeze and continue Step 5 -> Step 6 -> Step 8.

## Step 16 / Issue #62 — renderer/dossier quality

- Reviewed Product revision: `4ebec450bd87f2c29cc890dbd02941c7af953710`
- Review package: `docs/quality/review_packages/step_16_review_package.json`
- Package SHA-256: `062a8cbc37331dbaf4eda2f21e89dade1b6bac55393e5a5ffdbd6cee1e6edab6`
- Template: `docs/quality/reviews/step_16_independent_review.template.json`
- Human output: `docs/quality/reviews/step_16_independent_review.json`
- The reviewer must inspect the package materials and answer its review questions.
- The completed `reviewer_id` must equal the independent reviewer's exact GitHub login.

## Step 18 / Issue #64 — security auditability

- Reviewed Product revision: `4ebec450bd87f2c29cc890dbd02941c7af953710`
- Review package: `docs/quality/review_packages/step_18_review_package.json`
- Package SHA-256: `7491e8ccd5c7a2b4d2a9d2ac4fcfbe0dd19699bcdd287ddc69a45925d499f306`
- Template: `docs/quality/reviews/step_18_independent_review.template.json`
- Human output: `docs/quality/reviews/step_18_independent_review.json`
- Existing automated security/privacy gates remain necessary but are not sufficient.
- The completed `reviewer_id` must equal the independent reviewer's exact GitHub login.

## Authenticated provenance after the review artifact is committed

For all four gates, the same independent GitHub account named in `reviewer_id` must post an issue
comment beginning exactly with `LUKART_HUMAN_REVIEW_PROVENANCE_V1` and an exact JSON attestation.
The runtime collector verifies GitHub's authenticated comment author, reviewer identity, decision,
review digest, and reviewed revision before it materializes a temporary provenance receipt.
Repository JSON cannot prove its own human provenance.

## Gate discipline

A template, issue comment written by the owner, commit, PR, merge, bot response, self-declared
`reviewer_kind=human`, or automated PASS is not a human review. Only a genuine independent human
artifact plus authenticated provenance with the exact required subject/revision/hash binding may
unlock these gates.

A FAIL or REJECTED review must remain blocking until the reviewed defect is corrected and a new
valid review is performed when required.
