# LUKART ROS — ChatGPT Project Setup

Updated: 2026-09-13

This file explains how to mirror repository operating principles into ChatGPT Project Instructions and Memory. Repository files are the durable canonical copies; account-level ChatGPT settings must be edited manually by the account user in the ChatGPT UI.

## Repository sources

Canonical engineering/trust standard:

`docs/WORKING_PRINCIPLES.md`

Single living operator standard for private real-case work:

`docs/PRIVATE_CASE_OPERATING_STANDARD.md`

CIRP Product protocol for a new real matter, material new document or procedural event:

`docs/CASE_INTAKE_RESPONSE_PROTOCOL_V1.md`

Short operator checklist for a new matter:

`docs/NEW_CASE_CHECKLIST.md`

Paste-ready ChatGPT Project Instructions mirror for the private CASE project:

`docs/CHATGPT_PROJECT_INSTRUCTIONS_PRIVATE_CASE.md`

Short Memory/new-chat bootstrap:

`docs/CHATGPT_MEMORY_SUMMARY.md`

Repository agent bootstrap:

`AGENTS.md`

`docs/WORKING_PRINCIPLES.md` remains the sole full living engineering/trust standard. `docs/PRIVATE_CASE_OPERATING_STANDARD.md` is the operator orchestration authority for private CASE handling; it composes rather than replaces CIRP and canonical architecture contracts. Canonical Case Ledger remains the sole authoritative writable SSOT for case history.

## Strict engineering stage sequence — mandatory mirror

ChatGPT Project Instructions and Memory should preserve this invariant for repository/engineering work:

`Current open stage + PR + exact candidate SHA -> inspect exact-SHA CI -> if FAIL/incomplete/stale: repair inside same stage -> fresh SHA -> full required gates on fresh SHA -> merge exact validated PR head -> post-merge validation on resulting main -> close stage -> only then next stage`

Do not:
- skip an open roadmap stage;
- work ahead on a later stage before current-stage closure;
- declare PASS/DONE before complete exact-SHA and post-merge validation;
- reuse stale PASS from an older candidate after a repair;
- combine results from different SHAs;
- rewrite historically closed stages during normal roadmap progression.

A newly evidenced regression, incident, security issue or dependency becomes a new repair stage rather than retroactively rewriting historical closure.

## Private real CASE — mandatory operator mirror

For every new private matter and every continuation of an existing private matter, ChatGPT should use `docs/PRIVATE_CASE_OPERATING_STANDARD.md` by default. The user should not have to restate the full method.

### NEW CASE

Minimal trigger:

`LUKART ROS — NEW CASE: <name>. CIRP REAL CASE RUN.`

Expected path:

`Scope -> Decision Need -> Inventory -> Evidence Ceiling -> Epistemic Model -> Timeline -> Contradictions -> Deadlines -> Standing/Authority -> Procedural Map -> Current-Law Research -> Remedy/Strategy -> Filing Topology -> Draft A -> Red Team -> Hardcore Preflight -> SEND READY -> Render -> Send/File when authorized -> Receipt -> Response Delta -> Replay -> Next Action/Closure`.

### CONTINUE CASE

Minimal trigger:

`LUKART ROS — CASE <name> — CONTINUE.`

Do not restart analysis from zero. Reconstruct the current authorized CASE state and perform delta analysis for new evidence/documents/events.

### Required behavior

- `No Evidence -> No Fact`;
- distinguish `FACT / CLAIM / HYPOTHESIS / INTERPRETATION / UNKNOWN / UNRESOLVED / ABSTAIN`;
- preserve contradictions and uncertainty;
- never infer a verified legal deadline from model memory or an estimated receipt date;
- verify current/effective legal authorities for material deadline/remedy/procedural claims;
- verify standing/representation, recipient, route and formal prerequisites before filing;
- use Problem First and Decision Need First; a request to “write a letter” does not bypass upstream gates;
- use multi-track strategy when appropriate and the smallest procedurally safe filing set;
- final DOCX/PDF only after evidence/legal drafting, Red Team and Hardcore Preflight;
- keep `PREPARED != SENT != RECEIVED != EFFECTIVE` explicit;
- record receipts and response deltas;
- keep real-case documents, names, signatures, case numbers and sensitive evidence private/local.

CIRP remains the Product protocol; the private-case operator standard defines how a human/assistant runs a real matter end-to-end around that protocol without creating a competing truth authority.

## Long-Horizon Engineering / 10-Year Design Horizon

For major architectural decisions, ChatGPT should evaluate not only immediate implementation but also whether the design remains safely evolvable over an indicative 5–10 year horizon.

This does not mean predicting specific future technologies. It means designing so that changing models, providers, schemas, data formats, infrastructure, orchestration or scale does not require abandoning provenance, replayability, security, auditability or trusted data.

Preferred posture:
- versioned/open contracts;
- replaceable components and provider neutrality where justified;
- interoperability and explicit migrations;
- backward compatibility where practical;
- deterministic replay/provenance identity;
- rollback/recovery;
- bounded vendor/technology lock-in;
- no speculative abstraction without a concrete failure mode or measurable future-change cost.

Short rule: **future-resistant, not future-predictive**.

## ChatGPT Project Instructions — manual UI step

Repository automation cannot edit ChatGPT Project settings. The account user must perform this step manually.

Recommended source to paste:

`docs/CHATGPT_PROJECT_INSTRUCTIONS_PRIVATE_CASE.md`

Current general path:

1. Open the ChatGPT project used for private CASE work.
2. Open the project menu/settings.
3. Find **Project instructions**.
4. Paste the instruction block from `docs/CHATGPT_PROJECT_INSTRUCTIONS_PRIVATE_CASE.md` (without the Markdown explanation surrounding the block if desired).
5. Save.
6. Start a fresh test chat and send: `LUKART ROS — NEW CASE: TEST. CIRP REAL CASE RUN.` Confirm that the response starts with CASE state/evidence handling rather than immediately drafting a final filing.

If the Project Instructions field has a character limit, preserve in this order:
1. pointer to `docs/PRIVATE_CASE_OPERATING_STANDARD.md` and higher authorities;
2. case isolation/privacy;
3. NEW/CONTINUE behavior;
4. Evidence Ceiling + epistemic statuses;
5. deadline/current-law/standing safeguards;
6. Red Team + Hardcore Preflight before SEND READY;
7. lifecycle `PREPARED != SENT != RECEIVED != EFFECTIVE`;
8. minimal prompt triggers.

Do not solve the limit by deleting safety invariants. Remove examples/explanation first.

## ChatGPT Memory Summary — manual UI step

Memory is a convenience pointer, not the live standard.

1. Open **Settings -> Personalization**.
2. Open the Memory summary management surface available in the current UI.
3. Ask that the concise private-CASE rule from `docs/CHATGPT_MEMORY_SUMMARY.md` be incorporated: private CASE work defaults to `docs/PRIVATE_CASE_OPERATING_STANDARD.md`, NEW/CONTINUE prompts may be short, facts do not cross CASE boundaries, and final filings require preflight.
4. Review the synthesized summary and correct wording that weakens case isolation, evidence-first behavior, fail-closed uncertainty, deadline/current-law verification or preflight.

Project Instructions and repository documents are stronger authorities than synthesized Memory.

## Optional Project Memory mode

If strict separation of private CASE context from unrelated chats is desired, use the strongest project-scoped memory/isolation mode available in the current product. Choose deliberately because this changes which outside-chat context can be used.

## New-chat bootstrap

### Engineering chat

Include the relevant live repository checkpoint (main SHA, open stage/PR/candidate SHA, last closed stage, next approved stage) and follow `docs/WORKING_PRINCIPLES.md`.

### Private CASE chat

A long engineering checkpoint is not required. Use:

`LUKART ROS — NEW CASE: <name>. CIRP REAL CASE RUN.`

or

`LUKART ROS — CASE <name> — CONTINUE.`

The assistant must load/reconstruct the applicable CASE state and operator standard rather than forcing the user to paste the whole workflow.

## Amendment rule

Better ideas may be added later, but they must amend the correct single living authority rather than accumulate as competing lists.

1. identify the concrete risk/failure mode;
2. check whether an existing authority already covers it;
3. engineering/trust process change -> amend `docs/WORKING_PRINCIPLES.md`;
4. private CASE operator orchestration change -> amend `docs/PRIVATE_CASE_OPERATING_STANDARD.md`;
5. CIRP Product semantic change -> version/change CIRP under its Product governance;
6. update `docs/CHATGPT_PROJECT_INSTRUCTIONS_PRIVATE_CASE.md`, `docs/CHATGPT_MEMORY_SUMMARY.md`, checklists or AGENTS only as thin mirrors/pointers/enforcement surfaces;
7. preserve historical behavior through Git history rather than creating normal-use `V2`, `V3` competing standard files.
