# LUKART ROS — Private Case Operating Standard

Version: **1.0.0**  
Status: **ACTIVE OPERATOR STANDARD**  
Effective: **2026-09-13**  
Scope: **all private real-world CASE work**

## 1. Authority and role

This document is the single living **operator standard for private CASE work**. It composes existing LUKART ROS authorities; it does not replace the canonical engineering standard and does not create a second case-history truth store.

Authority order:

1. `docs/WORKING_PRINCIPLES.md` — sole canonical living engineering/trust standard;
2. Canonical Case Ledger — sole authoritative writable SSOT for case history;
3. `docs/CASE_INTAKE_RESPONSE_PROTOCOL_V1.md` — CIRP Product semantics;
4. canonical architecture contracts under `canon/`, especially Case, Problem, Evidence, Decision/Strategy and Document/Renderer contracts;
5. this file — mandatory operator orchestration for private real-case handling;
6. non-authoritative mirrors/checklists/templates used only to make execution easier.

If this file conflicts with a higher authority, fail closed and resolve the conflict in the higher canonical source instead of creating another competing rule list.

## 2. Privacy boundary

Real-case documents, names, signatures, addresses, phone numbers, case numbers, medical/financial records and other sensitive evidence are **local/private only**.

Public GitHub, CI, branch names, commit messages, documentation and fixtures MUST contain only approved code, generic rules, synthetic examples or anonymized material.

A private CASE is a cognitive and privacy boundary. Facts, documents and conclusions from another CASE MUST NOT enter the current CASE unless an explicit authorized cross-case reference/bridge exists.

## 3. Entry modes

### 3.1 NEW CASE

A new private matter begins in a new chat/workspace and receives a stable CASE identity. The operator does not need to repeat the full standard.

Minimal trigger:

`LUKART ROS — NEW CASE: <name>. CIRP REAL CASE RUN. Documents attached.`

Equivalent shorter wording is acceptable when intent is clear.

### 3.2 CONTINUE CASE

An existing matter is continued from its current state, not re-analysed from zero.

Minimal trigger:

`LUKART ROS — CASE <name> — CONTINUE.`

Before new conclusions, reconstruct the current CASE state from authorized evidence and prior case artifacts, then perform delta analysis for the new material/event.

## 4. Mandatory lifecycle

Every private CASE follows this sequence unless a step is genuinely not applicable and that non-applicability is explicit:

`Scope → Decision Need → Inventory → Evidence Ceiling → Epistemic Model → Timeline → Contradictions → Deadlines → Standing/Authority → Procedural Map → Current-Law Research → Remedy/Strategy → Filing Topology → Draft A → Red Team → Hardcore Preflight → Draft B / SEND READY → Render → Human/Operator Approval where required → Send/File → Receipt → Response Delta → Replay → Next Action / Closure`

Document generation is downstream. A request such as “write a letter” does not authorize skipping upstream evidence/procedure gates.

## 5. Gate model

### G0 — Scope / decision need

PASS requires:
- bounded CASE scope;
- explicit problem/decision need;
- desired outcome and minimum protective outcome;
- known stakeholder/represented interest;
- privacy boundary.

If decision need is materially ambiguous: `DECISION_REQUIRED` or `OPEN_QUESTION`.

### G1 — Evidence inventory

Before conclusions, inventory all available material. Each evidence item SHOULD have:
- stable `evidence_id` / `document_id`;
- original filename or source identity;
- source/provenance;
- date acquired;
- source date if known;
- original/copy status;
- integrity digest (SHA-256) where practical;
- sensitivity/privacy class;
- relevance;
- facts/claims it supports;
- contradictions or limitations.

Originals remain immutable. Redacted/cropped/annotated copies are separate derived artifacts.

### G2 — Evidence ceiling / epistemic model

Before strategy or drafting, state what the current material can and cannot establish.

Use explicit categories:
- `FACT` — adequately supported by admitted evidence;
- `CLAIM` — assertion by a party/source, not independently established;
- `HYPOTHESIS` — testable explanatory proposition;
- `INTERPRETATION` — analytical reading of facts/evidence;
- `UNKNOWN` — required information absent;
- `UNRESOLVED` — conflict or open issue remains;
- `ABSTAIN` — safe conclusion cannot be produced.

**No Evidence → No Fact.** A document proves that the document contains a statement; it does not automatically prove the underlying statement is true.

### G3 — Timeline / contradiction / deadline

Build an evidence-bound chronology. Preserve uncertainty in dates.

For every possible deadline distinguish:
- event/document date;
- receipt/service date;
- evidence supporting receipt/service;
- legal trigger;
- rule/source identity;
- computed deadline;
- safe internal deadline;
- status (`VERIFIED`, `PROVISIONAL`, `UNKNOWN_RULE`, `MISSING_INPUT`, `CONFLICTING_EVIDENCE`, etc.).

Never convert model memory, an estimate or an unverified receipt date into a verified legal deadline.

### G4 — Standing / authority / procedure

Before filing determine:
- who is the party/pokrzywdzony/applicant/creditor/debtor/etc.;
- who may sign/act and on what authority;
- competent authority;
- review authority vs filing authority vs filing route;
- current procedural posture;
- admissibility/formal prerequisites;
- whether multiple tracks are independent or coupled.

Unknown standing/representation that affects validity is a hard preflight blocker.

### G5 — Current law / authority research

For material legal/procedural assertions:
- use current/effective authoritative sources;
- bind rule/source identity and effective date where material;
- distinguish statute/regulation from case law, guidance and commentary;
- verify quotations and holdings;
- never state that an authority held more than it actually held;
- record contrary or limiting authority when material.

Model memory alone is not sufficient for a verified deadline, remedy or current legal rule.

### G6 — Remedy / strategy / filing topology

Problem first, document second.

Identify materially different safe options only when they could change the decision. For each meaningful option consider:
- legal/procedural availability;
- decisive evidence and missing evidence;
- deadline/timing risk;
- burden/standard if known;
- authority and route;
- financial/execution risk;
- privacy/reputational risk;
- reversibility;
- dependencies on other tracks.

Use multi-track strategy when appropriate (e.g. criminal, civil, administrative, financial, evidentiary). One filing is an optimization, not a rule.

Statuses include `RECOMMENDED`, `DECISION_REQUIRED`, `NEEDS_EVIDENCE`, `NO_SAFE_OPTION`, `ABSTAIN`.

### G7 — Draft / Red Team / Hardcore Preflight

Final professional documents are produced in two passes.

**Pass A — Legal/Evidence Draft**
- operative request;
- factual propositions with evidence status;
- legal grounds;
- case law/authority;
- evidence requests;
- attachments;
- route/signature requirements.

**Red Team** challenges the draft from the perspective of the recipient/opponent:
- unsupported factual assertion;
- wrong or stale law;
- overstatement of precedent;
- missing standing/authority;
- wrong recipient/route;
- missing attachment/signature/copy;
- premature legal conclusion;
- contradiction hidden by wording;
- avoidable disclosure or privacy leak;
- remedy outside recipient competence;
- unnecessary aggression that reduces credibility.

**Hardcore Preflight** must check at least:
- identity of filer/represented person;
- standing/authority;
- recipient and filing route;
- deadline status;
- explicit requests;
- factual/evidence mapping;
- legal/rule mapping;
- required attachments;
- signature/copies;
- contradictions/open questions;
- topology/consolidation safety;
- privacy/minimization;
- current date and contact details;
- no critical `UNKNOWN/UNRESOLVED` hidden from the filing.

Critical FAIL → `NOT_READY`. Critical UNKNOWN → `ABSTAIN` / `REVIEW_REQUIRED`. Only all-critical-PASS may become `FILING_READY` / `SEND READY`.

### G8 — Execution / receipt / replay

Artifact state is explicit:

`DRAFT → PREFLIGHTED → SEND_READY → APPROVED → SENT/FILED → RECEIVED/DELIVERED → RESPONDED → ASSESSED → CLOSED/ARCHIVED`

`PREPARED != SENT != RECEIVED != EFFECTIVE`.

For every external action record a receipt:
- exact document/version/digest;
- date/time;
- sender;
- recipient;
- channel/route;
- proof of submission;
- proof of receipt/delivery where available;
- response deadline/follow-up date;
- response and resulting CASE delta.

A response or material event starts a delta run; historical analyses are preserved, not silently rewritten.

## 6. Document standard — SEND READY

A final filing/letter must be a professional artifact, not a chat draft.

Unless the destination imposes another format, the renderer SHOULD produce:
- A4;
- readable professional typeface;
- stable paragraph hierarchy;
- adequate left margin for physical filing/binder where relevant;
- pagination;
- correct sender/recipient blocks;
- current date;
- signature block;
- ordered attachments;
- no internal CASE commentary, debug text, speculative labels or unused placeholders;
- DOCX and/or PDF when requested/appropriate.

Templates define presentation, not truth. The renderer MUST NOT invent facts, fix contradictions or change strategy. If rendering discovers a missing material input, return upstream to the appropriate gate.

## 7. Evidence-to-assertion traceability

Material factual assertions in a professional document SHOULD be traceable to admitted evidence or explicitly marked as a party’s assertion.

Preferred pattern for complex cases:

`Evidence E-xxx → Fact/Claim F/C-xxx → Legal/Procedural issue P-xxx → Remedy/Strategy R/S-xxx → Filing request Q-xxx`

Where practical, maintain hashes and artifact versions sufficient to reproduce why a particular filing version was generated.

## 8. Complexity scaling

The standard does not become weaker for simple cases or bureaucratically heavier for no reason.

- Simple matter: compressed execution, same invariants.
- Material legal/financial matter: full gates.
- High-risk/multi-party/multi-forum matter: full gates + adversarial review + explicit dependency graph + stronger provenance/replay.

Best-Justified Solution != Most Complex Solution.

## 9. Questions to the operator/user

Do not ask the user to restate information already present in the CASE or retrievable from authorized sources.

Ask only for the smallest genuinely blocking input, such as:
- identity/standing/representation;
- missing source document;
- receipt/service evidence;
- required signature/authority;
- missing transaction evidence;
- a true decision between materially different safe strategies.

Non-blocking gaps remain explicit `UNKNOWN/UNRESOLVED` and work continues to the evidence ceiling.

## 10. Real-case validation honesty

Do not claim:
- real-case validation without actual private-case evidence having been processed;
- delivery without a receipt;
- legal effect merely because a document was generated;
- independent/human/security/professional review unless it actually occurred;
- exact replay without complete bound identities/artifacts.

Synthetic CI validates engineering behavior, not the truth or legal correctness of a real matter.

## 11. Case closure / reopening

A CASE may close when:
- active goals are resolved, withdrawn, transferred or accepted as unresolved;
- required actions and follow-ups are completed;
- remaining unknowns are explicitly non-blocking or moved to monitoring;
- closure reason, authority and final state are recorded.

Closure freezes an auditable snapshot; it does not erase history. New material may reopen the CASE as a new state/run while preserving prior closure evidence.

## 12. Versioning and amendment

This is a living operator standard. Do not create `V2`, `V3` files for normal improvements.

For a material improvement:
1. identify a concrete failure mode or quality gap;
2. check whether an existing rule already covers it;
3. refine the existing rule where possible;
4. increment the semantic version in this file for material semantic change;
5. update non-authoritative mirrors only when necessary;
6. preserve history through Git commits/PRs rather than competing documents.

A CASE SHOULD record the operating-standard version and repository commit used for significant runs/filings when practical.

## 13. Default operator behavior

Within the ChatGPT project for private CASE work, this standard is the default. The user should not need to paste a long prompt for every matter.

For every NEW CASE or CONTINUE request:
- read/obey this standard and its higher authorities;
- keep CASE data isolated;
- continue end-to-end to the current evidence/authority ceiling;
- do not render final filings before G7 preflight;
- do not stop at a repairable drafting/research problem;
- report blockers precisely rather than manufacture certainty.
