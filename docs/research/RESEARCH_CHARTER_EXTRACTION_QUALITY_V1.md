# Research Charter: Extraction Quality — v1.0

## Decision Need

Can the current LukArt ROS extraction pipeline be trusted to preserve the
facts that materially affect a legal review?

## Hypothesis

The approved extractor version can identify critical legal facts with:

- critical recall = 100%;
- overall entity F1 >= 90%;
- CASE_NUMBER false-positive rate = 0%.

A numeric confidence score is not accepted as evidence unless it is calibrated
against the versioned ground-truth corpus.

## Measurement

For every entity type and document type measure:

- precision;
- recall;
- F1;
- false-positive rate;
- critical recall;
- critical precision;
- relation precision/recall where relations are annotated;
- regression delta against the previous approved extractor baseline.

The release decision is based on the critical metrics first. Overall F1 cannot
compensate for failure on a critical fact.

## Experiment Design

Initial corpus: 20 documents, five per document type:

1. wyrok_sadowy;
2. decyzja_zus;
3. umowa;
4. pismo_procesowe.

Documents are manually annotated against the normative taxonomy in
`docs/quality/critical_facts_schema.yaml`.

The corpus is split into:

- development set: 12 documents;
- validation set: 4 documents;
- locked evaluation set: 4 documents.

The locked evaluation set is not used to tune extraction rules. Changes to the
extractor are evaluated against it only after the implementation is frozen for
the experiment.

For the initial study, one primary annotator may create the first labels, but
any document that becomes a release-critical benchmark must subsequently pass
an independent review before it is frozen.

## Provenance Requirement

Every extracted fact in the benchmark interface must carry:

- source document identifier;
- page;
- character start/end offsets in normalized source text;
- extractor version;
- source document SHA-256 when available;
- extraction method when available.

Ground-truth annotations must point to the same source location wherever the
fact is textually grounded. This prevents a score from being detached from its
source evidence.

## Acceptance Criteria

### Release-blocking

- critical recall >= 100%;
- no unresolved critical extraction regression;
- schema/taxonomy version is frozen for the evaluation;
- provenance is present for all evaluated extracted facts;
- PII/security gate = PASS.

### Quality target

- overall entity F1 >= 90%;
- CASE_NUMBER false-positive rate = 0%;
- relation F1 target >= 90% once relation annotations exist.

If a criterion is not measurable because the corpus is incomplete, the status
is `PENDING`, never `PASS` and never silently treated as zero.

## Decision Rules

PASS → freeze the measured baseline and allow the next implementation step.

FAIL → identify the failure mode, create a minimal corrective experiment, and
rerun the locked evaluation set.

PENDING → do not claim release readiness; first complete the missing
measurement infrastructure.

## Methodological Guardrails

1. Measurement precedes architectural expansion.
2. Criticality is defined before evaluation and cannot be changed to improve a
   score.
3. A passing engineering suite does not establish legal extraction quality.
4. A high overall F1 does not compensate for critical fact loss.
5. Every accepted extractor change requires regression measurement.
