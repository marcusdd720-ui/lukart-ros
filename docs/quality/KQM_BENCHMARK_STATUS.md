# KQM Benchmark Status — v1.0

## Current state: PENDING

The synthetic 20-document corpus and deterministic evaluation primitives are committed, but the corpus is not independently reviewed or frozen. The current repository extractor also does not expose an entity-fact extraction interface; `knowledge/extractor.py` currently extracts document references/relations.

Therefore no legal extraction quality score is claimed at this stage.

## Implemented

- versioned synthetic gold corpus;
- development / validation / candidate-locked split;
- exact fact matching by document, entity type, and normalized value;
- precision, recall, F1;
- critical recall and critical precision;
- critical fact loss;
- document-level CASE_NUMBER false-positive rate;
- provenance completeness.

## Next measurement prerequisites

1. Independent review of the annotations and criticality assignments.
2. Freeze corpus v1.0 without using the locked split for tuning.
3. Expose current extraction output through an adapter that preserves `ExtractedFact` provenance.
4. Run development/validation experiments before evaluating the locked split.
5. Record the first reproducible KQM result and regression baseline.

Until these conditions are met, KQM remains `PENDING` by policy.
