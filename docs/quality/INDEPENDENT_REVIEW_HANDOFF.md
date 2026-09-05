# Independent Review Handoff

This handoff prepares the four external human gates without approving any of them.
Automation, bots, agents, system identities, and the Factory are not valid independent reviewers.

## Step 1 / Issue #50 — extraction-gold-v1

- Review subject: `data/quality/extraction_gold_v1.json`
- Exact SHA-256: `8f184c7944393d4fe617b24f900754f1dd8957ee1a43a4a9c0144e15ddd26ee8`
- Template: `docs/quality/reviews/extraction_gold_v1_review.template.json`
- Human output: `docs/quality/reviews/extraction_gold_v1_review.json`
- After valid APPROVED review: allow deterministic corpus freeze and continue Step 1 -> Step 3.

## Step 5 / Issue #51 — reasoning-gold-v2

- Review subject: `data/quality/reasoning_gold_v2.json`
- Exact SHA-256: `b51956dc82264ab4ae6bb7a183efa926ae087fc52b8b074fbb6468dd08614851`
- Template: `docs/quality/reviews/reasoning_gold_v2_review.template.json`
- Human output: `docs/quality/reviews/reasoning_gold_v2_review.json`
- Locked evaluation must not be used for tuning.
- After valid APPROVED review: allow deterministic corpus freeze and continue Step 5 -> Step 6 -> Step 8.

## Step 16 / Issue #62 — renderer/dossier quality

- Reviewed product revision: `32da9ed623c193ff234da5c0afa273b944e52390`
- Review package: `docs/quality/review_packages/step_16_review_package.json`
- Package SHA-256: `9bf3851073508a007b42ce0ebc6911e7ab7107eca7e7355d8d2cf667e0a388a9`
- Template: `docs/quality/reviews/step_16_independent_review.template.json`
- Human output: `docs/quality/reviews/step_16_independent_review.json`
- The reviewer must inspect the package materials and answer its review questions.

## Step 18 / Issue #64 — security auditability

- Reviewed product revision: `32da9ed623c193ff234da5c0afa273b944e52390`
- Review package: `docs/quality/review_packages/step_18_review_package.json`
- Package SHA-256: `1aab28f24251c8dadb98c5329cf218211927c825f875aed7b286436c8beafb94`
- Template: `docs/quality/reviews/step_18_independent_review.template.json`
- Human output: `docs/quality/reviews/step_18_independent_review.json`
- Existing automated security/privacy gates remain necessary but are not sufficient.

## Gate discipline

A template, issue comment, commit, PR, merge, bot response, or automated PASS is not a human review.
Only a genuine independent human artifact with the exact required subject/revision/hash binding may unlock these gates.
A FAIL or REJECTED review must remain blocking until the reviewed defect is corrected and a new valid review is performed when required.
