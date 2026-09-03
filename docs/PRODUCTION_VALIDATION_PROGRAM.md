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

The canonical machine-readable registry is `factory/production_validation_registry.py`. In addition
to the order and gate category, every non-review step declares an exact `evidence_kind` and a set of
required named checks. An evidence artifact from one step therefore cannot be silently reused as
proof for another step.

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

## Step 5 independent review gate

Step 5 uses the same fail-closed review model for `reasoning-gold-v2`. It is not a generic PASS JSON.
The exact bytes of `data/quality/reasoning_gold_v2.json` must be independently reviewed and bound by
SHA-256 in `docs/quality/reviews/reasoning_gold_v2_review.json`. A changed reasoning corpus invalidates
the prior review and requires a new independent review before a new freeze can be accepted.

## Bound evidence contract for Steps 2-4 and 6-20

Each non-review step has two artifacts:

1. a small evidence envelope at `factory/production_validation_evidence/step_NN.json`;
2. a separate JSON validation report named by `artifact_path` in that envelope.

The evidence envelope uses schema 2.0:

```json
{
  "schema_version": "2.0",
  "step": 2,
  "status": "PASS",
  "validated_sha": "FULL_40_CHARACTER_GIT_SHA",
  "gate_kind": "implementation",
  "evidence_kind": "reference_fact_agent_improvement",
  "artifact_path": "reports/production_validation/step_02.json",
  "artifact_sha256": "FULL_64_CHARACTER_SHA256_OF_REPORT_BYTES",
  "critical_gates_passed": true
}
```

The controller rejects a missing artifact, an absolute/path-traversal path, a self-reference, a
non-JSON artifact, a malformed digest, or any digest that does not equal SHA-256 of the exact report
bytes. This prevents a standalone JSON envelope from fabricating completion.

The bound report uses schema 1.0 and must repeat the step identity, exact validated Git SHA,
`gate_kind`, and `evidence_kind`. It must explicitly state that locked evaluation was not used for
tuning and private data was not committed. It also contains named checks:

```json
{
  "schema_version": "1.0",
  "step": 2,
  "status": "PASS",
  "validated_sha": "FULL_40_CHARACTER_GIT_SHA",
  "gate_kind": "implementation",
  "evidence_kind": "reference_fact_agent_improvement",
  "locked_evaluation_used_for_tuning": false,
  "private_data_committed": false,
  "checks": [
    {"name": "agent_version_changed", "status": "PASS"},
    {"name": "development_metrics_recorded", "status": "PASS"},
    {"name": "validation_metrics_recorded", "status": "PASS"},
    {"name": "locked_evaluation_untouched", "status": "PASS"}
  ]
}
```

Every declared check must be PASS, duplicate check names are rejected, and all required checks from
the canonical registry must be present. Different program steps have different required checks, so
for example replay evidence cannot satisfy a certification gate and a release report cannot satisfy
a privacy gate merely by declaring `PASS`.

The control plane still does not invent domain measurements. Step-specific tools must create the
underlying reports from real execution. The strengthened contract makes those reports cryptographically
bound and structurally required instead of trusting a Boolean assertion.

## Locked evaluation

Locked evaluation remains protected. A step that needs first-use locked evaluation must satisfy the
existing corpus review/freeze protocol and add explicit authorization evidence. Development and
validation improvement must not tune against locked evaluation. Every generic bound report must
explicitly record `locked_evaluation_used_for_tuning: false`.

## Private cases

Step 15 is local-only. Real private Cases, evidence, PII, and legal documents must not be committed
to the public repository. Public CI may contain only synthetic/anonymized proof or a non-sensitive
attestation that the local-only boundary works. Every generic bound report must explicitly record
`private_data_committed: false`.

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
