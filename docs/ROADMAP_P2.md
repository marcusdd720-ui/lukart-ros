# LUKART ROS — P2 Roadmap

Status: Active implementation contract
Baseline: Post-v1 / Roadmap v1.1 merged at `7ab4201da74f1ca36471c92cb8fcfc907e815725`
Target: P2 semantic intelligence and bounded interoperability layer

## Execution order

1. P2-01 Semantic Regression Intelligence
2. P2-02 Automatic Blast-Radius Analysis
3. P2-03 Cross-Version Replay & Migration Engine
4. P2-04 Longitudinal Quality Intelligence
5. P2-05 Explainability Layer v2
6. P2-06 Gold Candidate Discovery
7. P2-07 Agent Runtime v2
8. P2-08 API / Interoperability Layer
9. P2-09 Scalability / Concurrency / Caching
10. P2-10 Provider / Plugin Ecosystem

## P2-01 Semantic Regression Intelligence

A change is evaluated at the meaning layer, not only by byte or test differences. Changes to
reasoning outcome, epistemic status, evidence/support lineage, open questions, contradictions,
or certainty are critical semantic changes and require explicit review.

Acceptance:
- deterministic semantic diff;
- field/path visibility;
- critical-vs-material classification;
- no automatic normalization of critical semantic divergence into PASS.

## P2-02 Automatic Blast-Radius Analysis

The system calculates the transitive dependent set for changed artifacts. Only known affected
artifacts are selected, unrelated artifacts remain outside the replay set, and the result is
deterministic.

Acceptance:
- transitive reverse-dependency traversal;
- deterministic affected-artifact list;
- explicit replay scope for changed evidence/facts/claims/conclusions.

## P2-03 Cross-Version Replay & Migration Engine

Cross-version comparison binds input and output digests, code/version identity and semantic
diff. Equal inputs with semantically divergent outputs are reviewable differences, not silent
migration success.

Acceptance:
- replay snapshot identity;
- same-input detection;
- output digest comparison;
- semantic divergence classification.

## P2-04 Longitudinal Quality Intelligence

Quality is compared across versions using explicit metric direction. Regression remains
visible even if other metrics improve. Missing metrics are not interpreted as improvement.

Acceptance:
- per-metric version comparison;
- IMPROVED / REGRESSED / STABLE / MISSING states;
- metric direction is explicit and versionable.

## P2-05 Explainability Layer v2

Explainability is generated from the actual Reasoning result. It exposes the decision,
support lineage, evidence references, open questions, decisive epistemic factors and bounded
counterfactual revalidation checks. It must not invent alternative facts.

Acceptance:
- support lineage is traceable;
- evidence references are retained;
- abstention/open questions remain visible;
- counterfactuals describe revalidation conditions, not fabricated outcomes.

## P2-06 Gold Candidate Discovery

Repeated validated failures may become Gold candidates, never Gold automatically. Public
candidate discovery only accepts synthetic/anonymized events. Promotion still requires the
existing independent review/freeze process.

Acceptance:
- repeated failure grouping;
- severity threshold;
- privacy boundary;
- CANDIDATE state only;
- no direct Gold promotion.

## P2-07 Agent Runtime v2

Agents remain bounded Pipeline workers. Routing is capability-based and deterministic.
Provider identity and version are checked on returned artifacts. Resource budgets fail closed.

Acceptance:
- class-registered provider identity;
- capability routing;
- max-step and max-input budgets;
- mismatched identity/task result rejected.

## P2-08 API / Interoperability Layer

External artifacts use versioned, digest-bound envelopes. Payload tampering or schema/version
absence fails closed. The envelope carries data, not epistemic authority.

Acceptance:
- schema + version required;
- canonical payload digest;
- deterministic serialization;
- tamper detection.

## P2-09 Scalability / Concurrency / Caching

Performance primitives remain bounded and deterministic at their boundaries. Parallel map
preserves input order. Cache has an explicit capacity and thread-safe LRU behavior.

Acceptance:
- bounded worker count;
- order-preserving parallel output;
- bounded thread-safe cache;
- no unbounded implicit concurrency.

## P2-10 Provider / Plugin Ecosystem

ProviderRegistry stores provider classes, never mutable provider instances as configuration
authority. Plugin identity is `plugin_id@version`; duplicates fail closed and capability
discovery is explicit.

Acceptance:
- class-based registry;
- versioned identity;
- duplicate rejection;
- deterministic provider enumeration;
- capability discovery.

## P2 trust boundary

P2 does not change the core Foundation invariants. Semantic regression analysis, explainability,
plugins, replay and agents may observe or transform typed artifacts only within their declared
contract. None of these layers can independently promote a candidate to trusted FACT, rewrite
locked Gold, suppress an unresolved contradiction, or certify itself.

## P2 Definition of Done

P2-01 through P2-10 are implementation-complete when their versioned contracts, executable
code and focused tests exist on one candidate SHA. They are engineering-validated only when
Ruff, MyPy, focused P2 tests, full Pytest and the repository Stage Gate pass on that exact SHA.
Any future analytical certification continues to require the applicable Gold/KQM/human-review
requirements rather than treating engineering PASS as analytical certification.
