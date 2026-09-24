# LUKART ROS — Deferred Ideas Backlog

Status: non-authoritative parking lot for deferred ideas.
Canonical engineering standard remains `docs/WORKING_PRINCIPLES.md`.
Live implementation state remains GitHub `main` / active roadmap.
Items in this file are `PLANNED/DEFERRED` only and MUST NOT be treated as implemented, validated, certified, or release-authorized.

## IDEA-001 — Privacy-First Provider-Agnostic Preservation Fabric

Status: `DEFERRED`
Recorded: `2026-09-09`
Revisit not before: `2027-03-09`
Owner decision: do not use Amazon/AWS for real LUKART case data at this stage.

### Problem / motivation

Preserve case/replay artifacts outside the primary machine and GitHub without making any cloud provider a Product/CCL authority and without exposing plaintext case content to that provider.

### Target concept

- provider-independent storage contract under the existing `ArtifactEscrowBackendV1` / replay boundaries;
- mandatory client-side encryption before any sensitive bytes leave the trusted device;
- provider receives opaque ciphertext only; encryption keys remain outside provider storage and outside GitHub;
- no PII/case names/sygnatures in provider object keys or ordinary metadata;
- separate plaintext artifact identity and ciphertext object identity;
- at least one encrypted offline recovery copy on independent media;
- at least one external immutable/WORM provider with independently verifiable retention/version evidence;
- real restore/replay drill required before any `PRESERVED` claim;
- provider-specific evidence adapters remain replaceable and must not become a competing SSOT;
- future multi-provider mode may add a second independent European provider when risk, scale, SLA/RPO/RTO, client obligations, or cost justify it;
- AWS implementation already present in the repository may remain as dormant compatibility code, but Amazon is excluded from active real-data storage unless a future explicit business decision reverses that policy.

### Candidate provider direction for future review

Re-evaluate available European/privacy-aligned providers and no-cost/low-cost options at review time. Backblaze B2 was explored as a technically interesting S3-compatible WORM/Object-Lock candidate, but no provider is approved by this backlog entry and no account/storage deployment is authorized by it.

### Acceptance criteria for future activation

Before promotion from `DEFERRED` to an active stage, require fresh evidence on provider terms, jurisdiction/data handling, pricing, Object Lock/WORM semantics, version identity, API-verifiable retention, credential model, export/recovery path, portability, provider lock-in, deletion/retention controls, and client-side encryption/key-recovery design.

The future implementation should follow the canonical pipeline and fail closed. No plaintext case data may be uploaded during evaluation; synthetic artifacts must be used until the full privacy/security path is validated.

## IDEA-002 — Verified Legal Authority Fabric

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

The current engineering/trust substrate is materially more mature than the jurisdiction-specific legal-authority layer. A cryptographically correct replay can still preserve a legally wrong conclusion if the underlying statute, judgment, procedural rule, effective date, or holding is incorrect or stale.

### Target concept

Introduce a dedicated Legal Authority Fabric for immutable, source-bound snapshots of authoritative legal material, separate from case evidence and separate from the Canonical Case Ledger authority.

A legal authority record should bind, where applicable:

- jurisdiction;
- authority/source type;
- official source/provider identity;
- source reference and exact source bytes or verifiable snapshot identity;
- content digest;
- schema/parser identity;
- publication/decision date;
- effective-from/effective-until interval where applicable;
- retrieval/evaluation time;
- language;
- verification status;
- supersession/limitation relations.

Legal authority must remain an immutable input or deterministic/versioned projection. It MUST NOT become a second writable source of case history.

### Acceptance criteria for future activation

- material legal assertions can be traced to exact source identities;
- source tampering and source substitution fail closed;
- stale/unknown legal authority remains explicit;
- offline verification is possible for critical authority snapshots where technically feasible;
- no agent can manufacture an authority record without a verified source boundary;
- changes to authority bytes, parser/schema, effective period, or provider identity change the dependent result identity.

## IDEA-003 — Jurisdiction-Neutral Legal Core

Status: `DEFERRED`
Recorded: `2026-09-19`
Initial production jurisdiction: Poland + applicable European Union law.
Planned expansion direction: Colombia after approximately six months, subject to fresh legal/source validation and an explicit activation decision.

### Problem / motivation

Avoid encoding Polish procedural assumptions directly into the shared Product core and avoid building a second system for Colombia or later jurisdictions.

### Target concept

Keep the reusable core jurisdiction-neutral:

- Canonical Case Ledger;
- Evidence and private evidence boundary;
- epistemic state;
- Evidence Trust Graph;
- agent runtime and capability routing;
- reasoning;
- replay/provenance;
- security/authorization;
- rendering;
- external-action execution;
- validation and recovery.

Represent jurisdiction-specific behavior through explicit packages/contracts such as:

```text
jurisdictions/
    pl/
    eu/
    co/
```

Each jurisdiction package owns its legal sources, procedural rule packs, terminology, provider adapters, validation corpus and document-domain rules without gaining authority over the shared core.

### Acceptance criteria for future activation

- shared Product core has no hidden Poland-only legal assumptions at cross-jurisdiction boundaries;
- jurisdiction identity is explicit in persistent and cross-boundary legal artifacts;
- a Colombia package can be added without forking CCL, ETG, agent runtime, replay or security architecture;
- cross-jurisdiction matters preserve separate source/rule identities rather than translating one jurisdiction's law into another.

## IDEA-004 — Poland + EU First Production Legal Pack

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

LUKART needs a bounded first production legal vertical rather than broad claims of supporting all Polish law.

### Target concept

Use Poland as the first national jurisdiction and European Union law as an integrated supranational authority layer where applicable.

Initial source families may include, after independent source/API verification:

- Polish statutes and regulations from authoritative publication sources;
- KRS/PRS company-register data as case evidence where relevant;
- CEIDG/business-register data where relevant;
- Supreme Court / NSA / WSA case law from authoritative sources;
- EUR-Lex and CURIA/CJEU materials;
- official ZUS procedural and decision sources.

This backlog entry does not approve any specific endpoint until the endpoint, terms, schema, freshness semantics and evidence boundary have been freshly verified.

### Acceptance criteria for future activation

- every enabled source has a documented authority/non-authority contract;
- provider identity, schema, freshness and failure semantics are explicit;
- no ordinary web search is silently treated as equivalent to an official primary source;
- EU and Polish authority relationships remain explicit rather than flattened into one undifferentiated corpus.

## IDEA-005 — Citation Verification Gate

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

A valid citation string is not proof that an authority exists, that the cited text is correct, or that the authority supports the proposition attributed to it.

### Target concept

Create a fail-closed Citation Verification Gate between legal-authority ingestion and material legal output.

The gate should verify, where applicable:

- citation/sygnatura/ECLI identity;
- court/authority identity;
- decision/publication date;
- official source binding;
- quoted text or referenced section;
- proposition-to-source support;
- effective-law timing;
- supersession/limitation state;
- source and parser identities.

Statuses should include explicit states such as `VERIFIED`, `MISMATCH`, `STALE`, `UNVERIFIABLE`, and `MISSING_SOURCE`.

### Acceptance criteria for future activation

- an invented or mismatched case citation cannot pass;
- a real judgment with a falsely attributed holding cannot pass;
- a source change invalidates dependent verification;
- material legal drafting can require citation verification before `FILING_READY`;
- missing verification never becomes implicit PASS.

## IDEA-006 — Polish Procedural Rule Packs

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

A single generic legal agent cannot safely represent materially different Polish procedures, deadlines, authorities and remedies.

### Target concept

Extend the existing CIRP/rule-pack model with bounded, versioned, source-bound Polish procedural packs. Initial candidates include:

- `PL.ZUS.BENEFIT_APPEAL.*`;
- `PL.ZUS.CONTRIBUTION_DECISION.*`;
- `PL.ZUS.CONTRIBUTION_REMISSION.*`;
- `PL.ZUS.INSTALLMENT.*`;
- `PL.ZUS.ENFORCEMENT.*`;
- `PL.ADMIN.WSA.*`;
- `PL.COMPANY.KRS.*`;
- later bounded civil/KPC packs where justified.

Each executable rule should bind exact legal-source identities, effective dates, rule semantics, calendar/time assumptions and test evidence.

### Acceptance criteria for future activation

- unknown or stale rule-pack identity fails closed;
- deadlines are calculated only from verified rule semantics and verified/provisional trigger evidence;
- a rule outside its effective period cannot silently execute;
- each rule pack has focused, adversarial and regression coverage;
- procedure-specific logic does not leak into the shared jurisdiction-neutral core.

## IDEA-007 — Replaceable External Provider Adapter Architecture

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

A monolithic `GovAPIsIntegrator` would combine unrelated trust boundaries, schemas, authentication models, privacy classes, freshness requirements and failure semantics.

### Target concept

Use small provider-specific adapters behind common contracts, for example:

```text
core/external_sources/
    contracts.py
    registry.py
    freshness.py
    transport.py
    pl/
        krs_open_api.py
        ceidg_adapter.py
        zus_public_source.py
    eu/
        eurlex_adapter.py
        curia_adapter.py
```

Each adapter should declare:

- provider identity/version;
- allowed hosts/endpoints;
- operation/read semantics;
- input/output schema;
- timeout/retry policy;
- freshness policy;
- authentication class;
- privacy classification;
- provenance/evidence output;
- explicit failure states.

No adapter may silently substitute ordinary public search for a failed authoritative provider.

### Acceptance criteria for future activation

- provider failure returns an explicit non-PASS state;
- redirects or host substitution outside allowlist fail closed;
- malformed/truncated/unknown-schema responses fail closed;
- retry is bounded and only permitted for explicitly safe operations;
- replacing a provider does not change the Product authority model.

## IDEA-008 — Colombia Jurisdiction Pack

Status: `DEFERRED`
Recorded: `2026-09-19`
Target direction: evaluate activation approximately six months after the Poland + EU vertical reaches a sufficiently stable production state.

### Problem / motivation

Prepare for expansion into Colombia without copying Polish legal semantics or creating a separate Product architecture.

### Target concept

Build Colombia as another jurisdiction package over the same shared core:

- Colombian official legal-authority sources;
- Colombian procedural rule packs;
- Colombian provider adapters;
- Spanish legal terminology and rendering rules;
- Colombian validation/Gold corpus built from approved synthetic/anonymized materials;
- explicit handling of cross-border PL/EU/CO matters.

Candidate public institutions and source families must be researched afresh at activation time. No Colombian provider/API is approved merely by being named in earlier design discussions.

### Acceptance criteria for future activation

- fresh review of Colombian authoritative sources, procedure, privacy/data-transfer constraints and provider/API terms;
- Colombia package uses the same CCL/evidence/epistemic/replay/security invariants as Poland;
- no Polish deadline, remedy, court, terminology or authority assumption is inherited without an explicit Colombian rule/source;
- Spanish output is domain-reviewed before any production claim;
- cross-border conflicts remain explicit `UNKNOWN/UNRESOLVED` until governed by verified rules.

## IDEA-009 — Legal Domain Maturity Program

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

Current strategic gap identified during the 15+ year review:

`Assurance maturity > Legal-domain maturity`.

The project already contains substantial engineering controls for identity, provenance, replay, privacy, authorization, recovery and fail-closed validation. The next material gains should increasingly measure and improve legal correctness rather than add assurance complexity without a demonstrated gap.

### Target concept

Create a measured legal-domain maturity program covering:

- source coverage;
- authority freshness;
- citation precision;
- proposition-to-authority support;
- procedural-rule correctness;
- deadline correctness;
- filing-route correctness;
- abstention quality;
- contradiction detection;
- regression against independently reviewed legal Gold sets.

The program must remain separate from engineering CI success. Engineering PASS does not certify legal correctness.

### Acceptance criteria for future activation

- explicit legal-domain metrics and error taxonomy;
- independently reviewed legal Gold/evaluation material where required;
- no self-certification by the same agent/model that generated the answer;
- changes to legal evaluators/corpora receive independent identity and versioning;
- measured improvement is required before promotion of new legal capabilities.

## IDEA-010 — Controlled Legal Agent Layer

Status: `DEFERRED`
Recorded: `2026-09-19`

### Problem / motivation

Adding many unconstrained specialist personas would enlarge the authority and hallucination surface without proving a need.

### Target concept

Prefer a small number of bounded agents that reuse the existing capability router, contracts and validation gates. Initial candidate roles:

1. `LegalAuthoritySynthesisAgent` — consumes verified authority snapshots and produces a typed synthesis artifact;
2. `CitationVerificationAgent` or deterministic gate — verifies source/citation/proposition binding without case-history write authority;
3. `FilingRedTeamAgent` — challenges a proposed filing for unsupported assertions, stale law, standing, deadline, recipient/route, remedy competence, missing attachments and privacy disclosure.

Agents should not:

- directly write Evidence Trust Graph state;
- bypass Canonical Case Ledger authority;
- treat model memory as verified law;
- hide `UNKNOWN/UNRESOLVED`;
- declare external actions completed without receipt evidence.

### Acceptance criteria for future activation

- capability routing is schema/certification based, not keyword-only routing;
- each agent has explicit inputs, outputs, permissions and budgets;
- no agent gains broad network/filesystem/write access solely for convenience;
- adversarial tests cover fabricated citations, stale authority, cross-case substitution and unsupported legal conclusions;
- agent output remains untrusted until normal Product validation accepts it.

## Review boundary — rendered-document labels

Owner decision recorded `2026-09-19`: the proposal to add visible labels such as `REVIEW_REQUIRED`, `REVIEWED`, `AI-generated`, `Wygenerowano przez LukArt RoS`, or visible provenance statements to final legal/client documents is rejected.

This backlog does not authorize such labels. Internal provenance, identity and audit evidence may exist within LUKART system metadata/evidence boundaries, but must not be rendered into final documents merely because an artifact was produced with LUKART assistance.

## IDEA-011 — LATAM Career OS — Colombia-First Reference Implementation

Status: `DEFERRED / DISCOVERY`
Recorded: `2026-09-24`
Owner direction: Colombia is the first flagship market, learning environment, validation ground and reference implementation. Brazil and later LATAM markets must inherit only architecture that has first been validated in Colombia.

### Problem / motivation

Do not build a narrow "CV writing service" or prematurely generalize across Latin America. Build a regional operating system for career positioning, applications and employability, with Colombia as the first production market, learning environment, validation ground and reference implementation. The system name and shared core must remain country-neutral so that Brazil and later markets can reuse the validated architecture through explicit market packs.

Previous CV-related Steps 1–19 remain useful as `Discovery v0`, but they are not the new canonical architecture.

### Target concept

Working concept:

`LATAM CAREER OS — Operating System for Professional Career Positioning, Applications & Employability`

The country-neutral LATAM Career OS core should support the full candidate journey, while Colombia remains Market Pack #1 and the first reference implementation:

- Career Diagnosis;
- Candidate Intake;
- Career Truth Record;
- target-role definition;
- professional value proposition;
- competency and achievement mapping;
- Hoja de Vida ES-CO;
- international Resume EN;
- Carta de Presentación / Cover Letter;
- LinkedIn Rebuild;
- Vacancy Intelligence and role matching;
- ATS-oriented document structure;
- Interview Preparation;
- Application Tracking;
- client revisions, delivery, reviews and referrals;
- future career updates and maintenance.

### Core operating doctrines

- **Truth Before Persuasion** — never invent experience, education, certifications, language levels, tools, achievements or metrics.
- **Evidence Before Achievement** — quantified claims require a known evidence status.
- **Target Before Writing** — define the target role before final document generation.
- **Career Story Before Layout** — content and positioning precede visual design.
- **ATS + Human** — optimize for parsability and recruiter readability.
- **Localization Before Translation** — English documents are independently written, not literal translations.
- **Measured Before Automated** — observe and measure the real process before automating it.
- **Human Control at Critical Gates** — material facts, metrics, positioning and final delivery remain human-controlled.
- **Colombia First** — new product and automation ideas are first validated in Colombia.
- **Expansion After Evidence** — Brazil and later markets receive validated architecture plus local market/language packs, not copy-pasted Colombian workflows.

### Candidate Truth Record

Create a canonical candidate fact layer independent from any specific CV or LinkedIn output.

Each material claim should support explicit provenance/status, for example:

- `CONFIRMED`;
- `UNCONFIRMED`;
- `ESTIMATED`;
- `DO_NOT_USE`.

The same canonical fact set should feed CV, Resume, LinkedIn, cover letters, vacancy matching and interview preparation to prevent contradictions between outputs.

### LinkedIn Rebuild Engine

Treat LinkedIn reconstruction as a first-class product, not merely an "About" rewrite.

Potential scope:

- profile-photo and banner recommendations;
- headline;
- location / industry;
- About;
- Experience;
- Skills;
- Featured;
- certifications;
- languages;
- keyword strategy;
- consistency with CV;
- target-role alignment;
- recruiter-search alignment.

A future "Before / After" scorecard may use explicit criteria, but must not rely on pseudo-scientific opaque scores.

### Vacancy Intelligence

Parse a target vacancy into:

- must-have requirements;
- nice-to-have requirements;
- responsibilities;
- tools;
- languages;
- seniority;
- keywords;
- industry terminology.

Then compare vacancy requirements with the Candidate Truth Record and produce a transparent match map without fabricating missing qualifications.

### Lead / CRM / Order identity

Separate identifiers by role, e.g.:

- campaign/source: `CM-001`, `FB-001`, `LI-001`;
- lead: `LEAD-000001`;
- client: `CL-000001`;
- candidate: `CAND-000001`;
- order: `ORD-000001` or market-aware `CO-ORD-000001`;
- product identity such as `CV-PRO-CO` or `LINKEDIN-REBUILD-CO`.

### Event-driven operating model

Even while manually operated, design the lifecycle around explicit events such as:

`LEAD_CREATED`
`LEAD_QUALIFIED`
`OFFER_SENT`
`PAYMENT_CONFIRMED`
`INTAKE_RECEIVED`
`FACTS_VALIDATED`
`POSITIONING_APPROVED`
`DRAFT_READY`
`QA_PASSED`
`CLIENT_REVIEW`
`REVISION_REQUESTED`
`FINAL_DELIVERED`
`REVIEW_REQUESTED`
`ORDER_CLOSED`

This allows future automation without redesigning the authority model.

### AI / bot direction

Do **not** deploy an autonomous customer-facing bot at the start.

Initial automation direction:

1. **AI Copilot v0.1** — generates suggested replies, package explanations, FAQ responses and intake reminders; human reviews before sending.
2. **Bot v1** — automates only proven repetitive FAQs and basic routing after sufficient real conversation evidence.
3. **Bot v2** — may perform structured lead qualification, collect basic information, recommend a package within bounded rules, create Lead ID and send intake forms.
4. **Bot v3** — semi-autonomous customer operations only after stable pricing, CRM, payments, QA gates and sufficient production evidence.

Bots must not autonomously invent career facts or metrics, negotiate exceptional cases, decide refunds/complaints, promise employment outcomes, or resolve ambiguous candidate claims.

### Analytics

Colombia should function as the measured laboratory for:

- new and qualified leads;
- paid orders;
- lead-to-customer conversion;
- revenue by channel and product;
- average order value;
- delivery time;
- revision count;
- refund rate;
- LinkedIn attach rate;
- English upgrade rate;
- vacancy add-on rate;
- repeat-customer rate;
- referral rate;
- time per order;
- revenue per delivery hour.

### Fresh-stage roadmap

Restart the canonical design sequence as:

- Stage 00 — Constitution & Vision;
- Stage 01 — Domain Model;
- Stage 02 — Colombia Market Model;
- Stage 03 — Product Architecture;
- Stage 04 — Candidate Truth System;
- Stage 05 — Lead / Client / Order System;
- Stage 06 — Intake Engine;
- Stage 07 — Career Positioning Engine;
- Stage 08 — CV / Document Engine;
- Stage 09 — LinkedIn Rebuild Engine;
- Stage 10 — Vacancy Intelligence;
- Stage 11 — Interview Engine;
- Stage 12 — QA / Trust Engine;
- Stage 13 — CRM & Client Operations;
- Stage 14 — Payments / Legal / Privacy;
- Stage 15 — Analytics;
- Stage 16 — AI Copilot;
- Stage 17 — Bot / Automation;
- Stage 18 — Market Validation;
- Stage 19 — Scale Colombia;
- Stage 20 — Brazil Readiness.

### Language rule for project work

When Spanish content is produced for this project, provide a Polish translation alongside it.

### Expansion doctrine

The system name and shared core remain country-neutral. Colombia is Market Pack #1 / Reference Implementation, not the name of the operating system.

Brazil is the next intended market after Colombia reaches sufficient maturity. Brazil must use a localized `pt-BR` market/language pack and locally validated pricing, channels, CV conventions, ATS practices and LinkedIn positioning.

Later LATAM markets should follow the same model: shared proven core, explicit market/language packs, fresh local validation.

### Strategic summary

**Think regionally. Build locally. Validate in Colombia. Automate only what reality proves. Expand only what Colombia validates.**

