# Production Validation & Certification Program

Status: IMPLEMENTED CONTROL PLANE / STEP 1 BLOCKED BY INDEPENDENT REVIEW

## Purpose

This program automates progression after P0-P7 without renumbering the completed Stage 0-16
Factory lifecycle. It is a separate evidence-driven control plane for the twenty production
validation, certification, hardening, and release-candidate activities.

The program is deliberately fail-closed. Automation may discover, validate, sequence, and report
work, but it may not fabricate an external review, invent a certification result, authorize locked
evaluation, publish private Case data, or convert missing evidence into PASS.

## Execution rule

Every push or pull request runs `Production Validation Program`.

The workflow starts at the first program step and advances through every step whose evidence already
satisfies its gate. It stops at the first blocker and publishes that blocker in the GitHub Actions
summary. A later merge that supplies valid evidence automatically causes the workflow to retry and
continue to the next blocker.

Controlled `BLOCKED` is a valid program state. It is not a CI failure and it is not equivalent to
COMPLETE.

## Program order

1. Extraction Gold Corpus — independent review and freeze.
2. ReferenceFactAgent improvement.
3. Extraction KQM certification attempt.
4. Reasoning Gold Corpus v2.
5. Independent review and freeze Reasoning Corpus.
6. Reasoning Engine KQM certification.
7. End-to-End Gold Cases.
8. Agent Certification Program.
9. Adversarial Gold Cases.
10. Case Replay regression suite.
11. Change Propagation stress tests.
12. Controlled Learning experiments.
13. Model / strategy benchmark and routing.
14. Automatic candidate generation.
15. Local private-case pilot.
16. Renderer / final dossier and report quality.
17. Performance / budgets / SLA.
18. Security / privacy hardening.
19. Release / versioning / migration policy.
20. LUKART v1 Release Candidate.

The canonical machine-readable registry is `factory/production_validation_registry.py`.

## Step 1 independent review gate

The current extraction corpus is explicitly still a candidate. Step 1 cannot pass until the exact
corpus bytes receive an independent review artifact at:

`docs/quality/reviews/extraction_gold_v1_review.json`

The review must:

- identify `extraction-gold-v1`;
- bind to the exact corpus SHA-256;
- identify a real independent reviewer;
- not use reserved automated identities such as `system`, `factory`, `agent`, or `lukart`;
- approve annotations;
- approve criticality assignments;
- explicitly approve freeze;
- record PASS for IAA when the review protocol says IAA is required.

A template is provided at
`docs/quality/reviews/extraction_gold_v1_review.template.json`.

The freeze is cryptographic: the accepted review binds the reviewed corpus bytes by SHA-256. If the
corpus changes later, the review gate fails with `REVIEW_HASH_MISMATCH` and the corpus is no longer
accepted as the reviewed/frozen version. The controller can also materialize a deterministic local
freeze manifest for downstream tooling.

The repository currently does not contain the independent review artifact, so Step 1 is truthfully
BLOCKED rather than PASS.

## Step 2-20 evidence contract

After Step 1, each step supplies a JSON evidence artifact:

`factory/production_validation_evidence/step_NN.json`

Minimum fields:

```json
{
  "schema_version": "1.0",
  "step": 2,
  "status": "PASS",
  "validated_sha": "FULL_40_CHARACTER_GIT_SHA",
  "evidence_sha256": "FULL_64_CHARACTER_SHA256",
  "critical_gates_passed": true
}
```

A step cannot advance if the step number does not match, status is not PASS, the Git SHA is not a
full commit identifier, the evidence digest is malformed, or critical gates are not explicitly
recorded as passed.

The minimum envelope is intentionally generic. Each implementation step must additionally document
its domain-specific measurement/certification/replay/privacy evidence. The generic control plane is
not permission to reduce those domain gates to a single Boolean.

## Locked evaluation

Locked evaluation remains protected. A step that needs first-use locked evaluation must satisfy the
existing corpus review/freeze protocol and add explicit authorization evidence. Development and
validation improvement must not tune against locked evaluation.

## Private cases

Step 15 is local-only. Real private Cases, evidence, PII, and legal documents must not be committed
to the public repository. Public CI may contain only synthetic/anonymized proof that the local-only
boundary works.

## Relationship to P4-P7

This control plane reuses rather than replaces the completed learning architecture:

`Measured Failure -> P4 Experiment/Promotion -> P5 Teaching -> P6 Fresh-SHA Readiness -> P7 Adversarial Verification`

When steps 2, 12, 13, or 14 use learning or candidate-generation mechanisms, they remain subject to
those existing contracts. The program orchestrator does not grant patch, merge, deployment, or
truth authority to agents.

## Release Candidate rule

Step 20 may become PASS only after Steps 1-19 have passed in order and the Release Candidate evidence
is bound to a validated revision. Engineering completion alone does not substitute for the remaining
production KQM and independent-review requirements.
