# LUKART ROS — KANONICZNY STANDARD INŻYNIERSKI

Living standard Post-v1. Memory/chat nie są live state. **GitHub ma pierwszeństwo** dla main SHA, PR, candidate SHA, CI, roadmap i release. `v1.0.1` = immutable baseline.

## 1. END-TO-END / NO-STOP

Zaakceptowany etap jest jednym zadaniem. Start: live repo → stage/PR → exact candidate SHA → required checks. Nie zaczynaj późniejszego etapu przed closure.

Ocena pomysłu może zakończyć się `HOLD / NO MATERIAL GAP`. Sam `ACCEPT` nie rozszerza autoryzacji ani scope; naprawialny FAIL zatwierdzonej implementacji nadal wymaga repair loop.

`Problem → Evidence → Measurement → Design → Implementation → Focused Tests → Adversarial Tests → Full Regression → CI → Exact-SHA Validation → PR → Merge → Post-Merge Validation → Evidence → Closure`.

Nie zatrzymuj się na branchu, commicie, PR, partial PASS, `queued/pending/in_progress`, merge-ready ani naprawialnym FAIL. Finalna odpowiedź etapu wykonawczego tylko przy `CLOSED / ENGINEERING PASS` albo `HARD BLOCKER`: brak autoryzacji/sekretu/artefaktu, decyzja biznesowa, prawdziwy human/independent/external review, niezatwierdzona operacja nieodwracalna lub niedostępna niezbędna usługa. Naprawialne test/CI/security/schema/dependency/merge failures nie są HARD BLOCKEREM.

Repair loop:
`FAIL → evidence → root cause → smallest justified fix → fresh SHA → focused → adversarial → regression → security/policy → exact-SHA CI → re-evaluation`.
Powtarzaj automatycznie. Nie osłabiaj testu, thresholda, gate'a ani trust boundary dla PASS. Materialna zmiana tworzy fresh SHA i unieważnia stare PASS; nie łącz evidence z różnych SHA.

CI: `poll → inspect → poll` do terminal state. Exact-SHA PASS wymaga terminalnego dozwolonego `SUCCESS` wszystkich required checks tego SHA; `queued/pending/in_progress`, brak wyniku lub inny niedozwolony wynik != PASS.

Exact-SHA PASS nie kończy etapu:
`verify unchanged PR head/base → guarded merge → resulting main SHA → post-merge validation/regression/security/policy → baseline/release side effects → evidence → closure`.
Post-merge FAIL → repair stage/PR. Po closure przejdź do następnego zatwierdzonego etapu.

## 2. FUNDAMENTY

Evidence Before Conclusion; Decision Need First; Problem First; Measurement Before Conclusion; Incremental Validation; Evidence Before Standard; Factory != Product; Single Source of Truth; Validation Before Trust; Planned != Implemented != Validated != Certified.

Proste zadania: krótko. Repo audit, architecture, trust/security, replay/migration, CI/governance, merge/release: maksymalna staranność.

## 3. HARDCORE ENTERPRISE / LONG-HORIZON

Dla większej zmiany: `live SSOT → Problem → Evidence → Measurement → existing capability/gap → Alternatives → Trade-offs → Decision → Validation`. Najpierw ustal realny gap; preferuj brak zmiany lub najmniejszą uzasadnioną modyfikację.

Oceń correctness, epistemic safety, trust boundary, data loss, nondeterminism, security, concurrency, scale/performance, recovery, provenance/replay, audit/observability, migration/compatibility i evolvability w 5–10+ year horizon, także przy failure i zmianach schema/providerów/kluczy. Preferuj deterministic, bounded, fail-closed, versioned/open, replaceable contracts i explicit migrations; future-resistant, nie future-predictive.

Porównuj 2–4 materialne warianty tylko gdy mogą zmienić decyzję. **Best-Justified Solution != Most Complex Solution.** Krytyczna identity: code SHA + config/corpus digests + schema + provider/plugin versions + input/evidence digests; incomplete != identical replay. Wskaż największy failure mode i remedy. Nie twórz nowej authority, gdy kanon wystarcza.

## 4. EPISTEMIKA / SSOT / FAIL-CLOSED

Agent/plugin/model/renderer/telemetry/self-healing/learning nie są źródłem prawdy. Canonical Case Ledger = jedyny writable SSOT historii sprawy. Evidence/Gold = immutable inputs. Epistemic State, Trust Graph, reasoning, renderer, search, KQM i propagation = versioned/deterministic projections.

`Evidence → Canonical Ledger → Epistemic State → Trust Graph → Reasoning → Result → Invalidation → Recompute → Replay → verifiable evidence`.

Nie promuj FACT bez evidence; nie ukrywaj contradictions/open questions. Brak podstaw → `UNKNOWN / UNRESOLVED / ABSTAIN`. Unknown/invalid schema/API, identity, capability, credential, provenance, migration, attestation lub authorization → odmowa.

## 5. DETERMINIZM / PROVENANCE / MIGRACJE

Krytyczne artefakty: canonical serialization, digest binding, tamper evidence i pełna replay identity z §3. Nie nazywaj replay identycznym przy niepełnej identity. Oddziel semantic change od presentation diff.

Migracje: explicit, versioned, deterministic, możliwie idempotentne, testowane na starych danych, fail-closed dla unknown/ambiguous path. Nie twórz drugiej authority, jeśli można rozszerzyć kanon.

## 6. SECURITY / SUPPLY CHAIN / RUNTIME

Defence in depth; least privilege; deny by default; tenant/case isolation; short-lived credentials; timeout/cancellation; bounded work/concurrency; tamper detection; audit trail. Preferuj full-SHA Actions, frozen dependencies, dependency audit, SBOM/provenance, CodeQL/SAST, secret/PII gates.

Agent = bounded capability worker. Runtime wiąże capability, provider/model/plugin identity/version, budgets, fallback/circuit-breaker i audit. Brak undeclared permissions.

## 7. PERFORMANCE / CONTROLLED LEARNING

Performance: `Measurement → profiling → budget → improvement → re-measurement`; mierz runtime, memory, concurrency i replay.

Learning/self-healing: `Failure → Candidate → Experiment → Validation → Promotion → Monitoring → optional Rollback`. Brak Candidate → Trusted bez gate.

## 8. REVIEW / RELEASE / REAL-WORLD EVIDENCE

Nie fabrykuj human/independent/security/red-team/external review/certification. Automaty mogą dać `ENGINEERING PASS`; brak wymaganej oceny → `INDEPENDENT_REVIEW_REQUIRED`.

Nie deklaruj fizycznej separacji nośników, realnego DR drill, provider durability, key custody, geographic redundancy ani real-case validation bez realnego evidence. CI, mock, symulacja, `st_dev` lub operator metadata nie dowodzą fizycznej/organizacyjnej niezależności.

Nie przywracaj historycznych blockerów bez nowej evidence. Zamknięty release/tag = immutable; publikacja wymaga explicit release intent + exact-SHA validation.

## 9. DEFINITION OF DONE

DONE: implementation; focused/adversarial; regression; lint/type-check; security/policy; exact-SHA CI; unchanged PR head/base; merge; exact main; post-merge validation; baseline/release side effects; evidence; brak naprawialnego blockera.

Branch/commit/PR/fresh SHA/partial PASS/waiting CI/merge-ready != DONE. Jeśli istnieje kolejny dozwolony i wykonalny krok pipeline, wykonaj go przed finalną odpowiedzią.

## 10. GOVERNANCE / MEMORY / KOMUNIKACJA

**SSOT:** Memory = trwałe zasady + pointer. `docs/WORKING_PRINCIPLES.md` = jedyny pełny living standard. GitHub = live SHA/PR/CI/roadmap/release. AGENTS/ADR/CI/testy i cienkie execution profiles tylko wskazują kanon lub egzekwują repo-specific constraints; nie duplikują go. Profile są non-authoritative; przy konflikcie wygrywa live GitHub i ten plik.

Aktualizacje są informacyjne, nie checkpointem. Po closure raportuj `STATUS`, `WYKONANO`, `FINAL STATE`, `WNIOSEK`, `NEXT`.

Improvement Review: `evidence → weaknesses → alternatives → trade-offs → best-justified scenario → improvements`. Przed finalnym closure wdrażaj tylko materialne ulepszenia jednoznacznie w scope, bez nowej decyzji biznesowej, trust boundary/authority ani nieodwracalnej/zewnętrznej operacji. Resztę zapisz jako ordered follow-up bez scope creep. Po opublikowanym closure kolejne zmiany tworzą nowe powiązane SHA/evidence; nie przepisuj historycznego closure.

## 11. NORTH STAR

Każdy etap ma zwiększać correctness, epistemic safety, determinism, security, provenance/replay, resilience, observability, recovery, auditability i evolvability bez nieuzasadnionej złożoności.
