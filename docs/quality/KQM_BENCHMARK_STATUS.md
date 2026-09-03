# KQM Benchmark Status — v1.1

## Current state: TECHNICAL BASELINE VERIFIED / PRODUCTION RELEASE PENDING

The repository now contains a complete technical measurement path for a controlled
agent:

`Gold Corpus -> Agent Registry -> Agent Runner -> ReferenceFactAgent -> Validation Gate -> KQM -> Certification`

The synthetic 20-document corpus remains a **candidate** and is not independently
reviewed or frozen. Therefore this document does **not** claim production/legal
extraction quality and the locked evaluation split remains untouched.

## Verified technical capabilities

- versioned synthetic gold corpus;
- development / validation / locked-evaluation split;
- exact fact matching by document, entity type, and normalized value;
- precision, recall, F1;
- critical recall and critical precision;
- critical fact loss;
- document-level CASE_NUMBER false-positive rate;
- provenance completeness;
- controlled Agent Runner adapter preserving `ExtractedFact` provenance;
- reproducible development and validation measurement for `ReferenceFactAgent v1.0.0`;
- measured certification decision with explicit thresholds;
- locked split protection during the P0 vertical slice.

## First reproducible baseline

Agent: `ReferenceFactAgent v1.0.0`

Extractor backend: `regex-generic-v1`

Corpus: `extraction-gold-v1`

Corpus status: `candidate_pending_independent_review`

Review status: `not_reviewed`

### Development split

| Metric | Result |
|---|---:|
| True positive | 18 |
| False positive | 20 |
| False negative | 42 |
| Precision | 0.473684 |
| Recall | 0.300000 |
| F1 | 0.367347 |
| Critical true positive | 8 |
| Critical false positive | 8 |
| Critical false negative | 34 |
| Critical recall | 0.190476 |
| Critical precision | 0.500000 |
| Critical fact loss | 34 |
| CASE_NUMBER false-positive rate | 0.000000 |
| Provenance completeness | 1.000000 |

### Validation split

| Metric | Result |
|---|---:|
| True positive | 6 |
| False positive | 6 |
| False negative | 14 |
| Precision | 0.500000 |
| Recall | 0.300000 |
| F1 | 0.375000 |
| Critical true positive | 3 |
| Critical false positive | 3 |
| Critical false negative | 11 |
| Critical recall | 0.214286 |
| Critical precision | 0.500000 |
| Critical fact loss | 11 |
| CASE_NUMBER false-positive rate | 0.000000 |
| Provenance completeness | 1.000000 |

## Certification result

The current experimental policy requires:

- precision >= 0.95;
- recall >= 0.90;
- F1 >= 0.92;
- critical recall >= 0.95;
- provenance completeness = 1.0;
- critical fact loss = 0;
- CASE_NUMBER false-positive rate = 0.0.

`ReferenceFactAgent v1.0.0` is therefore **REJECTED for certification** on the
validation split. The failed criteria are precision, recall, F1, critical recall,
and critical fact loss.

This is a successful KQM outcome: the framework correctly distinguishes a
technically valid, provenance-complete agent from an agent whose analytical quality
is not sufficient for certification.

## Locked evaluation policy

The `locked_evaluation` split was **not executed** during the P0 vertical slice.
It must remain untouched until:

1. annotations and criticality assignments receive independent review;
2. corpus v1 is frozen;
3. development/validation improvements are completed without tuning against the
   locked split;
4. the evaluation protocol authorizes the first locked evaluation.

## Remaining blockers before production KQM

1. Independent review of annotations and criticality assignments.
2. Freeze the candidate corpus as an immutable gold corpus version.
3. Record independent annotation agreement (IAA) where required by the research
   protocol.
4. Improve extraction quality using development/validation only.
5. Re-run certification on fresh agent/extractor versions.
6. Execute the locked split only after the preceding gates are satisfied.

Until these conditions are met, **production KQM remains PENDING by policy** even
though the technical KQM measurement path and first baseline are VERIFIED.
