# New case checklist — CIRP entry (LUKART ROS)

Use this checklist for every new real matter, every material new document and every event that can change procedural posture, deadline, remedy or filing strategy.

The default operator path is CIRP. Engineering case-workspace registration is secondary and must not replace the procedural assessment.

## 1. Privacy boundary

- [ ] Keep real documents, names, signatures, case numbers and sensitive evidence local-only.
- [ ] Public GitHub/CI may contain only approved code, documentation and synthetic/anonymized fixtures.
- [ ] Do not copy raw private evidence into repository documentation, tests, branch names or commit messages.

## 2. Intake identity

Before conclusions, establish or explicitly mark UNKNOWN:

- [ ] document / event identity and source evidence;
- [ ] document kind and subject;
- [ ] issuer and recipient;
- [ ] document date;
- [ ] case reference, if present;
- [ ] requested action / operative content;
- [ ] stated deadline, if the source states one;
- [ ] date and method of receipt/service;
- [ ] evidence of receipt/service (UPO, e-Doręczenie, envelope, acknowledgment or equivalent).

A statement in a document is evidence of what the document says; it is not automatically a verified fact about the underlying matter.

## 3. Mandatory CIRP assessment

Run the evidence-bound sequence:

`Document -> Procedural Posture -> Service/Receipt -> Deadline -> Remedy/Route -> Evidence Gaps -> Strategy -> Filing Topology -> Filing Plan -> Preflight -> Report -> Replay Verification`

Create or derive, as applicable:

- [ ] `DocumentAssessment`;
- [ ] `ProceduralAssessment`;
- [ ] `ServiceAssessment`;
- [ ] `DeadlineAssessment`;
- [ ] remedy assessment / `RemedyOption` set;
- [ ] `EvidenceRequirement` gap set;
- [ ] `StrategyDecision`;
- [ ] `FilingTopologyDecision`;
- [ ] `FilingPlan` set;
- [ ] `PreflightResult`;
- [ ] `CIRPReport`;
- [ ] CIRP replay manifest/comparison when replay verification is applicable.

## 4. Deadline guard — fail closed

Never turn an estimate or model memory into a verified legal deadline.

- [ ] verified trigger/service evidence exists, or status remains `MISSING_INPUT` / `PROVISIONAL`;
- [ ] current/effective rule identity and legal-source identity exist, or status remains `UNKNOWN_RULE`;
- [ ] conflicting service evidence remains `CONFLICTING_EVIDENCE`;
- [ ] `safe_internal_deadline <= legal_deadline` whenever both exist;
- [ ] expired/unknown deadlines remain explicit and cannot be hidden by narrative.

## 5. Evidence and strategy

- [ ] distinguish deadline-critical, admissibility-critical, merits-critical, procedural, supporting and optional evidence;
- [ ] identify which missing items block action now;
- [ ] compare materially different safe options only when they can change the decision;
- [ ] recommendation identifies decisive evidence and decisive rules;
- [ ] if more than one safe strategy remains, use `DECISION_REQUIRED` rather than inventing certainty;
- [ ] if evidence/rules are insufficient, use `NEEDS_EVIDENCE`, `UNKNOWN_RULE`, `CONFLICTING_EVIDENCE`, `NO_SAFE_OPTION` or `ABSTAIN` as appropriate.

## 6. Filing package

Prefer the smallest procedurally safe filing set, not automatically one document.

- [ ] one filing only when authority, route, timing and verified consolidation are compatible;
- [ ] otherwise preserve multiple filings or `CONSOLIDATION_UNCERTAIN`;
- [ ] semantic `FilingPlan` is complete before DOCX/PDF rendering;
- [ ] requests, grounds, evidence mapping, rule mapping, attachments, signature/copies and delivery route are explicit;
- [ ] every critical preflight check passes before `FILING_READY`;
- [ ] `READY_TO_FILE` does not mean sent, delivered or legally effective.

## 7. Ask the operator only when genuinely blocking

Do not stop for information that can be derived safely from available evidence. Ask for the smallest missing fact/evidence that blocks a truthful next step, for example:

- effective receipt/service date;
- missing source document or attachment;
- unresolved authority/jurisdiction/procedural route;
- evidence needed for admissibility or a material factual allegation;
- a genuine business/legal choice between equally safe strategies.

## 8. Optional engineering workspace onboarding

Only when the private matter is also being onboarded into the local LUKART runtime/workspace, use the existing case registry/workspace conventions. Do not create a second FactAgent/LawAgent, a parallel case truth store or case-specific export/pipeline architecture.

The authoritative CIRP contract is `docs/CASE_INTAKE_RESPONSE_PROTOCOL_V1.md`. The canonical engineering standard remains `docs/WORKING_PRINCIPLES.md`.
