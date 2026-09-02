# Gold Corpus Protocol — v1.0

## Purpose

Create a reproducible, anonymized reference set for measuring extraction quality without using production case material.

## Corpus contract

- 20 documents total.
- Five documents per normative document type: `wyrok_sadowy`, `decyzja_zus`, `umowa`, `pismo_procesowe`.
- Split: development 12, validation 4, locked evaluation 4.
- Every annotation has a normalized entity type, exact source value, and fixed criticality.
- Synthetic identifiers and parties are used in repository fixtures.

## Freeze protocol

The committed corpus is a **candidate** until an independent reviewer confirms that the annotations and criticality assignments are internally consistent with `docs/quality/critical_facts_schema.yaml`.

Only after that review may `review_status` become `independently_reviewed` and `status` become `locked`.

The locked evaluation split must not be used for extractor tuning, rule selection, threshold selection, or error-driven annotation changes.

## Change control

Any material annotation change requires a new corpus version. Do not rewrite a frozen corpus in place.

A benchmark result must record:

1. corpus id and version;
2. split;
3. extractor version;
4. source document hash when available;
5. metric output;
6. unresolved errors and critical-fact loss.

## Safety

No real case document, court/ZUS correspondence, identifiable party data, production export, or previously deleted case-specific artifact may enter this corpus.
