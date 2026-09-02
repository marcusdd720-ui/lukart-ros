# LukArt ROS — Quality Gates

## Release principle

A green process is not evidence that legal extraction is correct. Release readiness therefore requires two independent dimensions:

1. **Engineering integrity** — tests, static analysis, schema compatibility and deterministic graph behavior.
2. **Analytical validity** — measured extraction quality against a versioned ground-truth corpus.

Neither dimension may substitute for the other.

### Gate A — deterministic engineering
- Unit tests pass.
- Integration tests pass.
- Serialization round-trip tests pass.
- Graph integrity validation passes.
- Ruff passes.
- No placeholder CI jobs are allowed.

### Gate B — pipeline observability
Every execution must expose terminal status (`success`, `partial`, or `failure`), stage status, warnings/errors, provenance metadata, input/content hashes where applicable, output identity, and graph schema version.

A numeric confidence score must not be fabricated from heuristics. It becomes a release metric only after calibration against ground truth.

### Gate C — extraction quality
Maintain a versioned, anonymized gold corpus with expected entities and relations. Track precision, recall, F1, high-risk false-positive rate, missing-critical-fact rate, relation precision/recall, and regression delta.

### Gate D — safety
A release is blocked when a critical validation error occurs, a required stage fails, persisted data cannot be validated, a configured quality threshold is missed, or a critical regression is detected.

## Methodological rule

Measurement precedes architectural expansion. Any proposed improvement to extraction or scoring is a hypothesis, evaluated against the gold corpus, and adopted only when the measured result improves without unacceptable regressions.
