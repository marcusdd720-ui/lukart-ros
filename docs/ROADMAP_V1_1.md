# LUKART ROS — Roadmap v1.1

Status: Active
Baseline: `v1.0.1 @ 802013c4d0e53dc12306a97e1877ebba86af64a7`
Governance: `MASTER_PLAN.md` + `FOUNDATION.md`

This roadmap hardens, integrates, measures, and certifies the existing cognitive stack. It does
not treat already implemented Reasoning, epistemic, Renderer, KQM, replay, propagation, or
controlled-learning primitives as greenfield modules.

## P0-01 — Governance

Deliverables:
- immutable baseline declaration;
- fixed Post-v1 execution order;
- certification matrix;
- separation of runtime, evaluation, and governance changes;
- stale RC issue disposition policy.

Acceptance:
- v1.0.1 locked artifacts cannot be edited to manufacture v1.1 PASS;
- every certification claim is tied to exact SHA/versioned evidence;
- historical RC issues do not silently become v1.1 blockers.

## P0-02 — Gold Corpus v1.1

Deliverables:
- versioned synthetic/anonymized corpus;
- manifest containing corpus version/hash and per-case input identity;
- positive and negative cases covering FACT, CLAIM, HYPOTHESIS, INTERPRETATION,
  RECOMMENDATION, transition rules, insufficient evidence, contradictions, unresolved state,
  ABSTAIN, provenance, replay, renderer fidelity, propagation, and controlled self-healing;
- frozen release-evaluation split independent from candidate tuning.

Acceptance:
- corpus identity is deterministic and independently versioned;
- locked historical data is untouched;
- expected semantic results are explicit rather than inferred from renderer text.

## P0-03 — Cognitive Vertical Slice

Target path:

`Evidence -> Knowledge -> Epistemic State -> Reasoning -> KQM -> Renderer -> Provenance -> Replay`

Required negative paths:
- missing evidence;
- conflicting evidence;
- UNKNOWN;
- UNRESOLVED;
- REJECTED;
- ABSTAIN;
- open questions;
- partial input;
- damaged provenance.

Acceptance:
- identical input + code + config + schema/component versions yields the same canonical
  semantic result and replay identity;
- failures remain explicit and cannot be cosmetically rendered as success.

## P0-04 — Epistemic/Reasoning invariants

Required invariants:
1. FACT without qualifying evidence is impossible.
2. Illegal epistemic transitions fail closed.
3. Absence of evidence cannot inflate certainty.
4. Unresolved contradictions remain represented until explicitly resolved by admissible input.
5. Unresolved questions remain unresolved until answered by admissible input.
6. Renderer cannot alter epistemic status.
7. Self-healing cannot autonomously promote a hypothesis/candidate to FACT.
8. Adapter paths cannot bypass the Reasoning Core where the Reasoning contract applies.

Acceptance:
- invariant suite is a mandatory PR gate and a release gate.

## P0-05 — Renderer fidelity

Renderer must preserve the semantic contract of its immutable source artifact.

It must not:
- increase certainty;
- remove caveats;
- drop evidence references required by the source contract;
- alter epistemic status;
- hide open questions or contradictions;
- invent a conclusion absent from the Reasoning artifact.

Acceptance:
`Reasoning Artifact -> Render -> semantic comparison = PASS`.

## P0-06 — Replay / Provenance

Deliverables:
- canonical serialization;
- content hashes;
- versioned artifacts;
- provenance continuity checks;
- tamper detection;
- deterministic replay;
- replay identity carrying code, config, schema, corpus/evaluator and relevant component
  versions.

Acceptance:
- unchanged material input replays identically;
- a material evidence mutation changes the expected identity and is detected;
- broken provenance is a visible failure, not an implicit fallback.

## P0-07 — Propagation / Self-Healing safety

Required workflow:

`Observation -> Candidate -> Quarantine -> Validation -> Promotion Gate -> Versioned Change -> Monitoring`

Deliverables:
- candidate state;
- quarantine;
- validation;
- explicit human/policy promotion;
- audit trail;
- rollback;
- propagation scope / affected-artifact inventory;
- replay after promoted change.

Acceptance:
- no direct candidate -> FACT/trusted-state path;
- locked Gold and historical evidence are immutable;
- change propagation is measurable and reversible.

## P1-01 — KQM

Required metrics:
- evidence coverage;
- epistemic accuracy;
- abstention precision;
- contradiction detection;
- unsupported conclusion rate;
- renderer fidelity;
- replay determinism;
- provenance integrity;
- propagation correctness.

Each metric has:
`baseline -> warning threshold -> release threshold -> evidence source`.

Acceptance:
- release policy consumes machine-readable metrics;
- thresholds are versioned and are not silently relaxed by candidate code.

## P1-02 — Failure Corpus

Add synthetic/adversarial cases for:
- false/fabricated documents;
- conflicting dates;
- conflicting sources;
- missing pages;
- invalid metadata;
- incomplete OCR;
- hostile instructions embedded in evidence;
- duplicates;
- stale evidence;
- evidence poisoning.

Acceptance:
- failures exercise both detection and safe behavior;
- hostile document text never becomes control-plane authority.

## P1-03 — Controlled Learning

Required lifecycle:

`Failure -> Candidate -> Experiment -> Validation -> Promotion -> Monitoring -> Rollback`

Deliverables:
- promotion budget;
- contamination protection;
- immutable audit record;
- reviewer/policy identity;
- rollback trigger and procedure.

Acceptance:
- raw production outcome cannot directly mutate trusted knowledge, prompts, rules, schemas,
  certification state, or Gold truth.

## P1-04 — Performance

Measure before optimizing:
- end-to-end latency;
- peak memory;
- graph size;
- Reasoning runtime;
- replay runtime;
- renderer runtime;
- full-case runtime.

Acceptance:
- metrics are recorded with environment/context;
- release budgets are broad enough to avoid brittle shared-runner noise;
- regressions can be detected without confusing performance with analytical correctness.

## P1-05 — Security / Privacy

Required coverage:
- hostile evidence;
- prompt/instruction injection inside documents;
- provenance spoofing;
- unsafe file handling;
- secret leakage;
- PII boundary;
- dependency integrity.

Acceptance:
- public repo/CI uses only approved synthetic/anonymized fixtures;
- evidence is data, never trusted control-plane instruction;
- security/privacy failure blocks release and appropriate failures block PRs.

## P1-06 — CI architecture

PR fast gates:

`lint -> types -> unit -> invariants -> focused integration`

Release/certification gates:

`Gold -> Cognitive E2E -> Replay -> KQM -> Security -> Performance -> Evidence bundle`

Acceptance:
- PR and release responsibilities are explicit;
- certification evidence is generated for the exact candidate SHA;
- a skipped required gate cannot be reported as PASS.

## P1-07 — Documentation

Required runbooks:
- architecture map;
- troubleshooting;
- developer workflow;
- release/certification runbook;
- corpus maintenance;
- replay procedure;
- incident procedure.

Acceptance:
- operator can reproduce the documented validation/release path without relying on chat
  history;
- documentation references versioned repository contracts and actual automation.

## P2 entry condition

P2 begins only after P0-01 through P1-07 are implemented as repository artifacts and their
applicable checks are wired into the Post-v1 validation path. P2 is strategic development;
its scope is chosen from measured gaps rather than feature count.