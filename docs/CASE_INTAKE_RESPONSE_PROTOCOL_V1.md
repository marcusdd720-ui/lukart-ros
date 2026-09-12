# LUKART ROS — Case Intake & Response Protocol (CIRP) v1.0

Status: **CLOSED / ENGINEERING PASS**

CIRP is the fail-closed Product protocol that converts a new case document or
material case event into an evidence-bound procedural assessment and a
best-justified action package. CIRP is not a legal-source database, not an
autonomous filing authority and not a second source of truth.

## Authority and privacy

- `docs/WORKING_PRINCIPLES.md` remains the single canonical living engineering
  standard.
- Canonical Case Ledger remains the sole authoritative writable SSOT for case
  history.
- CIRP outputs are typed, versioned derived artifacts bound to exact inputs,
  evidence and rule identities.
- Real-case documents, names, signatures, case numbers and sensitive evidence
  remain local-only. Public GitHub and CI contain only code, documentation and
  synthetic/anonymized fixtures.
- Missing evidence, unknown rules, conflicting service data and unresolved
  procedural state fail closed.

## Product objective

For every new document or material event CIRP is designed to establish, or
explicitly abstain from establishing:

`Document → Procedural Posture → Service/Receipt → Deadline → Remedy/Route → Evidence Gaps → Strategy → Filing Topology → Filing Plan → Preflight → Report → Replay Verification`

A new material document or changed critical input creates a new CIRP run;
historical analyses are not silently rewritten.

## Runtime stages

1. `CIRP-01` — Contracts & Invariants — implemented.
2. `CIRP-02` — Procedural Rule Pack + Deadline Guard — implemented.
3. `CIRP-03` — Remedy + Evidence Gap — implemented.
4. `CIRP-04` — Strategy + Filing Topology — implemented.
5. `CIRP-05` — Filing Plan + Hardcore Preflight + Report — implemented.
6. `CIRP-06` — Adversarial / Replay / Integration — implemented and
   post-merge validated.

## Stage boundaries

### CIRP-01 — contracts and invariants

CIRP-01 defines typed contracts, canonical serialization and fail-closed boundary
invariants. CIRP reuses existing P3 canonical JSON and Case Ledger case identity
instead of creating competing identity schemes.

### CIRP-02 — deadline semantics

`core/cirp/deadline.py` is jurisdiction-neutral. Production law is supplied as
verified rule-pack data rather than hard-coded runtime knowledge.

A verified deadline requires:

- an ACTIVE rule pack;
- an executable deadline rule cryptographically bound to that rule pack;
- effective and verified legal-source identity;
- a verified trigger bound to evidence;
- matching calendar semantics and timezone identity;
- an effective-law date inside the rule/source validity window.

Missing/conflicting triggers, unknown rules or ineffective/unverified sources do
not become estimated verified deadlines. `safe_internal_deadline` may precede,
but never exceed, `legal_deadline`.

### CIRP-03 — remedy and evidence-gap semantics

`core/cirp/remedy.py` evaluates jurisdiction-neutral executable remedy semantics
bound to the active rule pack.

A `VERIFIED_AVAILABLE` remedy requires verified/effective rule and source
identity, verified applicability, satisfied deadline dependency where declared,
all required evidence present and zero blockers. Critical missing/conflicting
or stale evidence propagates uncertainty downstream instead of being hidden.

### CIRP-04 — strategy and filing topology

`core/cirp/strategy.py` performs fail-closed strategy selection without false
numeric precision.

A strategy can be `RECOMMENDED` only when exactly one candidate remains fully
verified and deadline-safe and explicit decisive evidence and rule references
are supplied. More than one safe candidate yields `DECISION_REQUIRED`; a sole
safe candidate without a decisive basis yields `ABSTAIN`.

One filing is an optimization, not a rule. Multiple remedies may share one
filing unit only when an explicit verified consolidation assessment covers the
exact remedy set and the remedies have compatible target authority, filing
authority and filing route. Otherwise CIRP returns multiple filing units or
`CONSOLIDATION_UNCERTAIN`.

### CIRP-05 — semantic filing plan

`core/cirp/filing.py` converts one `RECOMMENDED` strategy and a verified filing
topology into immutable `FilingPlan` contracts.

The planner requires:

1. a `RECOMMENDED` strategy whose identity is present in the supplied strategy
   set;
2. `SINGLE_FILING_SAFE` or `MULTIPLE_FILINGS_REQUIRED` topology;
3. an exact non-overlapping filing-spec partition of the selected remedy set;
4. every selected remedy at `VERIFIED_AVAILABLE`;
5. compatible target authority, filing authority and `filing_via` inside every
   filing unit;
6. filing rule references covering every selected remedy rule identity;
7. filing evidence references covering remedy evidence dependencies and present
   in the supplied available-evidence set;
8. a `VERIFIED` deadline assessment for every deadline-dependent remedy;
9. one compatible deadline identity per filing unit.

The semantic `FilingPlan` remains separate from DOCX/PDF rendering. A renderer
may present a plan but may not mutate its semantics.

### CIRP-05 — Hardcore Preflight

`core/cirp/preflight.py` evaluates execution readiness without repairing or
rewriting the filing plan.

The critical preflight boundary checks:

- filing identity;
- verified remedy availability;
- verified filing route;
- deadline identity and status;
- explicit requests and grounds;
- rule-basis completeness;
- evidence-basis completeness;
- remedy formal requirements;
- required attachments;
- signature readiness when required;
- copy readiness when required;
- verified filing topology;
- absence of critical `UNKNOWN/UNRESOLVED` state.

A non-applicable requirement is represented as a successful critical condition,
not as a hidden missing check. `FILING_READY` requires every critical check to
be `PASS` and zero blockers. A critical `UNKNOWN` produces `ABSTAIN`; a critical
`FAIL` produces `NOT_READY`.

### CIRP-05 — report projection

`core/cirp/report.py` defines the render-neutral schema
`lukart.cirp.report.v1`.

The report is a deterministic projection of already-derived CIRP artifacts. It
contains case/run identity, document/procedural summaries, deadlines, remedies,
evidence gaps, strategy state, filing topology, filing identities, preflight
states, open questions and critical unknowns.

The report does not silently repair or suppress upstream uncertainty:

- evidence gaps produce `NEEDS_EVIDENCE`;
- multiple safe strategies remain `DECISION_REQUIRED`;
- no safe strategy remains `NO_SAFE_OPTION`;
- critical unknowns produce `ABSTAIN`;
- non-ready preflight produces `NOT_READY`;
- only a complete filing set whose preflights are all `FILING_READY` can produce
  `READY_TO_FILE`.

A `READY_TO_FILE` report carrying a critical unknown is contract-invalid.

### CIRP-06 — adversarial replay and integration

`core/cirp/replay.py` closes the deterministic replay-verification boundary. A
replay manifest is a verification artifact only. It never becomes a second case
ledger and never stores raw evidence, source documents or case narrative.

The CIRP-06 replay boundary enforces:

1. the replay manifest is bound to the exact `CIRPRunIdentity.digest()`;
2. every semantic artifact reference has an explicit logical identity, schema
   identity and SHA-256 content digest;
3. artifact identities are unique and are canonically ordered before manifest
   hashing, so caller ordering cannot change replay identity;
4. every manifest identifies exactly one final `lukart.cirp.report.v1` artifact;
5. exact artifact-set mismatch is `INCOMPLETE`, never guessed as identical;
6. changed run identity, report identity, artifact schema or artifact digest is
   `DIFFERENT`;
7. `IDENTICAL` is permitted only when run identity, report identity, exact
   artifact set and every artifact digest match and manifest digests are equal;
8. CIRP v1 does not claim `CROSS_VERSION_COMPARABLE`; a future version requires
   an explicit compatibility contract before that relation can be emitted;
9. replay verification compares derived semantics and never promotes a replayed
   conclusion into an authoritative case fact.

The CIRP-06 adversarial integration suite verifies the executable chain from
strategy/topology through filing plan, Hardcore Preflight, report projection and
replay manifest. It checks exact deterministic replay, canonical artifact order,
duplicate/missing/unexpected artifacts, artifact tampering, changed run identity,
route tampering, critical unknown propagation and multi-strategy ambiguity.

CIRP-06 therefore closes the v1 engineering loop without claiming that an
incomplete or model-assisted environment can provide byte-identical replay.

## CIRP v1 contract identities

CIRP v1 uses explicit stable schema identities, including:

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
- `lukart.cirp.report.v1`
- `lukart.cirp.replay-manifest.v1`
- `lukart.cirp.replay-comparison.v1`

Older schema identities remain historically interpretable when later versions are
introduced; semantic changes require an explicit version change rather than a
silent reinterpretation.

## CIRP v1 invariants

1. **No Evidence → No Fact.**
2. Missing verified trigger input cannot produce a `VERIFIED` deadline.
3. Missing current rule identity cannot be replaced by model memory for a
   verified result.
4. Rules and legal sources must be effective for the relevant time.
5. `safe_internal_deadline <= legal_deadline` whenever both exist.
6. Conflicting service evidence remains `CONFLICTING`.
7. `VERIFIED_AVAILABLE` remedy requires rule identity and zero blockers.
8. Filing route is modeled separately from review authority.
9. Critical evidence gaps block dependent runtime decisions.
10. A `RECOMMENDED` strategy identifies decisive evidence and decisive rules.
11. Every materially rejected strategy has a rejection reason.
12. One-filing optimization must not degrade procedural safety.
13. Renderer output may present but must not mutate the semantic `FilingPlan`.
14. CIRP derived state never becomes a competing case-history SSOT.
15. Critical `UNKNOWN/UNRESOLVED` state remains visible in later projections.
16. `FILING_READY` requires all critical preflight checks at `PASS` and zero
    blockers.
17. Replay identity may be `IDENTICAL` only for an exact complete deterministic
    semantic artifact set bound to the same run identity.
18. Missing replay material remains `INCOMPLETE`; replay verification never
    repairs or invents a missing artifact.

CIRP-06 makes replay invariants 17 and 18 executable and adversarially verifies
that earlier uncertainty and safety boundaries survive through the final report
and replay projection.

## One-filing preference

CIRP prefers the smallest procedurally safe filing set. It never combines
remedies merely for convenience. If procedure, authority, route, timing or
verified consolidation evidence do not support a single filing, CIRP preserves
multiple filings or abstains from consolidation.

## Replay and identity

CIRP contracts are content-digestible and use deterministic canonical JSON. A
run identity binds the relevant evidence/event and rule-pack identities. The
verified deterministic core is expected to reproduce the same semantic result
for the same material inputs.

CIRP-06 records only derived artifact identifiers, schema identities and content
digests in the replay manifest. Exact replay does not depend on persisting a
second copy of case facts. Missing or partial replay identity fails closed.
Model-assisted reasoning may be environment-bound; CIRP does not claim
byte-identical replay from incomplete runtime/model identity.

## Canonical engineering closure evidence

CIRP v1 closed through CIRP-06 implementation PR **#263**.

Implementation qualification:

- exact final CIRP-06 PR head: `ddad8f63723dbcdee78bf5f26f1884aa6c5c5c02`;
- exact-head workflow qualification: **43 SUCCESS** with no terminal failure on
  that candidate at merge decision;
- guarded merge resulting `main`:
  `452de5c2388e4e5e5754ffa35b8e13281461e494`;
- resulting-main workflow set: **41/41 SUCCESS**;
- resulting-main terminal negative states at closure evaluation:
  **0 failure, 0 queued, 0 in-progress, 0 cancelled, 0 timed-out**;
- dependent `MVROS v1 Release` guard run **#980** completed `SUCCESS` on the exact
  resulting merge SHA;
- the resulting merge commit was GitHub-verified and became the live `main`
  identity before this documentation follow-up was prepared.

This evidence closes the six-stage CIRP v1 **engineering** baseline only. It does
not manufacture legal, independent, security, regulatory or professional
certification and does not convert synthetic CI into real-case validation.

## Engineering closure and non-claims

The six CIRP v1 runtime stages form a complete **engineering baseline** because
the CIRP-06 implementation, adversarial tests, full regression, exact-SHA CI and
post-merge validation all passed. This is an engineering result, not legal or
independent certification.

The CIRP v1 baseline does **not** claim:

- correctness of any production jurisdiction deadline or remedy unless a
  separately verified current rule pack and legal sources are supplied;
- production coverage of Polish law or any other jurisdiction;
- legal certification, independent review or professional legal advice;
- autonomous filing, delivery or external submission;
- that `READY_TO_FILE` means a filing was actually sent or legally effective;
- that a rendered DOCX/PDF may change the semantic filing plan;
- real-case validation from public CI fixtures;
- cross-version exact/comparable replay without a separately defined and
  validated compatibility contract.

Public CIRP tests remain synthetic. Real-case evidence and operational case data
stay outside the public repository.
