# CO Source & Authority Matrix v1

Status: RESEARCH / PLANNING BASELINE
Recorded: 2026-09-26
Jurisdiction: Colombia (CO)
Scope: source discovery, authority classification, temporal/legal-data capability, privacy boundary, adapter feasibility and fail-closed semantics.
Authority: non-authoritative research artifact. Canonical LUKART engineering standard remains `docs/WORKING_PRINCIPLES.md`; live implementation state remains GitHub.

## 1. Purpose

Define the first theoretical Colombia source map before implementation. The matrix is intended to prevent ad-hoc scraping, source conflation, hidden authority assumptions and duplicated integration work.

The matrix deliberately preserves SUIN-Juriscol as a high-value official source. It is not rejected or demoted to "untrusted web". Its role is classified separately from primary publication evidence because those functions are different.

## 2. Source classes

LUKART should not flatten all official/public sources into one trust level.

- `PRIMARY_PUBLICATION`: official publication or court-issued full decision where publication/original decision evidence is the relevant claim.
- `OFFICIAL_CONSOLIDATED`: official consolidated normative/legal information with high research and temporal value.
- `OFFICIAL_JURISPRUDENCE`: court-operated relatoría/search/full-text source.
- `OFFICIAL_OPEN_DATA`: official machine-readable dataset/API, potentially metadata-only.
- `OFFICIAL_OPERATIONAL`: official portal representing case/process/benefit/contribution/affiliation operational state.
- `DERIVED_OPEN_SOURCE`: third-party open-source derivative/index; useful for research/temporal diffs but never silently substituted for official evidence.
- `PRIVATE_CASE_DATA`: authenticated or person-specific data requiring case-scoped authorization/privacy controls.

Source class is not a single "truth score". A source can be authoritative for one proposition and insufficient for another.

## 3. Matrix v1

| Domain | Institution / Source | Access | Authority class | Temporal capability | Privacy | LUKART adapter candidate | Fallback / corroboration | Fail-closed rule |
|---|---|---|---|---|---|---|---|---|
| National normative publication | Imprenta Nacional — Diario Oficial | Web/search; publication records | PRIMARY_PUBLICATION | Publication date / edition identity | Public | `CO_DiarioOficialAdapter` | SUIN / Gestor for discovery and consolidation | If exact edition/publication cannot be established for a publication-sensitive claim, do not claim verified publication |
| Consolidated national law | Ministerio de Justicia — SUIN-Juriscol | Web; official consolidated corpus | OFFICIAL_CONSOLIDATED | Strong: vigencia, modifications, derogations, original/current text where available | Public; terms require review for automated/commercial use | `CO_SUINAdapter` | Diario Oficial for publication identity; court source for judgment full text | Parser/schema/transport uncertainty => explicit UNVERIFIED; never treat missing search result as proof of non-existence |
| Public-sector normative/legal guidance | Función Pública — Gestor Normativo | Web/search | OFFICIAL_CONSOLIDATED | Updated laws, decrees, concepts, jurisprudence; sector/public-function context | Public | `CO_FuncionPublicaAdapter` | SUIN + Diario Oficial + issuing authority | Concept/guidance must not be silently promoted to statute/court authority |
| Constitutional jurisprudence — metadata | Corte Constitucional via datos.gov.co dataset `v2k4-2t8s` | Socrata/SODA REST JSON | OFFICIAL_OPEN_DATA | Decision date; dataset monthly updates | Public | `CO_CorteConstitucionalMetadataAdapter` | Corte Constitucional Relatoría/full text | Metadata existence verifies citation metadata only; not holding/proposition support |
| Constitutional jurisprudence — full text | Corte Constitucional Relatoría | Web/full decision | OFFICIAL_JURISPRUDENCE | Decision date; historical corpus | Public | `CO_CorteConstitucionalFullTextAdapter` | datos.gov.co metadata for citation identity | No proposition verification without exact retrieved decision text/source identity |
| Supreme Court jurisprudence | Corte Suprema de Justicia — Relatorías | Web/search/full-text/publications | OFFICIAL_JURISPRUDENCE | Decision dates; chamber-specific historical corpus | Public | `CO_CorteSupremaAdapter` | CENDOJ/Rama Judicial where appropriate | Chamber/source ambiguity => no PASS; result must bind chamber + citation + date |
| Administrative high-court jurisprudence | Consejo de Estado — Relatoría | Web/search/full text | OFFICIAL_JURISPRUDENCE | Date filters, proceeding identity, subject/norm fields | Public | `CO_ConsejoEstadoAdapter` | Rama Judicial / source-linked decision | Search hit without exact full-text binding cannot establish proposition support |
| General judicial search | Rama Judicial / CENDOJ | Web/search | OFFICIAL_JURISPRUDENCE / discovery | Varies by corpus | Public | `CO_CENDOJAdapter` | Court-specific relatoría | Discovery result is not automatically a verified final source |
| Process status | Consulta de Procesos Nacional Unificada (CPNU) | Official web; underlying API requires separate contract verification | OFFICIAL_OPERATIONAL | Current/last procedural actions | Public-to-case-sensitive depending query | `CO_CPNUAdapter` research candidate | Court portal/manual official confirmation | Undocumented endpoint instability => no production contract; ambiguous/missing response != no process |
| Pensions / benefits | Colpensiones — Sede Electrónica | Official web; authenticated and some public one-click services | OFFICIAL_OPERATIONAL + PRIVATE_CASE_DATA | Current benefit/application/history state; contribution history | Sensitive/person-specific | `CO_ColpensionesAdapter` case-scoped | Official certificates/responses; user-provided records | No automated access without lawful user authorization; session/CAPTCHA/auth failure => stop |
| Contributions / enforcement | UGPP | Official web, procedures, guidance, enforcement/fiscalization services | OFFICIAL_OPERATIONAL | Current proceedings, contribution/fiscalization obligations, historical records where exposed | Sensitive/person/company | `CO_UGPPAdapter` case-scoped | Official act/notice + PILA data where authorized | Never infer debt/liability solely from a partial portal result; require exact act/evidence |
| Contribution settlement | PILA ecosystem / MinSalud framework | Official framework + authorized operators | OFFICIAL_OPERATIONAL | Period-specific contribution data | Sensitive/person/company | `CO_PILAProviderAdapterV1` with provider-specific implementations | UGPP / operator receipt / case evidence | Provider output must bind period/operator/receipt; no cross-provider silent substitution |
| Social-protection affiliations | SISPRO / RUAF | Official web/data systems | OFFICIAL_OPERATIONAL + PRIVATE_CASE_DATA | Current affiliation state; historical capability depends service | Sensitive | `CO_RUAFAdapter` user-authorized only | Administrator/source entity / case documents | Case-scoped consent/authorization required; stale administrator data must remain explicit |
| Health affiliation | ADRES / BDUA | Official public lookup + authenticated institutional systems | OFFICIAL_OPERATIONAL + PRIVATE_CASE_DATA | Current reported affiliation; explicit update date | Sensitive | `CO_ADRESAdapter` bounded lookup | EPS / SAT / official certificate | ADRES reflects data reported by EPS; mismatch => unresolved, not automatic override |
| Open government datasets | datos.gov.co / Socrata | REST/SODA JSON where dataset supports it | OFFICIAL_OPEN_DATA | Dataset-specific update cadence | Mostly public; dataset-specific | `CO_DatosGovAdapter` generic transport + per-dataset schema | Publishing institution | Dataset schema/update/owner identity must be pinned; metadata-only datasets cannot prove full-text propositions |
| Versioned derivative law corpus | legalize-dev/legalize-co | Git/Markdown | DERIVED_OPEN_SOURCE | Strong research value: reforms represented through Git/history reconstruction | Public | Research/temporal benchmark adapter only | SUIN + Diario Oficial | Never use as sole final authority; known transport/parser choices must not weaken LUKART TLS/security policy |
| Multi-source MCP | Normativa-colombiana-MCP | MCP/stdin; multiple official sources | DERIVED_OPEN_SOURCE / ADAPTER CANDIDATE | Source-dependent, including vigencia/history tools | Public + source-dependent | Deep-review candidate behind LUKART protocol adapter | Direct official sources | MCP tool output remains untrusted boundary input until source/provenance validation |
| Constitutional citation MCP | co-eli-mcp | MCP; datos.gov.co-backed metadata | DERIVED_OPEN_SOURCE / ADAPTER CANDIDATE | Dataset-dependent | Public | Strong citation-metadata adapter candidate | Direct datos.gov.co + Corte full text | Citation existence != legal holding; full-text verification required for proposition claims |

## 4. SUIN-Juriscol treatment

SUIN-Juriscol is retained as a strategic Colombia source because it offers capabilities that are directly valuable to LUKART:

- official Ministry of Justice provenance;
- consolidated normative search;
- vigencia state;
- modification/derogation/addition relationships;
- original/current text presentation where available;
- jurisprudential links and historical normative context.

LUKART should model the distinction:

```text
SUIN-Juriscol
= official consolidated legal/temporal intelligence

Diario Oficial
= primary publication evidence where exact publication identity matters
```

This is complementary, not competitive. For many workflows SUIN may be the best discovery/temporal source; for publication-sensitive evidence the system can bind the corresponding Diario Oficial identity.

## 5. Proposed Colombia adapter architecture

```text
LUKART jurisdiction-neutral core
          │
          ▼
CO Jurisdiction Pack
          │
          ├── authority policy
          ├── temporal rules
          ├── privacy/authorization policy
          ├── source registry
          └── procedural rule packs
                 │
                 ▼
ExternalSourceAdapterV1
   ├── CO_SUINAdapter
   ├── CO_DiarioOficialAdapter
   ├── CO_FuncionPublicaAdapter
   ├── CO_CorteConstitucionalAdapter
   ├── CO_CorteSupremaAdapter
   ├── CO_ConsejoEstadoAdapter
   ├── CO_CPNUAdapter
   ├── CO_ColpensionesAdapter
   ├── CO_UGPPAdapter
   ├── CO_PILAProviderAdapterV1
   ├── CO_RUAFAdapter
   └── CO_ADRESAdapter
```

MCP, REST, scraping, browser automation and authenticated portal access are transports/adapters, not Product authority models.

## 6. Common ExternalSourceAdapterV1 contract proposal

Every source adapter should expose a common result envelope:

- jurisdiction;
- source_id;
- institution;
- source_class;
- operation;
- retrieval_time;
- authoritative_url/source locator;
- exact source/document/case identity where available;
- source bytes/content digest where legally/technically permissible;
- schema/parser/adapter version;
- temporal metadata;
- privacy classification;
- authorization evidence when required;
- completeness/coverage declaration;
- explicit warnings/limitations;
- fallback/corroboration pointers;
- result status: `VERIFIED_SOURCE`, `PARTIAL`, `STALE`, `UNAVAILABLE`, `UNVERIFIED`, `AUTH_REQUIRED`, `SCHEMA_CHANGED`.

No adapter may return ordinary empty data as implicit proof of non-existence.

## 7. Theoretical first vertical slice

Do not integrate all Colombian sources at once.

Recommended first research slice:

```text
Question about a Colombian statute
→ search SUIN / Función Pública
→ resolve exact norm
→ capture vigencia/modification metadata
→ corroborate publication identity in Diario Oficial when material
→ retrieve related Corte Constitucional citation metadata
→ fetch exact official judgment full text if cited
→ Citation/Grounding/Temporal gates
→ execution receipt
→ final answer with source provenance
```

This single slice tests the reusable core needed for later Colpensiones/UGPP work without handling private personal data first.

## 8. Social-security second slice

Only after public-source legal slice is validated:

```text
user-authorized case
→ Colpensiones / UGPP / RUAF / ADRES / PILA evidence
→ private-data boundary
→ procedural/legal rule pack
→ official legal authority
→ case ledger
→ reasoning
→ filing/document plan
```

This should be synthetic-data-first until privacy, authorization, session and portal-contract behavior are validated.

## 9. Implementation decision

Current state: `RESEARCH BASELINE ONLY`.

No Colombia adapter is authorized for production merely by appearing in this matrix.

Promotion path:

`source evidence → adapter contract → synthetic fixture → focused test → adversarial test → live public-source test → privacy/security review → capability certification → limited shadow use → production decision`.

## 10. Acceleration implication

The matrix supports a broader implementation strategy: build the adapter contract, test harness, authority/temporal envelope and certification mechanism once, then implement each national source as a thin replaceable adapter.

This is materially faster and safer than building source-specific agents or jurisdiction-specific subsystems independently.
