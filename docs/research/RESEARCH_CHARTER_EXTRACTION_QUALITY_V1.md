# Research Charter: Extraction Quality — v1.0

## Decision Need

Can the current LukArt ROS extraction pipeline be trusted to preserve facts that materially affect legal review?

## Hypothesis

The approved extractor can identify critical legal facts with critical recall = 100%, overall entity F1 >= 90%, and CASE_NUMBER false-positive rate = 0%.

A numeric confidence score is not evidence unless calibrated against a versioned ground-truth corpus.

## Measurement

Measure precision, recall, F1, false-positive rate, critical recall, critical precision, relation precision/recall where annotated, and regression delta per entity/document type.

## Experiment Design

Initial corpus: 20 documents, five per type: `wyrok_sadowy`, `decyzja_zus`, `umowa`, `pismo_procesowe`.

Split: development 12, validation 4, locked evaluation 4. The locked set is not used for tuning.

Initial annotation may be produced by one primary annotator, but every release-critical benchmark must pass independent review before freezing.

## Provenance Requirement

Every evaluated extracted fact must carry source document identifier, page, normalized-text character offsets, extractor version, source SHA-256 when available, and extraction method when available.

## Acceptance Criteria

Release-blocking:
- critical recall >= 100%;
- no unresolved critical extraction regression;
- taxonomy/schema version frozen;
- provenance present for all evaluated extracted facts;
- PII/security gate = PASS.

Quality targets:
- overall entity F1 >= 90%;
- CASE_NUMBER false-positive rate = 0%;
- relation F1 >= 90% once relation annotations exist.

Incomplete measurement is `PENDING`, never `PASS` and never silently treated as zero.

## Decision Rules

PASS → freeze baseline and proceed.

FAIL → isolate failure mode, run a minimal corrective experiment, and rerun the locked set.

PENDING → complete the missing measurement infrastructure before claiming readiness.

## Guardrails

1. Measurement precedes architectural expansion.
2. Criticality is defined before evaluation and cannot be changed to improve a score.
3. Engineering tests do not establish legal extraction quality.
4. Overall F1 does not compensate for critical fact loss.
5. Every accepted extractor change requires regression measurement.
