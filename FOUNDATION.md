# LUKART ROS / KOS — Foundation

Status: Active foundation contract

## Mission

LUKART ROS / KOS is a controlled, auditable environment for case-based analytical work.
It is not designed as a generic chatbot. The system structures evidence, preserves epistemic
status, executes bounded analytical components, validates reasoning, renders structured
results, and measures quality before trust is granted.

The target Product value loop is:

`Case -> Evidence -> Epistemic Model -> Reasoning -> Validation -> Result -> Renderer -> KQM -> Feedback`

The long-term controlled-learning loop is:

`Case -> Controlled Agents -> Result -> KQM -> Learning Event -> Experiment -> Validated Improvement -> Certified Version`

## Authority and Single Source of Truth

Repository decisions are governed in this order:

1. Accepted architecture decision records in `docs/architecture/adr/`.
2. Explicit safety, privacy, quality, schema, and validation invariants.
3. `AGENTS.md` as the repository-wide operating contract for agents and automation.
4. This foundation and the master roadmap.
5. Component documentation and implementation notes.

A lower-level document must not silently override a higher-authority invariant.

## Factory is not Product

### Factory

Factory builds, tests, validates, diagnoses, repairs, and releases Product code. It includes
GitHub Actions, stage orchestration, static analysis, test gates, audits, self-healing
primitives, and development/release automation.

### Product

Product performs case-oriented knowledge work. Its current architecture includes:

- Case and local-only case storage;
- Evidence and provenance;
- Knowledge Graph;
- epistemic status control;
- controlled Agent Layer;
- controlled multi-agent workflow and capability routing;
- Reasoning Core;
- Renderer/Result presentation layer;
- KQM/Gold measurement infrastructure.

Learning and self-improvement remain gated evolution layers, not implicit Product authority.

## Non-negotiable invariants

1. Evidence Before Conclusion.
2. Measurement Before Conclusion.
3. Validation Before Trust.
4. Model/Contract Before Code for cross-boundary behavior.
5. Typed, explicit artifacts across architectural boundaries.
6. Deterministic components remain reproducible for identical inputs.
7. Provenance is preserved whenever the source contract supports it.
8. Unknown and unresolved states remain visible; abstention is valid behavior.
9. Contradictions are represented and cannot be resolved by model preference alone.
10. Agent capability does not imply certification.
11. Engineering PASS does not imply analytical certification.
12. Any repair requires a fresh SHA before it can be treated as validated.
13. Renderer code may present reasoning state but cannot rewrite it.
14. Measurement code may observe quality but cannot silently promote Product state.
15. Raw production outcomes cannot directly mutate trusted knowledge, prompts, rules,
    contracts, models, or certification state.

## Privacy boundary

Real cases and sensitive case material are local-only. Public GitHub and GitHub Actions may
contain code, documentation, and approved synthetic/anonymized fixtures only.

Private runtime storage uses `MVROS_DATA_ROOT` or the documented local fallback. A privacy
boundary violation is FATAL and must not be propagated through commits, CI logs, fixtures,
or pull-request content.

## Epistemic model

The canonical knowledge statuses include:

- `FACT`
- `CLAIM`
- `INTERPRETATION`
- `HYPOTHESIS`
- `CONCLUSION`
- `RECOMMENDATION`
- `UNKNOWN`
- `UNRESOLVED`
- `REJECTED`

The canonical `EpistemicStatusMachine` controls promotions. In particular, uncertain states
cannot be promoted to `FACT` without new Evidence satisfying the transition contract.

## Agent model

Agents are bounded Pipeline workers, not unconstrained autonomous personas. Production agent
execution requires a contract, registry identity/version, validation gate, provenance,
resource limits, and quality/certification policy where applicable.

Preferred execution pattern:

`Task -> Required Capability -> Certified Agent -> Typed Artifact -> Validation -> KQM`

## Reasoning model

The Reasoning Core evaluates explicit typed artifacts and evidence-backed support lineages.
It does not invent missing facts or missing conclusions. Unsupported, unresolved, cyclic, or
otherwise invalid critical reasoning causes `ABSTAIN` and explicit Open Questions.

## Renderer model

Presentation is separated from reasoning. A renderer consumes an immutable structured result
and produces a deterministic presentation artifact tied to the source result digest.
Presentation must never become an alternate reasoning authority.

Existing Case/Dossier renderers remain valid for their own domain. Reasoning-result renderers
are adapters for `ReasoningRunResult`; they do not replace Case timeline semantics.

## Measurement model

KQM is independent of engineering tests. Gold corpora are versioned, synthetic/anonymized in
public repository use, and split so development/validation cannot tune against locked
evaluation data.

A candidate corpus is not production ground truth until the required independent review and
freeze protocol is satisfied.

## Controlled learning boundary

Future learning is permitted only through an auditable promotion path:

`Observation -> Learning Candidate -> Experiment -> Measurement -> Promotion Gate -> Versioned Change`

Self-learning means controlled measurable improvement, not uncontrolled self-modification.

## Reproducibility

Material analytical runs should be replayable with sufficient identity for input/evidence
hashes, schemas, pipeline/code SHA, agent/contract versions, graph state, renderer version,
and measurement/evaluator version.

## Definition of trustworthy progress

A feature moves from planned to implemented only when code/artifacts exist. It becomes
validated only after the required gates pass on the exact SHA. Analytical certification
additionally requires relevant measured KQM/Gold evidence. These states must never be
reported as interchangeable.
