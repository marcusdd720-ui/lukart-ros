# New case checklist — private CASE / CIRP entry

Use this checklist for every new real matter, every material new document and every event that can change procedural posture, deadline, remedy, evidence state or filing strategy.

Primary operator authority: `docs/PRIVATE_CASE_OPERATING_STANDARD.md`.  
CIRP Product contract: `docs/CASE_INTAKE_RESPONSE_PROTOCOL_V1.md`.  
Canonical engineering/trust authority: `docs/WORKING_PRINCIPLES.md`.

This checklist is a thin execution aid. It does not replace the living operator standard.

## 1. Privacy and scope

- [ ] Create/use a separate CASE boundary; do not import facts from another CASE without explicit authorization/reference.
- [ ] Keep real documents, names, signatures, case numbers and sensitive evidence private/local.
- [ ] Public GitHub/CI may contain only approved code, documentation and synthetic/anonymized fixtures.
- [ ] State the decision need/problem and desired outcome before strategy or drafting.

## 2. Intake identity / inventory

Before conclusions, establish or explicitly mark `UNKNOWN`:

- [ ] document/event identity and source evidence;
- [ ] issuer/source and recipient;
- [ ] document/event date;
- [ ] case reference, if present;
- [ ] requested action / operative content;
- [ ] stated deadline, if any;
- [ ] date and method of receipt/service;
- [ ] evidence of receipt/service;
- [ ] stable evidence/document IDs;
- [ ] source/provenance, original/copy status and SHA-256 where practical.

A statement in a document is evidence of what the document says; it is not automatically a verified fact about the underlying matter.

## 3. Evidence ceiling / epistemic state

- [ ] classify material propositions as `FACT`, `CLAIM`, `HYPOTHESIS`, `INTERPRETATION`, `UNKNOWN` or `UNRESOLVED`;
- [ ] identify contradictions and competing accounts;
- [ ] record what the current material cannot establish;
- [ ] do not promote a claim to fact merely because it appears in an official/private document;
- [ ] use `ABSTAIN` when safe conclusion is not supportable.

## 4. Mandatory CIRP/procedural assessment

Run the evidence-bound sequence appropriate to the matter:

`Document/Event -> Procedural Posture -> Service/Receipt -> Deadline -> Remedy/Route -> Evidence Gaps -> Strategy -> Filing Topology -> Filing Plan -> Preflight -> Report -> Replay Verification`.

In operator terms this sits inside the larger private-CASE lifecycle in `docs/PRIVATE_CASE_OPERATING_STANDARD.md`.

## 5. Deadline / current-law guard

Never turn an estimate or model memory into a verified legal deadline.

- [ ] verified trigger/service evidence exists or status remains provisional/missing;
- [ ] current/effective rule identity and authoritative legal source are verified;
- [ ] conflicting service evidence remains explicit;
- [ ] safe internal deadline does not exceed verified legal deadline;
- [ ] expired/unknown deadlines remain visible;
- [ ] material case law is correctly characterized and not overstated.

## 6. Standing / authority / route

- [ ] identify the party/pokrzywdzony/applicant and represented interest;
- [ ] identify who may sign/act and on what authority;
- [ ] distinguish competent/review authority, filing authority and filing route;
- [ ] identify formal prerequisites, required copies and signature requirements;
- [ ] unresolved standing/representation that affects validity blocks final filing.

## 7. Evidence, remedy and strategy

- [ ] distinguish deadline-critical, admissibility-critical, merits-critical, procedural, supporting and optional evidence;
- [ ] identify which missing items block action now;
- [ ] compare materially different safe options only when they can change the decision;
- [ ] use multi-track strategy when appropriate;
- [ ] recommendation identifies decisive evidence and decisive rules;
- [ ] preserve `DECISION_REQUIRED`, `NEEDS_EVIDENCE`, `NO_SAFE_OPTION` or `ABSTAIN` instead of manufacturing certainty;
- [ ] prefer the smallest procedurally safe filing set; one filing is an optimization, not a rule.

## 8. Draft / Red Team / Hardcore Preflight

Do not render final DOCX/PDF before preflight.

- [ ] Pass A legal/evidence draft exists;
- [ ] Red Team checked unsupported facts, stale/wrong law, overstated precedent, standing, recipient/route, attachments, privacy and remedy competence;
- [ ] fact/evidence mapping is complete for material assertions;
- [ ] rule/legal-source mapping is complete for material legal requests;
- [ ] required attachments/signatures/copies are present;
- [ ] no critical `UNKNOWN/UNRESOLVED` is hidden;
- [ ] all critical preflight checks PASS before `FILING_READY` / `SEND_READY`.

## 9. SEND READY / execution lifecycle

- [ ] final artifact is professionally formatted and contains no internal/debug commentary or unused placeholders;
- [ ] current date, sender/recipient, signature and attachments are correct;
- [ ] state is explicit: `DRAFT -> PREFLIGHTED -> SEND_READY -> APPROVED -> SENT/FILED -> RECEIVED/DELIVERED -> RESPONDED -> ASSESSED -> CLOSED/ARCHIVED`;
- [ ] remember: `PREPARED != SENT != RECEIVED != EFFECTIVE`;
- [ ] receipt/proof of submission is stored;
- [ ] response/follow-up deadline is recorded;
- [ ] new response/event triggers delta analysis rather than silent rewrite.

## 10. Ask the operator only when genuinely blocking

Do not stop for information that can be derived safely from authorized evidence. Ask only for the smallest missing item that blocks a truthful next step, e.g.:

- identity/standing/representation;
- receipt/service evidence;
- missing source document/attachment;
- transaction evidence;
- unresolved authority/route;
- a real decision between materially different safe strategies.

## 11. Minimal user trigger

New matter:

`LUKART ROS — NEW CASE: <name>. CIRP REAL CASE RUN.`

Existing matter:

`LUKART ROS — CASE <name> — CONTINUE.`

The user should not need to paste the full operating standard in every chat.
