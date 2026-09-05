# TM-1.0 — Kanon Modelu Czasu

Canonical ID: TM-1.0
Title: Kanon Modelu Czasu
Version: 1.0
Status: CANDIDATE CANON
Class: ONTOLOGY
Stability Index: 4
Owner: Core Architecture
Depends On: KMeta-1.0; CK-1.0; KMR-1.0
Affects: KMS; KMP; Evidence; Reasoning; Timeline; Case Replay; Strategy
Supersedes: none
Validation Method: temporal-consistency tests + replay + synthetic legal timeline cases
Review Requirement: independent architectural review before CANONICAL
Change Policy: versioned semantic change only

## 1. Purpose

TM-1.0 defines temporal semantics required to distinguish what happened, when a source was created, when the system learned about it, and when a proposition was believed to be valid.

## 2. Required time axes

Artur OS MUST distinguish at least:

1. `event_time` — when an event occurred or a state became true in the represented reality;
2. `source_time` — when a source/document was created, issued, signed, published or recorded;
3. `knowledge_time` — when Artur OS received, extracted or registered the information;
4. `system_time` — when a model/object version was committed by the system.

These values MUST NOT be silently collapsed into one timestamp.

## 3. Optional validity interval

Where semantics require an interval, a proposition may have:

`valid_from` and `valid_to`.

Absence of `valid_to` does not automatically mean infinity. It may mean unknown or still-open depending on type contract.

## 4. Uncertain time

Temporal uncertainty is explicit. A time expression may be:

- exact,
- bounded interval,
- approximate,
- relative,
- unknown,
- disputed.

An approximate or inferred date MUST NOT be stored as exact without preserving the inference status and provenance.

## 5. Temporal provenance

Every parsed or inferred time value MUST retain a link to the source or transformation that produced it when provenance is available.

## 6. Knowledge revision

Later knowledge may change what Artur believes about `event_time` without rewriting the historical fact that an earlier model version held a different view.

Therefore:

- event/source time may be corrected through a new object version;
- knowledge/system time of the prior version remains immutable;
- Case Replay MUST be able to reconstruct what was known at an earlier knowledge time.

## 7. Ordering

Temporal order is a derived relation and may be partial.

If two events cannot be reliably ordered, the model MUST preserve that uncertainty instead of inventing an order.

## 8. Legal/process deadlines

Deadline calculation is outside TM core semantics, but any deadline engine MUST consume explicit temporal values and legal rules. TM does not infer legal consequences from dates by itself.

## 9. Timeline view

A timeline is a projection of temporally annotated cognitive objects. It is not an independent source of truth.

The renderer/timeline layer MUST preserve links back to object versions and provenance.

## 10. Failure modes

Temporal processing MUST fail closed or mark unresolved when:

- a required timezone/locale changes interpretation and is unavailable;
- source text supports only an approximate time but exact time is requested;
- conflicting source dates cannot be reconciled by evidence;
- relative expressions lack a reliable anchor;
- an update would overwrite historical knowledge time;
- event/source/knowledge time are conflated in a way that changes reasoning.

## 11. Validation

TM-1.0 remains Candidate until:

1. synthetic cases cover event/source/knowledge/system-time divergence;
2. timeline/replay preserves earlier knowledge states after later correction;
3. current timeline implementation is mapped to TM semantics;
4. KMS/KMP use TM without duplicating time definitions;
5. exact-SHA CI/Audit/Stage Gate passes;
6. independent architectural review approves before CANONICAL.
