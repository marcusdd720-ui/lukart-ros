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


## IDEA-011 — Synthetic Reality / Synthetic Assurance Fabric

Status: `DEFERRED`
Recorded: `2026-09-25`

### Problem / motivation

Both LUKART and the LATAM Career OS need large volumes of realistic test/demo data without relying on real client identities or a small hand-authored corpus.

The failure mode is not merely "insufficient fake data". The material risk is that independently generated fields look plausible in isolation while the whole scenario is internally inconsistent, irreproducible, or unable to prove what the system was expected to detect.

Examples include:

- impossible career timelines;
- unsupported skills or achievements;
- contradictory employment dates;
- legal facts that violate temporal constraints;
- missing evidence that is not detected;
- stale or wrong-jurisdiction legal authority;
- synthetic scenarios whose expected result is unknown;
- test data that changes silently after generator/provider upgrades.

### Target concept

Create a domain-neutral synthetic-generation and assurance framework capable of producing reproducible, relationally coherent, explainable synthetic worlds.

Working names:

- `Synthetic Reality Engine` — generation substrate;
- `Synthetic Assurance Fabric (SAF)` — assurance/test layer built on top of generated scenarios.

The shared core should not contain CV-specific or legal-specific semantics. Domain packages should remain separate.

Candidate structure:

```text
synthetic/
    core/
        seed
        provenance
        versioning
        manifest
    providers/
    constraints/
    scenarios/
    mutation/
    oracle/
    replay/
```

### Core design principles

1. **Canonical model before rendering**
   - generated documents are projections of a canonical scenario/person/case model;
   - the rendered CV, filing, letter, README, etc. is never the source of truth.

2. **Deterministic replay**
   - persist generator identity/version, schema version, locale/provider version, seed, policy/constraint set and artifact hash;
   - do not rely on a single library seed as a long-term reproducibility guarantee.

3. **Derived sub-seeds**
   - derive independent deterministic seeds for identity, education, career, achievements, evidence, chronology, etc.;
   - adding a new field/provider must not reshuffle unrelated previously generated state.

4. **Constraint-first generation**
   - generate values under explicit relational, temporal, jurisdictional and domain constraints;
   - reject impossible scenarios instead of post-hoc accepting plausible-looking fields.

5. **Expected Outcome Oracle**
   - every assurance scenario should carry explicit expected findings/results where applicable;
   - an LLM that generated a scenario must not be the sole oracle judging that scenario.

6. **Mutation and metamorphic testing**
   - start from a valid scenario;
   - deliberately mutate evidence, dates, jurisdiction, authority, provenance, identities or relations;
   - assert the expected failure mode deterministically.

7. **Failure-mode coverage**
   - measure coverage by scenario class, constraint, relation, failure mode, jurisdiction and temporal boundary rather than only by test count.

8. **Synthetic-data provenance**
   - distinguish internal data classes such as `REAL`, `SYNTHETIC`, `ANONYMIZED`, and `TEST`;
   - the system must never silently promote synthetic material into a real-client workflow.

### LATAM Career OS / Colombia application

Use the framework to generate coherent demonstration candidates for Colombian CV, cover-letter, LinkedIn and portfolio examples.

A canonical synthetic career should bind, for example:

- synthetic identity;
- Colombia locale (`es_CO`) provider data;
- age/education chronology;
- employment history;
- role progression;
- skills;
- achievements;
- languages;
- target roles;
- document/rendering variants.

The key requirement is coherence across all outputs: one canonical synthetic career may render into multiple CV designs, cover letters, LinkedIn sections and interview materials without contradictory facts.

A low-level library such as Python Faker may be used as a replaceable provider for locale-safe primitive data, but must not own career logic, canonical truth, validation, or replay semantics.

### LUKART application

Use the same framework pattern, with a separate legal-domain package, to generate synthetic legal cases and adversarial validation scenarios.

Candidate scenario families include:

- coherent case;
- missing evidence;
- contradictory fact;
- temporal impossibility;
- wrong jurisdiction;
- stale legal source;
- citation/source mismatch;
- provenance break;
- duplicate or substituted evidence;
- concurrency/mutation edge cases.

Each scenario should bind expected validation findings and, where safe and well-defined, expected decision constraints.

This is intended to complement — not replace — unit, contract, integration, exact-SHA, regression and independently reviewed Gold-corpus testing.

### External projects reviewed

The following external projects informed the idea but are not approved as production dependencies by this entry:

- `FakerPHP/Faker`;
- `YukinobuAsakawa/FakerPHP-Sample`;
- `yunwei37/AI-GitHub-Profile-Generator`.

Useful patterns:

- locale-aware primitive fake-data providers;
- source-data → analysis → representation pipeline;
- synthetic/demo generation.

Patterns not to adopt directly:

- PHP runtime solely for fake-data generation;
- single-RNG/seeding as a long-term replay guarantee;
- inference-first truth creation;
- random presentation decisions in assurance-critical paths;
- LLM self-evaluation as the only oracle.

### Deep technical review decision gate — 2026-09-25

The following provider/tool decisions are recorded from the comparative review:

- **Python Faker — ADAPTER-ONLY / APPROVED**
  - first practical primitive-data provider for Colombia;
  - preferred initial locale path because native `es_CO` support exists;
  - must remain behind a provider contract and MUST NOT become canonical career truth.

- **Mimesis — ADAPTER-ONLY / APPROVED AS SECONDARY**
  - useful as an alternate provider, structured-data reference and benchmark;
  - not preferred as the first Colombia provider because no dedicated `es_CO` locale was confirmed;
  - may be used to test provider portability and performance assumptions.

- **SeedFaker — RESEARCH-ONLY / HIGH PRIORITY**
  - strategically interesting for field-addressable determinism, multi-runtime reproducibility, algorithm fingerprinting and controlled corruption;
  - not accepted as a production dependency until a dedicated determinism/security/maintenance spike passes;
  - future status may be promoted to adapter-only only with evidence.

- **SDV — RESEARCH-ONLY / FUTURE POPULATION SYNTHESIS**
  - applicable to statistically representative synthetic populations learned from sufficiently large real datasets;
  - not suitable as the present primitive provider or canonical deterministic scenario engine;
  - licensing and service-use constraints require fresh review before any production adoption.

- **Synthcity — RESEARCH-ONLY / FUTURE ASSURANCE**
  - primarily valuable as a reference for privacy, quality, re-identification-risk and synthetic-data evaluation;
  - not part of the current runtime architecture.

- **Any external faker/synthetic library as core architecture — REJECT**
  - no external data generator may own canonical truth, replay semantics, constraints, provenance, scenario identity or expected outcome.

### Adopted architecture direction

The strategic component remains an internally controlled **Synthetic Core** with replaceable adapters.

The intended separation is:

```text
Synthetic Core
    ├── Canonical Domain Model
    ├── SyntheticProvider Contract
    ├── Constraint Engine
    ├── Scenario DNA / deterministic identity
    ├── Provenance + versioned manifest
    ├── Replay
    ├── Mutation / metamorphic layer
    └── Expected Outcome Oracle
             │
             ├── Career domain
             └── Legal domain
```

External libraries are subordinate providers or research inputs only.

### Scenario DNA refinement

Long-term deterministic identity should be field-addressable rather than rely solely on one sequential RNG stream.

Candidate value derivation model:

```text
value = H(
    scenario_seed,
    namespace,
    entity_id,
    field_id,
    schema_version
)
```

A scenario manifest should be able to bind at least:

- engine version;
- schema version;
- domain version;
- scenario seed;
- namespace;
- entity identity;
- field identity;
- provider identity/version;
- algorithm fingerprint where available;
- constraint-set identity;
- output hash.

Adding unrelated fields or providers should not reshuffle existing validated synthetic state.

### Colombia first implementation direction

The first implementation candidate, if/when IDEA-011 is activated, should be:

1. `Canonical Career Schema 1.0`;
2. `SyntheticProvider` protocol;
3. `FakerCOAdapter` backed by Python Faker `es_CO`;
4. `Career Constraint Engine 0.1`;
5. three controlled personas:
   - `CO-DEMO-JUNIOR-001`;
   - `CO-DEMO-MID-001`;
   - `CO-DEMO-SENIOR-001`;
6. deterministic replay + manifest/hash verification;
7. render-consistency test across CV / cover letter / LinkedIn projections;
8. deliberate mutation tests for impossible chronology and unsupported claims.

Mimesis should remain a secondary adapter candidate. SeedFaker should receive a separate research spike before any production role.

### LUKART assurance direction

LUKART should not reuse Career-domain semantics. It may reuse the Synthetic Core pattern with a separate legal scenario package containing:

- Legal Scenario Engine;
- legal/temporal/jurisdictional constraints;
- controlled mutation engine;
- independent Expected Outcome Oracle;
- failure-mode coverage;
- replay/provenance manifests.

The most interesting SeedFaker ideas for LUKART are:

- field-addressable deterministic generation;
- algorithm-drift fingerprinting;
- controlled data corruption for known-failure scenarios.

These ideas may be reimplemented internally even if SeedFaker itself is never adopted as a dependency.

### Acceptance criteria for future activation

Before promotion from `DEFERRED`:

- define a concrete Decision Need for the target domain;
- define canonical scenario schema and data-class boundary;
- prove deterministic replay across a pinned toolchain;
- add sub-seed derivation and versioned manifests;
- implement constraint validation and explicit failure states;
- prove that synthetic data cannot enter real-client state without an authorized boundary crossing;
- implement at least one independent deterministic oracle;
- implement mutation/metamorphic regression tests;
- demonstrate failure-mode coverage metrics;
- validate Colombia synthetic career coherence before using generated personas in public demo materials;
- validate LUKART synthetic cases independently before using them as assurance evidence.

Evidence Before Standard. Planned ≠ Implemented ≠ Validated ≠ Certified.

## IDEA-012 — Provider-Agnostic Messaging Gateway for LATAM Career OS

Status: `DEFERRED`
Recorded: `2026-09-25`
Primary target: LATAM Career OS, Colombia-first communication channel.

### Problem / motivation

LATAM Career OS may need a low-cost, controllable messaging channel for transactional client communication, intake, status notifications and future agent-assisted workflows without coupling the Product directly to one SMS/SaaS vendor.

The phone number, carrier/SIM, transport gateway and Product workflow are separate concerns. A gateway application does not itself provide a Colombian phone number. A real Colombia `+57` SIM/eSIM remains a separate operational asset.

The architecture must avoid vendor lock-in and must not allow a third-party messaging platform to become the source of truth for client workflow state.

### External projects reviewed

#### `capcom6/android-sms-gateway`

Decision direction: **ADOPT CANDIDATE — PRIMARY SMS TRANSPORT / FIRST PoC**.

Useful capabilities identified:

- turns an Android phone with a SIM into a programmable SMS/MMS gateway;
- REST API for sending messages;
- receiving SMS and reporting events through webhooks;
- delivery/failure/cancellation status handling;
- inbox access;
- local-server mode suitable for a zero-cost LAN proof of concept;
- private-server/self-host direction for later deployment;
- multi-SIM and multi-device operation;
- message scheduling / working-hour controls;
- rate limiting and bounded sending controls;
- MMS support;
- API/authentication and signed-webhook security mechanisms;
- client ecosystem suitable for Python/TypeScript/Go/PHP/Rust integration.

Important boundary:

- the project **does not provide a phone number**;
- it requires a real SIM/eSIM and Android device;
- a future Colombia `+57` number must be procured and controlled independently;
- the gateway should be treated as transport infrastructure, not as LATAM Career OS domain logic or canonical client state.

#### `textbee/textbee`

Decision direction: **ADAPTER / REFERENCE IMPLEMENTATION — SECONDARY PoC**.

Useful capabilities identified:

- open-source Android + backend + web dashboard stack;
- REST API;
- incoming/outgoing SMS workflows;
- webhooks and delivery history;
- self-hosting;
- JavaScript/TypeScript SDK;
- multi-device management;
- operational dashboard;
- integrations oriented toward automation;
- MCP and n8n integration patterns useful for later agent/workflow research.

Strategic value:

- strong reference for a more complete messaging product and operational UI;
- useful source of patterns for agent/MCP/n8n integration;
- higher platform complexity than the minimal Android SMS Gateway path;
- should remain replaceable behind the LATAM Career OS provider boundary.

### Adopted architecture direction

LATAM Career OS should own a provider-neutral messaging contract rather than call either external project directly from domain code.

Candidate contract:

```text
MessagingProvider

send_message()
receive_message()
get_status()
list_devices()
health_check()
```

Initial adapters:

```text
AndroidSmsGatewayProvider
TextBeeProvider
```

Future adapters may include other SMS, WhatsApp or carrier providers without changing the Product-domain workflow.

Target separation:

```text
LATAM Career OS
      |
      v
Messaging Service / Provider Contract
      |
      +--> AndroidSmsGatewayProvider
      |
      +--> TextBeeProvider
      |
      +--> future providers
```

No external gateway may become the canonical store for client identity, CV workflow state, payment state, case history or business decisions.

### Colombia-first operating model

Target long-term path:

```text
Colombia +57 SIM/eSIM
        |
        v
Android device
        |
        v
SMS Gateway
        |
        v
Provider Adapter
        |
        v
LATAM Career OS
        |
        +--> client identification
        +--> intake/status workflow
        +--> CRM/state machine
        +--> notifications
        +--> future bounded agent assistance
```

A Colombia `+57` SIM/eSIM is therefore an operational dependency, not part of the gateway software itself.

### Zero-cost proof-of-concept direction

Before buying a Colombia number, validate the architecture with an existing Android phone and an available Polish SIM.

#### SMS-00 — Android SMS Gateway PoC

Validate:

1. Android installation and permissions;
2. local/LAN server mode;
3. REST send operation;
4. incoming SMS;
5. webhook delivery;
6. delivery/failure status;
7. restart recovery;
8. reconnect behavior;
9. duplicate-event handling;
10. authentication/signature handling;
11. bounded rate behavior;
12. basic resource usage.

Target:

```text
PC / local service
      |
      | REST
      v
Android SMS Gateway
      |
      v
SIM
      |
      v
mobile network
```

#### SMS-01 — TextBee PoC

Run the same functional scenario against TextBee and compare it with SMS-00.

### Comparison / measurement gate

Do not choose production transport solely from README/features. Measure both implementations against the same test matrix:

- send latency;
- receive latency;
- delivery-status accuracy;
- reliability over extended runtime;
- restart recovery;
- network reconnect;
- duplicate delivery/event behavior;
- webhook retry behavior;
- authentication and secret handling;
- local/self-host requirements;
- resource consumption;
- operational observability;
- multi-device behavior;
- failure isolation;
- dependency complexity;
- maintenance activity;
- upgrade/replay behavior.

### Security / operational constraints

Before production activation:

- do not expose an Android local API directly to the public Internet;
- authenticate API access;
- verify webhook authenticity where supported;
- keep credentials/secrets out of repository content;
- use explicit allowlists/network boundaries where practical;
- define idempotency/duplicate-event handling;
- define message retention and deletion policy;
- treat phone numbers and message contents as client data;
- verify carrier terms and anti-spam limits;
- use bounded sending rates;
- require explicit failure states rather than silently dropping or retrying indefinitely;
- test device reboot, application restart, SIM outage and network outage.

### Intended LATAM Career OS use cases

Candidate uses include:

- transactional status notifications;
- appointment/reminder messages;
- notification that CV/cover letter work is ready;
- client intake acknowledgements;
- controlled inbound SMS intake;
- client reply capture;
- workflow transitions triggered by verified inbound events;
- future CRM integration;
- future bounded AI-assisted response preparation;
- multi-country expansion through replaceable country/provider adapters.

This is not intended as a bulk unsolicited SMS marketing engine.

### Acceptance criteria for future activation

Before promotion from `DEFERRED`:

- complete SMS-00 with a real Android + SIM;
- complete SMS-01 if comparison remains decision-relevant;
- record measured reliability/reconnect/duplicate/restart results;
- define the versioned `MessagingProvider` contract;
- prove that provider substitution does not change LATAM Career OS canonical business state;
- define secure webhook/API boundaries;
- define message idempotency and delivery-state semantics;
- validate zero-cost/local mode before adding paid infrastructure;
- separately validate procurement/ownership of a Colombia `+57` number;
- perform a fresh license/security/maintenance review of the selected external dependency;
- keep WhatsApp Business / Meta transport as a separate future adapter rather than conflating it with SMS transport.



### Owner operating decisions — Colombia number strategy

Recorded: `2026-09-25`

The current operating preference for LATAM Career OS is:

- **testing:** use free public temporary numbers where sufficient for non-sensitive SMS/OTP experiments;
- public temporary numbers are test-only and MUST NOT be used for important production accounts, recovery-critical access, client-sensitive data or long-term business identity;
- **production direction:** obtain a normal Colombian prepaid `+57` number on a physical SIM or eSIM when the project actually needs it;
- **Movistar Colombia** remains a previously reviewed prepaid candidate for the future permanent `+57` line;
- target operating model is low-cost prepaid maintenance with periodic top-ups rather than a recurring virtual-number subscription;
- the working preference is approximately one maintenance/top-up cycle every three months, but the exact validity/retention rule MUST be re-verified against the selected carrier's current terms at purchase time;
- **eSIM is optional**, not a requirement: purchase/activation should happen only when the owner decides it is useful;
- **Telnyx is rejected for the current project direction on cost grounds**;
- paid private temporary-number/OTP services are not required while free public numbers are sufficient for the current test scope;
- the permanent `+57` line, once acquired, may later be connected to WhatsApp Business and/or a provider adapter such as Android SMS Gateway or TextBee;
- the phone number/SIM remains an independently controlled operational asset and must not be coupled to one messaging software provider.

This decision intentionally optimizes for low recurring cost and operational ownership while preserving the ability to upgrade later if scale or reliability requirements justify it.

Evidence Before Standard. Planned ≠ Implemented ≠ Validated ≠ Certified.

