# LukArt ROS — Quality Gates

## Release principle

A green process is not evidence that legal extraction is correct. Release readiness therefore requires two independent dimensions:

1. **Engineering integrity** — tests, static analysis, schema compatibility and deterministic graph behavior.
2. **Analytical validity** — measured extraction quality against a versioned ground-truth corpus.

Neither dimension may substitute for the other.

## Required gates

### Gate A — deterministic engineering
- Unit tests pass.
- Integration tests pass.
- Serialization round-trip tests pass.
- Graph integrity validation passes.
- Ruff passes.
- No placeholder CI jobs are allowed.

### Gate B — pipeline observability
Every execution must expose:
- terminal status: `success`, `partial`, or `failure`;
- stage-level status;
- warnings and errors;
- provenance metadata;
- input/content hashes where applicable;
- output artifact identity;
- schema version for persisted graph artifacts.

A numeric confidence score must not be fabricated from heuristics. It becomes a release metric only after calibration against ground truth.

### Gate C — extraction quality
Maintain a versioned, anonymized gold corpus with expected entities and relations. Track at minimum:
- precision;
- recall;
- F1;
- false-positive rate for high-risk entity types;
- missing-critical-fact rate;
- relation precision/recall;
- regression delta versus the previous approved baseline.

### Gate D — safety
A release is blocked when:
- a critical validation error occurs;
- a required stage fails;
- persisted data cannot be validated against its schema;
- a quality metric falls below its configured threshold;
- a critical regression is detected.

## Methodological rule

Measurement precedes architectural expansion. Any proposed improvement to extraction or scoring is treated as a hypothesis, evaluated against the gold corpus, and adopted only when the measured result improves without unacceptable regressions.
