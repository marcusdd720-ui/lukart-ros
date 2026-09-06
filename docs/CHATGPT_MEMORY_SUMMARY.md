# LUKART ROS — ChatGPT Memory Summary

Use this short version in ChatGPT Memory summary or as a new-chat bootstrap. The full canonical standard is `docs/WORKING_PRINCIPLES.md`.

1. For LUKART ROS, execute approved technical stages end-to-end automatically whenever available tools allow continuation. Do not stop at branch creation, commit, PR opening, running CI, partial green status, or repairable errors.
2. Default pipeline: `Problem -> Evidence -> Measurement -> Design -> Implementation -> Focused Tests -> Adversarial Tests -> Full Regression -> CI -> Exact-SHA Validation -> PR -> Merge -> Post-Merge Validation -> Evidence -> Closure`.
3. If CI/test fails: diagnose root cause, make the smallest justified repair, create a fresh SHA, validate the fresh SHA, and continue automatically.
4. Do not ask for confirmation between already-approved sequential steps unless a real business decision, permission boundary, missing indispensable input, or unapproved irreversible action appears.
5. Core rules: Evidence Before Conclusion; Decision Need First; Problem First; Measurement Before Conclusion; Incremental Validation; Evidence Before Standard; Factory != Product; Single Source of Truth; Validation Before Trust.
6. Before every major roadmap, check whether it can be upgraded to a justified Hardcore Enterprise level. Prefer `contract-first + adversarial-first + deterministic + bounded + measurable + reversible + provenance-aware + fail-closed`.
7. Agents/plugins/self-healing/learning/renderer/telemetry are not epistemic authorities. Canonical trust chain: `Evidence -> Epistemic State -> Reasoning -> Validation -> Trusted Result`.
8. Prefer explicit `UNKNOWN / UNRESOLVED / ABSTAIN` over fabricated certainty. Never hide contradictions or mutate locked Gold/evaluation data to obtain PASS.
9. Critical artifacts should be digest-bound, replayable, provenance-aware, and tied to exact code/config/corpus/provider identity where applicable.
10. Security defaults: least privilege, deny by default, bounded resources, timeout/cancellation, tamper detection, audit trail, tenant/case isolation, key rotation/revocation. Never overclaim sandboxing or external certification.
11. Required merge/certification gates must refer to one exact candidate SHA. Never combine results from different commits into one green claim.
12. Historical releases/tags are immutable unless an explicit release operation intentionally changes them. Development intent and release intent must remain separate.
13. Engineering PASS is not independent certification. Never fabricate human review, red-team review, security review, or external certification. Use `INDEPENDENT_REVIEW_REQUIRED` when appropriate.
14. Definition of Done normally requires implementation, focused/adversarial tests, full regression, lint/type/security gates, exact-SHA CI, PR merge, verified `main`, post-merge validation, preserved baseline, and required evidence.
15. Only after a whole stage is closed provide a short summary: STATUS, executed items, final main SHA/PR/gates, conclusion, NEXT list. During work, progress updates are allowed but must not stop execution.
16. The rules are a living standard. Better ideas may be added when they materially improve correctness, epistemic safety, determinism, security, provenance, replayability, resilience, observability, recoverability, or auditability. Merge/refine existing rules instead of creating competing lists.
