# LUKART ROS — Case Intake & Response Protocol (CIRP) v1.0

Status: **CIRP-02 engineering baseline**

CIRP is the fail-closed Product protocol for converting a new case document or material case event into an evidence-bound procedural assessment and, in later stages, a best-justified action package. It is not a legal-source database, not an autonomous filing authority, and not a second source of truth.

## Authority and privacy

- `docs/WORKING_PRINCIPLES.md` remains the single canonical living engineering standard.
- Canonical Case Ledger remains the sole authoritative writable SSOT for case history.
- CIRP outputs are typed, versioned **derived artifacts** tied to exact inputs and rule identities.
- Real-case documents, names, signatures, case numbers and sensitive evidence remain local-only. Public GitHub and CI may contain code, documentation and synthetic/anonymized fixtures only.
- Missing evidence, unknown rules, conflicting service data and unresolved procedural state fail closed.

## Product objective

For every new document or material event CIRP is designed to establish, or explicitly abstain from establishing:

`Document → Procedural Posture → Service/Receipt → Deadline → Remedy/Route → Evidence Gaps → Strategy → Filing Topology → Filing Plan → Preflight → Report`

A new material document or changed critical input creates a new CIRP run; historical analyses are not silently rewritten.

## Stage scope

`CIRP-01` defines boundary contracts, canonical serialization and enforceable invariants.

`CIRP-02` adds generic executable deadline semantics and a fail-closed deadline guard. It deliberately does **not** embed jurisdiction-specific production rules, retrieve legal sources, infer missing trigger facts, perform strategy reasoning, generate documents, transmit filings to an authority, or monitor external proceedings.

Runtime stages are planned as:

1. `CIRP-01` — Contracts & Invariants.
2. `CIRP-02` — Procedural Rule Pack + Deadline Guard.
3. `CIRP-03` — Remedy + Evidence Gap.
4. `CIRP-04` — Strategy + Filing Topology.
5. `CIRP-05` — Filing Plan + Hardcore Preflight + Report.
6. `CIRP-06` — Adversarial / Replay / Integration.

## Contract identities

CIRP v1 uses explicit schema identities:

- `lukart.cirp.run.v1`
- `lukart.cirp.document-assessment.v1`
- `lukart.cirp.procedural-assessment.v1`
- `lukart.cirp.service-assessment.v1`
- `lukart.cirp.deadline-assessment.v1`
- `lukart.cirp.legal-source-ref.v1`
- `lukart.cirp.procedural-rule-pack.v1`
- `lukart.cirp.remedy-option.v1`
- `lukart.cirp.evidence-requirement.v1`
- `lukart.cirp.strategy-option.v1`
- `lukart.cirp.strategy-decision.v1`
- `lukart.cirp.filing-topology-decision.v1`
- `lukart.cirp.filing-plan.v1`
- `lukart.cirp.preflight-check.v1`
- `lukart.cirp.preflight-result.v1`

All contracts have deterministic `canonical_dict()` representations and content digests. CIRP reuses existing P3 canonical JSON and Case Ledger case identity rather than defining competing canonicalization or case-identity schemes.

## Core contract roles

### `CIRPRunIdentity`

Binds the analysis to the exact case, evidence/event inputs, rule-pack set, configuration, policy/runtime/model identity and timezone-aware evaluation time. A run without material evidence/event input is invalid.

### `DocumentAssessment`

Describes what the source document says and how it is classified. A statement contained in a document is not automatically a fact about the external world. `VERIFIED` classification requires evidence and cannot use `UNKNOWN` document kind.

### `ProceduralAssessment`

Keeps procedural stage and the authority roles explicit. `review_authority`, `filing_authority` and `filing_via` are separate fields by design and must not be collapsed by inference.

### `ServiceAssessment`

Separates verified service from user-reported/document-stated service. Conflicting dates cannot be silently resolved: `CONFLICTING` requires at least two distinct candidates and no settled service date.

### `DeadlineAssessment`

Represents the evidence and rule identity behind a deadline. `VERIFIED` requires a trigger date/evidence, rule pack/rule/version, effective-law date, legal-source reference and calculated legal deadline. `MISSING_INPUT`, `UNKNOWN_RULE` and `CONFLICTING_EVIDENCE` require explicit blocking questions.

### `LegalSourceRef` / `ProceduralRulePack`

Legal source references are version/effective-time aware. A verified source requires a content digest. A rule pack cryptographically binds its source set via `source_set_digest`.

CIRP-02 adds an executable deadline rule whose `pack_token` has the form `rule_id@version#semantic_digest`. An ACTIVE deadline runtime requires the rule pack's `deadline_rules` set to match the exact executable tokens. Calendar semantics are also content-digested and bound into the executable rule. Changing duration, start rule, roll convention, calendar identity, holiday set or legal-source bindings therefore changes the semantic digest and cannot silently reuse the previous rule-pack token.

### `RemedyOption` / `EvidenceRequirement`

A `VERIFIED_AVAILABLE` remedy requires explicit rule identity and cannot carry unresolved blockers. Evidence requirements distinguish deadline/admissibility/merits-critical gaps from supporting/optional material.

### `StrategyOption` / `StrategyDecision`

Strategy uses semantic dimensions instead of false numerical precision. A `RECOMMENDED` decision requires selected strategy identity, decisive evidence and decisive rules. Every materially rejected strategy requires a recorded reason. Non-recommended outcomes may explicitly be `NEEDS_EVIDENCE`, `DECISION_REQUIRED`, `NO_SAFE_OPTION` or `ABSTAIN`.

### `FilingTopologyDecision`

One-filing is an optimization, not a rule. `SINGLE_FILING_SAFE` requires exactly one filing and no blockers. `MULTIPLE_FILINGS_REQUIRED` requires at least two filings. Uncertain consolidation must remain explicit.

### `FilingPlan` / `PreflightResult`

The semantic filing plan is separate from DOCX/PDF rendering. `FILING_READY` requires at least one preflight check, no blockers and every critical check at `PASS`.

## CIRP-02 executable deadline semantics

`core/cirp/deadline.py` is jurisdiction-neutral. Production law is data/configuration supplied through verified rule packs; the runtime does not contain hard-coded Polish-law deadlines.

The CIRP-02 deadline guard enforces the following boundary:

1. the `ProceduralRulePack` must be `ACTIVE`;
2. every executable deadline rule must be cryptographically bound by its exact `pack_token`;
3. the referenced calendar profile digest must match the calendar actually used at runtime;
4. rule and calendar legal-source identifiers must exist in the pack source set;
5. source jurisdiction must match the rule-pack jurisdiction;
6. the rule pack, executable rule and every relied-on legal source must be effective on the supplied `effective_law_date`;
7. a `VERIFIED` deadline requires verified legal sources plus a verified trigger date bound to evidence;
8. provisional trigger evidence may produce only a `PROVISIONAL` deadline;
9. missing or conflicting trigger state returns `MISSING_INPUT` or `CONFLICTING_EVIDENCE` rather than a guessed date;
10. unknown/mismatched rule identity returns `UNKNOWN_RULE` with an explicit blocker;
11. deadline expiry is evaluated using a timezone-aware evaluation time converted into the bound calendar timezone;
12. calendar-day and business-day duration semantics are explicit, including trigger inclusion/exclusion and optional roll to the next business day;
13. a safe internal deadline may be earlier than the legal deadline but may not be configured before the trigger date.

Calendar profiles explicitly bind timezone, weekend weekdays, holiday dates and any legal sources needed to justify those calendar semantics. Synthetic fixtures are used in public CI; real case data and private legal materials remain outside the repository.

## CIRP v1 invariants

1. **No Evidence → No Fact.** CIRP may represent document content or a claim, but evidence-free external assertions cannot be promoted to fact by CIRP narrative.
2. Missing verified trigger input cannot produce a `VERIFIED` deadline.
3. Missing current rule identity cannot be replaced by model memory for a `VERIFIED` result.
4. Rules/legal sources must be effective for the relevant time before later runtime stages may rely on them.
5. `safe_internal_deadline <= legal_deadline` whenever both exist.
6. Conflicting service evidence remains `CONFLICTING`; it cannot carry a settled service date.
7. `VERIFIED_AVAILABLE` remedy requires rule identity.
8. Filing route is modeled separately from review authority.
9. Critical evidence gaps must block dependent runtime decisions; CIRP-03 will enforce dependency propagation.
10. A `RECOMMENDED` strategy identifies decisive evidence and decisive rules.
11. Every materially rejected strategy has a rejection reason.
12. One-filing optimization must not degrade procedural safety; uncertain consolidation remains fail-closed.
13. Renderer output may present but must not mutate the semantic `FilingPlan`.
14. CIRP derived state never becomes a competing case-history SSOT.
15. Critical `UNKNOWN` / `UNRESOLVED` state must remain visible in later report rendering.
16. `FILING_READY` requires all critical preflight checks to pass and zero blockers.

CIRP-01 enforces invariant portions representable at the contract boundary. CIRP-02 additionally enforces the deadline-runtime portions of invariants 2, 3, 4 and 5. Invariants 1, 9, 12, 13, 14 and 15 also cross later component/runtime boundaries and require continued enforcement in later stages and integration tests.

## Deadline safety model

CIRP deliberately distinguishes:

- `legal_deadline` — deadline derived from a verified procedural rule and trigger;
- `safe_internal_deadline` — earlier operational target used to reduce last-moment execution risk.

The internal deadline can never be later than the legal deadline. CIRP-02 also rejects a configured internal buffer that would move the internal target before the trigger date. A missing service/trigger fact, unknown rule, ineffective rule/source or unverified source produces an unresolved/provisional state instead of an estimated verified deadline.

## One-filing preference

CIRP prefers the smallest procedurally safe filing set. It may combine remedies only when later runtime validation establishes compatible procedure, route, authority and timing. Otherwise it must select multiple filings or `CONSOLIDATION_UNCERTAIN`.

## Replay and identity

CIRP contracts are content-digestible and reuse deterministic canonical JSON. The run identity records the relevant evidence/event and rule-pack identities. CIRP-02 additionally binds executable deadline semantics and calendar semantics through content digests. Model-assisted reasoning may later be environment-bound; CIRP must never claim byte-identical replay from incomplete identity.

## Non-claims

CIRP-02 does not claim:

- correctness of any Polish-law deadline or remedy unless a separately verified jurisdiction rule pack and current legal sources are supplied;
- current production legal-source coverage;
- legal certification or independent review;
- autonomous filing or external delivery;
- real-case validation;
- that a generated document alone completes a case action.

Those claims require later implementation and appropriate evidence.
