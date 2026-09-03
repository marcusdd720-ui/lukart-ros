# LUKART ROS / KOS — AGENTS.md

Version: 2.0
Status: Proposed Enterprise Operating Contract
Scope: Repository-wide
Owner: LukArt ROS Team

## 1. Purpose

This file defines the mandatory operating contract for coding agents, reviewers, automation, and AI-assisted engineering working in this repository.

It does not replace architectural ADRs or quality specifications. It operationalizes them.

Canonical references:

- `docs/architecture/adr/0000-project-principles.md`
- `docs/architecture/adr/0001-foundation-of-kos.md`
- `docs/QUALITY_GATES.md`
- `README.md`

If this file conflicts with an Accepted ADR or an explicit quality/safety invariant, the canonical ADR/invariant wins. The conflict must be reported instead of silently resolved.

## 2. Mission

LUKART ROS / KOS is not a generic chatbot project. It is a controlled, auditable Knowledge Operating System for case-based analytical work.

The target value loop is:

`Case -> Evidence -> Epistemic Model -> Reasoning -> Validation -> Result -> Renderer -> KQM -> Feedback`

The long-term agent loop is:

`Case -> Controlled Agents -> Result -> KQM -> Learning Event -> Experiment -> Validated Improvement -> Certified Agent vNext`

The system must prefer verifiable correctness over fluent output.

## 3. Non-negotiable principles

All agents MUST follow these principles:

1. **Single Source of Truth** — do not create competing canonical definitions.
2. **Validation Before Trust** — unvalidated data cannot be promoted into trusted state.
3. **Model Before Code** — define contracts, states, invariants, and expected behavior before implementation.
4. **Architecture Before Features** — features must fit the microkernel/modular architecture.
5. **Deterministic Execution** — deterministic components must remain reproducible for identical inputs.
6. **Typed Everything** — persistent and cross-boundary objects require explicit types/contracts.
7. **Traceability** — every knowledge/result element must be traceable to its source.
8. **Evidence Before Conclusion** — conclusions must be backed by explicit evidence chains.
9. **Measurement Before Conclusion** — quality claims require measured evidence.
10. **Validation Before Expansion** — architecture is not expanded merely because expansion is possible.
11. **Planned != Implemented != Validated != Certified** — status words are not interchangeable.
12. **Autonomy Within Control** — agents act only inside explicit contracts and validation gates.

## 4. Factory != Product

The repository has two conceptual domains.

### Factory

Factory builds, tests, validates, diagnoses, repairs, and releases the Product.

Examples:

- CI/CD
- static analysis
- Ruff
- MyPy
- pytest
- validation infrastructure
- CKV
- stage orchestration
- self-healing primitives
- change-propagation infrastructure

### Product / MVROS / KOS runtime

Product performs case-oriented knowledge work.

Examples:

- Case
- Evidence
- Knowledge Graph
- Epistemic state
- Reasoning
- Result
- Renderer / Report Engine
- KQM analytical measurement
- Controlled Agents

Agents MUST NOT justify Product incompleteness by increasing Factory complexity unless a measured Factory deficiency blocks Product validation.

## 5. Privacy boundary — FATAL invariant

Real case data is local-only.

The public GitHub repository may contain only code, tests, documentation, anonymized/synthetic fixtures, and non-sensitive artifacts approved for version control.

Real cases, source documents, personal data, case numbers, sensitive identifiers, and private evidence MUST NOT be:

- committed,
- pushed,
- uploaded to GitHub Actions,
- copied into public fixtures,
- included in CI logs,
- included in PR descriptions,
- included in issue bodies.

Private case storage uses `MVROS_DATA_ROOT` or the documented local fallback.

A privacy-boundary violation is **FATAL**. Stop work, do not propagate the data, and report the exact path/artifact involved.

## 6. Canonical engineering workflow

For any non-trivial change:

1. Read the relevant ADRs, contracts, tests, and current implementation.
2. State the decision need and the observable acceptance criteria.
3. Identify affected Product and Factory boundaries.
4. Create or update the smallest necessary model/contract first.
5. Implement the smallest vertical slice.
6. Add/modify tests that prove the intended behavior.
7. Run deterministic local/static validation where available.
8. Create a new commit/SHA.
9. Validate the new SHA in CI.
10. If CI fails, diagnose the real failure, repair it, create a fresh SHA, and validate again.
11. Do not declare COMPLETE until the Definition of Done is satisfied.

Prefer a branch + PR workflow for substantive changes.

## 7. Fresh-SHA rule — mandatory

A rerun of an old commit is not evidence that a new repair works.

After any code/configuration change intended to repair a failure:

`FAIL -> diagnosis -> repair -> NEW SHA -> validation -> PASS/FAIL`

The repair is not validated until the new SHA passes the required gates.

Agents MUST NOT report a stale workflow rerun as validation of a later change.

## 8. Failure handling and self-healing

Do not stop at the first CI error if the requested workflow requires completion.

Failure procedure:

1. Capture run/job/stage identity.
2. Read the failing step/log.
3. Classify failure: syntax/static/type/test/schema/privacy/integration/semantic/infrastructure.
4. Identify root cause, not only the last visible symptom.
5. Make the smallest justified repair.
6. Create a fresh SHA.
7. Re-run validation on the fresh SHA.
8. Continue to the next agreed stage only after PASS.

Blind retry is not self-healing.

Self-healing means **diagnosis + targeted repair + fresh validation**.

## 9. Evidence and provenance

Knowledge/results MUST preserve source provenance whenever the source contract supports it.

Expected provenance may include:

- source/document identifier,
- source location,
- page/section/line/span,
- content hash,
- repository or artifact revision,
- extraction/processor version,
- graph schema version.

A model-generated statement is not itself evidence.

Memory is not truth.

Previous agent output is not truth.

A prior conclusion may be reused only through an explicit validated artifact/provenance chain.

## 10. Epistemic discipline

The Product must evolve toward explicit epistemic states such as:

- `FACT`
- `CLAIM`
- `INTERPRETATION`
- `HYPOTHESIS`
- `CONCLUSION`
- `RECOMMENDATION`

Until the formal Epistemic Status Machine is implemented, agents MUST preserve these distinctions conceptually and MUST NOT silently promote uncertain statements into facts.

Examples of forbidden epistemic behavior:

- `CLAIM -> FACT` without new validating Evidence.
- contradiction resolved by model preference without evidence.
- recommendation represented as a fact.
- inferred intent represented as an observed event.

When evidence is insufficient, prefer explicit abstention/open question over fabrication.

## 11. Contradictions and unknowns

Contradictions MUST be represented, not hidden.

Expected future behavior:

- create explicit `CONTRADICTS` relations,
- preserve both sides and provenance,
- mark unresolved status,
- require a documented resolution rule or new evidence before resolution.

Unknowns MUST remain visible through an Open Questions mechanism/ledger as the Product evolves.

`UNKNOWN` or `UNRESOLVED` is a valid result.

## 12. Agent Step Contract

No production agent may operate without an explicit Agent Step Contract.

Minimum contract fields:

- `agent_id`
- `version`
- `purpose`
- `input_schema`
- `output_schema`
- `required_evidence`
- `provenance_requirements`
- `allowed_operations`
- `forbidden_operations`
- `epistemic_permissions`
- `validation_gates`
- `failure_modes`
- `resource_limits`
- `observability_requirements`

The contract defines authority, not merely documentation.

An agent attempting an operation outside its contract must fail closed.

## 13. Agent Layer target architecture

The planned controlled Agent Layer consists of:

1. Agent Contract
2. Agent Registry
3. Agent Runner
4. Validation Gate
5. Agent Evaluation
6. Agent Certification
7. Measurement Hook / KQM
8. Learning Events
9. Distillation/Teaching mechanisms
10. Capability-aware routing

Do not implement all components at once.

Build and validate one reference agent end-to-end first.

## 14. Agent Registry

The Agent Registry will be the authoritative catalog of executable agents.

It should eventually track:

- identity,
- semantic version,
- contract version,
- capabilities,
- dependencies,
- underlying model/provider where relevant,
- evaluation metrics,
- certification status,
- compatibility constraints.

Registry presence does not imply certification.

## 15. Agent status lifecycle

Use explicit states rather than vague readiness language.

Recommended lifecycle:

`DRAFT -> TESTED -> EVALUATED -> CERTIFIED -> PRODUCTION`

Exceptional terminal/intermediate states may include:

- `REJECTED`
- `DEPRECATED`
- `SUSPENDED`

Only agents meeting the required validation and KQM thresholds may be represented as certified.

## 16. Reference Agent rule

Before scaling to multiple agents, select one existing/small agent as the Reference Agent.

The Reference Agent must prove the entire lifecycle:

`Contract -> Registry -> Runner -> Output -> Provenance -> Validation -> KQM -> Certification -> Replay`

Architecture changes discovered during this vertical slice should be measured and incorporated before multiplying agent count.

## 17. Agent evaluation

Agent evaluation is separate from code tests.

Engineering PASS proves software integrity.

Agent evaluation must address analytical behavior such as:

- precision,
- recall,
- F1 where meaningful,
- provenance completeness,
- critical false-positive rate,
- missing-critical-fact rate,
- contradiction detection/handling,
- epistemic transition violations,
- abstention behavior,
- regression delta.

Do not invent confidence metrics without calibration.

## 18. Gold Corpus and KQM

A green CI pipeline is insufficient evidence of analytical correctness.

Gold/KQM must provide a versioned ground truth for Product evaluation.

Gold data must be synthetic or safely anonymized for repository use unless an approved local-only evaluation path is used.

Every proposed analytical improvement is a hypothesis.

Adopt it only when measurement demonstrates improvement without unacceptable regression.

## 19. Learning Events

The self-learning architecture MUST NOT directly mutate trusted knowledge, contracts, rules, prompts, or models from raw production outcomes.

Observed behavior should first become a `Learning Candidate` / `Learning Event` containing, where possible:

- agent/version,
- task,
- input identity/hash,
- output identity/hash,
- measured error/success,
- expected behavior,
- evidence/provenance,
- suspected cause,
- proposed lesson/improvement.

Promotion path:

`Observation -> Learning Candidate -> Experiment -> Measurement -> Promotion Gate -> Versioned Change`

No automatic promotion without a gate.

## 20. Distillation and teaching

Distillation is one learning mechanism, not the Learning System itself.

Possible improvement mechanisms include:

- prompt improvement,
- retrieval improvement,
- policy/rule improvement,
- routing improvement,
- structured examples,
- failure examples,
- distillation,
- fine-tuning,
- model replacement.

Training examples must come from validated/certified material, not raw unchecked agent output.

## 21. Controlled self-learning

Self-learning means controlled, measurable self-improvement — not uncontrolled self-modification.

Target loop:

`Case -> Agents -> Result -> KQM -> Learning Event -> Hypothesis -> Experiment -> New Version -> KQM -> Certification`

The system may propose changes automatically.

It may test candidates automatically within approved sandboxes.

It MUST NOT silently promote a candidate into canonical production state without the required validation/promotion policy.

## 22. Multi-agent orchestration

Multi-agent execution is a later capability and must preserve clear ownership and contracts.

Preferred pattern:

`Task -> required capabilities -> certified agent(s) -> execution -> reviewer/validator -> KQM`

Avoid free-form agent conversations as an architectural primitive.

Agent-to-agent communication should use typed artifacts/events when possible.

## 23. Adversarial verification

For high-risk reasoning, future architecture may use separate roles:

- Generator
- Challenger / Adversary
- Evidence verifier
- Validator / Reviewer

The adversary must not be allowed to alter source evidence or ground truth.

Debate is evidence generation/critique, not proof by majority vote.

## 24. Model/provider independence

Agent identity should be separated from the underlying LLM/provider where practical.

A contract should define capability and behavior; provider/model is an implementation/configuration choice subject to evaluation.

Changing a model requires regression evaluation before certification is inherited.

## 25. Renderer separation

Reasoning output must remain separable from presentation.

Target renderers include at least:

- structured JSON,
- Markdown report,
- timeline,
- evidence list/map.

Do not bury reasoning state exclusively inside prose.

## 26. Case Replay and reproducibility

The target replay artifact should identify enough information to reproduce an analytical run, including where applicable:

- input hashes,
- evidence hashes,
- pipeline version,
- code/repository SHA,
- ontology/schema version,
- agent/model versions,
- graph hash,
- renderer version,
- KQM/evaluator version,
- final output identity.

Immutable/hash-chained snapshots are preferred for audit-sensitive evolution.

## 27. Change Propagation

Do not equate Change Propagation with `run everything`.

The target capability is dependency-aware revalidation:

`changed component -> dependency graph -> affected downstream components -> selective validation -> gates`

Until a trustworthy dependency graph exists, prefer safe broader validation over pretending selective validation is correct.

## 28. Scope control and anti-over-engineering

Before adding a framework, service, agent, stage, abstraction, or infrastructure layer, answer:

1. What measurable problem does it solve?
2. What current blocker requires it?
3. What is the smallest experiment proving its value?
4. What new failure modes does it introduce?
5. Can an existing component satisfy the requirement?

If these answers are weak, defer the expansion.

## 29. Testing expectations

Changes should use the smallest sufficient set of tests plus broader required gates.

Typical order:

1. focused unit tests,
2. focused integration tests,
3. static/type/lint validation,
4. serialization/schema/graph integrity where affected,
5. full required CI,
6. KQM/gold evaluation for analytical changes.

Never weaken or delete a failing test merely to obtain green CI unless the test is demonstrably invalid and the reason is documented.

## 30. Quality-gate separation

Maintain two independent dimensions:

### Engineering integrity

Examples:

- Ruff
- MyPy
- pytest
- schema compatibility
- deterministic graph behavior
- serialization
- CI integrity

### Analytical validity

Examples:

- gold-corpus comparison
- extraction precision/recall
- reasoning support coverage
- contradiction handling
- unsupported-conclusion rate
- missing-critical-fact rate

Engineering PASS cannot substitute for analytical PASS.

## 31. Status reporting

Every material work item should use precise status vocabulary:

- `PLANNED` — accepted for future work, no implementation claim.
- `IN_PROGRESS` — implementation actively incomplete.
- `IMPLEMENTED` — code/artifact exists.
- `VALIDATED` — required engineering/behavioral validation passed.
- `CERTIFIED` — explicit certification criteria passed.
- `COMPLETE` — Definition of Done for the scoped item is satisfied.
- `BLOCKED` — cannot proceed because of a named dependency/blocker.

Never describe PLANNED as implemented or IMPLEMENTED as validated.

## 32. Definition of Done

A work item is COMPLETE only when all applicable conditions are satisfied:

- model/contract is explicit,
- implementation exists,
- tests exist and pass,
- required quality gates pass,
- documentation/SSoT is updated,
- privacy boundary is preserved,
- provenance/observability requirements are met,
- new SHA is validated,
- no known critical regression remains,
- status is recorded truthfully.

Analytical functionality additionally requires relevant measured KQM/gold evidence before certification/release claims.

## 33. Pull request expectations

A substantive PR should communicate:

- decision need,
- scope,
- files/components affected,
- invariants introduced/changed,
- tests executed,
- CI status,
- KQM impact when applicable,
- privacy impact,
- known limitations,
- rollback/recovery considerations where relevant.

Keep PRs small enough to review and replay.

## 34. Forbidden shortcuts

Agents MUST NOT:

- hide failing validation,
- fabricate test/KQM results,
- claim a workflow was run when it was not,
- treat stale-SHA results as proof of a repair,
- write private case data to the public repo,
- promote model output to fact without evidence,
- resolve contradictions by unsupported preference,
- invent provenance,
- fabricate numeric confidence,
- silently change accepted architectural principles,
- bypass gates for convenience,
- mark work COMPLETE because code merely compiles,
- build new Factory layers to avoid validating Product value.

## 35. Communication contract for AI agents

When reporting progress, distinguish:

- observed facts,
- inference/hypothesis,
- action taken,
- validation result,
- remaining blocker,
- next action.

Report failures early and specifically.

Do not stop a requested staged implementation merely to announce an expected intermediate failure if diagnosis and repair can continue safely.

Do not conceal uncertainty.

## 36. Priority roadmap guardrail

Current strategic ordering is:

### P0 — NOW

- Enterprise `AGENTS.md`
- secure repository/tool permissions
- Agent Step Contract
- Agent Registry
- Agent Runner / Validation Gate foundation
- Reference Agent
- Agent Evaluation / Certification foundation
- Gold/KQM closure for the first vertical slice

### P1 — SOON

- multi-agent Codex development workflow
- Epistemic Status Machine
- ContradictionAgent
- Reviewer Agent
- competency profiles / capability-aware routing
- Case Replay

### P2 — LATER

- Learning Events / Learning Candidates
- controlled teaching/distillation pipeline
- curriculum / failure corpus
- improved dependency-aware Change Propagation
- semantic self-healing experiments

### P3 — HARDCORE / EXPERIMENTAL

- controlled self-learning loop
- adversarial agent verification
- multi-agent verification protocols
- model/provider benchmarking and routing
- automatic candidate improvement experiments with gated promotion

This roadmap may change only based on measured need, validated dependencies, or an explicit architectural decision.

## 37. Final operating rule

The objective is not to maximize code, stages, agents, or automation.

The objective is to maximize:

- measured correctness,
- traceability,
- reproducibility,
- privacy,
- controlled autonomy,
- engineering reliability,
- analytical validity,
- and sustainable development speed.

When speed conflicts with unverifiable correctness, preserve correctness and improve the process that made correctness slow.
