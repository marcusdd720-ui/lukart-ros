# LUKART ROS — KANONICZNY STANDARD INŻYNIERSKI

Living standard execution/trust Post-v1. Memory/chat nie są live state. **GitHub ma pierwszeństwo** dla main SHA, PR, candidate SHA, CI i roadmap. `v1.0.1` = immutable baseline.

## 1. END-TO-END / NO-STOP

Zaakceptowany etap jest jednym zadaniem. Start: live repo → stage/PR → exact PR-head/candidate SHA → required checks. Nie zaczynaj późniejszego etapu przed closure.

`Problem → Evidence → Measurement → Design → Implementation → Focused Tests → Adversarial Tests → Full Regression → CI → Exact-SHA Validation → PR → Merge → Post-Merge Validation → Evidence → Closure`.

Nie zatrzymuj się na branchu, commicie, PR, partial PASS, `queued/pending/in_progress`, merge-ready ani naprawialnym FAIL. Finalna odpowiedź tylko przy:
1. `CLOSED / ENGINEERING PASS`; albo
2. `HARD BLOCKER`: brak wymaganej autoryzacji/sekretu/artefaktu, konieczna decyzja biznesowa, prawdziwy human/independent/external review, niezatwierdzona operacja nieodwracalna lub niedostępna/nieobsługiwana niezbędna usługa.

FAIL testu, Ruff/MyPy/CodeQL, security/policy, schema/regression, stale SHA, merge conflict, fixture/manifest/dependency issue i naprawialny CI **nie są HARD BLOCKEREM**.

Repair loop:
`FAIL → evidence → root cause → smallest justified fix → fresh SHA → focused → adversarial → regression → security/policy → exact-SHA CI → re-evaluation`.
Powtarzaj automatycznie do PASS. Nie pytaj o zgodę między zatwierdzonymi krokami. Nie osłabiaj testu, thresholda, gate'a ani trust boundary dla PASS; zmieniaj wymóg tylko gdy evidence dowodzi jego błędu.

Każda zmiana wyniku tworzy fresh SHA i unieważnia stare PASS. Nie łącz evidence z różnych SHA. Wszystkie required checks dotyczą jednego exact candidate SHA.

CI: `poll → inspect → poll` do terminal state. FAIL → repair loop; komplet SUCCESS → następny krok.

Exact-SHA PASS nie kończy etapu:
`verify unchanged PR head/base → guarded merge → resulting main SHA → post-merge validation/regression/security/policy → baseline/release side effects → evidence → closure`.
Post-merge FAIL → repair stage/PR. Po closure automatycznie rozpocznij następny zatwierdzony etap roadmapy.

## 2. FUNDAMENTY

Evidence Before Conclusion; Decision Need First; Problem First; Measurement Before Conclusion; Incremental Validation; Evidence Before Standard; Factory != Product; Build First, Discuss Only When Necessary; Single Source of Truth; Validation Before Trust; Planned != Implemented != Validated != Certified.

Proste zadania: krótko. Repo audit, architecture, trust/security, provenance/replay, migration, CI/governance, merge/release: maksymalna staranność.

## 3. HARDCORE ENTERPRISE / LONG-HORIZON

Dla większej zmiany: `live SSOT → Problem → Evidence → Measurement → existing capability/gap → Alternatives → Trade-offs → Decision → Validation`. Najpierw ustal realny gap; preferuj brak zmiany lub najmniejszą uzasadnioną modyfikację.

Oceń correctness, epistemic safety, trust boundary, data loss, nondeterminism, security, scale, recovery, provenance/replay, audit, migration i evolvability w 5–10+ year horizon, także przy failure i zmianach schema/providerów/kluczy. Preferuj deterministic, bounded, fail-closed, versioned/open, replaceable contracts i bounded lock-in.

Porównuj 2–4 materialne warianty tylko gdy mogą zmienić decyzję. **Best-Justified Solution != Most Complex Solution.** Krytyczna identity: code SHA + config/corpus digests + schema + provider/plugin versions + input/evidence digests; incomplete != identical replay. Wskaż największy failure mode/residual risk i naprawę; jeśli jest w scope, wdroż ją przed closure. Nie twórz nowej authority, gdy kanon wystarcza

## 4. EPISTEMIKA / SSOT / FAIL-CLOSED

Agent, plugin, model, renderer, telemetry, self-healing i learning pipeline nie są źródłem prawdy. Canonical Case Ledger = jedyny autorytatywny writable SSOT historii sprawy. Evidence/Gold = immutable inputs. Epistemic State, Trust Graph, reasoning, renderer, search, KQM i propagation = versioned/deterministic projections lub derived artifacts, nigdy konkurencyjny SSOT.

`Evidence → Canonical Ledger → Epistemic State → Trust Graph → Reasoning → Result → Invalidation → Recompute → Replay → verifiable evidence`.

Nie promuj FACT bez evidence; nie ukrywaj contradictions/open questions. Brak podstaw → `UNKNOWN / UNRESOLVED / ABSTAIN`. Invalid/unknown schema/API, identity, capability, credential, provenance, migration, attestation lub authorization → odmowa.

## 5. DETERMINIZM / PROVENANCE / REPLAY / MIGRACJE

Krytyczne artefakty: canonical serialization, digest binding, tamper evidence, exact code/config/schema/provider/input identity. Replay identity: code SHA + config/corpus digests + schema + provider/plugin versions + input/evidence digests. Nie nazywaj replay identycznym przy niepełnej identity. Oddziel semantic change od presentation diff.

Migracje: explicit, versioned, deterministic, możliwie idempotentne, testowane na starych danych, fail-closed dla unknown/ambiguous path. Nie twórz drugiej authority, jeśli można rozszerzyć kanon.

## 6. SECURITY / SUPPLY CHAIN / RUNTIME

Defence in depth; least privilege; deny by default; tenant/case isolation; short-lived credentials; timeout/cancellation; bounded work/concurrency; tamper detection; audit trail. Preferuj full-SHA Actions, frozen dependencies, dependency audit, SBOM/provenance, CodeQL/SAST, secret/PII gates.

Agent = bounded capability worker. Runtime: capability routing, provider/model/plugin identity/version, budgets, deterministic fallback, circuit breaker, audit. Plugin registry: jawne versions/capabilities; brak undeclared permissions.

## 7. PERFORMANCE / CONTROLLED LEARNING

Performance: `Measurement → profiling → budget → improvement → re-measurement`; mierz runtime, memory, concurrency, replay i blast radius; preferuj deterministyczne limity.

Learning/self-healing: `Failure → Candidate → Experiment → Validation → Promotion → Monitoring → optional Rollback`. Brak Candidate → Trusted bez gate. Self-healing nie rozszerza trust authority.

## 8. REVIEW / CERTYFIKACJA / RELEASE

Nie fabrykuj human/independent/security/red-team/external review/certification. Automaty mogą dać `ENGINEERING PASS`; brak wymaganej oceny → `INDEPENDENT_REVIEW_REQUIRED`. Nie przywracaj historycznych blockerów bez nowej evidence. Zamknięty release/tag = immutable. Publikacja wymaga explicit release intent + exact-SHA validation.

## 9. DEFINITION OF DONE

DONE dopiero po: implementation; focused/adversarial; regression; lint/type-check; security/policy; exact-SHA CI; validated PR-head; merge; exact main; post-merge validation; baseline/release side effects; evidence; brak naprawialnego blockera.

Branch/commit/PR/fresh SHA/partial PASS/waiting CI/merge-ready != DONE. Jeśli istnieje kolejny dozwolony i wykonalny krok pipeline, wykonaj go przed finalną odpowiedzią.

## 10. GOVERNANCE / MEMORY / KOMUNIKACJA

**SSOT:** Memory = trwałe zasady, autonomiczny sposób pracy, invarianty + pointer do kanonu. `docs/WORKING_PRINCIPLES.md` = jedyny pełny living standard. GitHub = live SHA/PR/CI/roadmap/release. AGENTS/ADR/CI/testy tylko wskazują kanon lub egzekwują repo-specific constraints; nie duplikują standardu.

Aktualizacje są informacyjne, nigdy checkpointem. Nie kończ listą „pozostaje zrobić”, jeśli możesz działać. Po closure: `STATUS`, `WYKONANO`, `FINAL STATE` (SHA, PR/merge, gates, post-merge, baseline/release, evidence), `WNIOSEK`, `NEXT`.

Po closure: `evidence → weaknesses → 2–4 material alternatives (gdy potrzebne) → trade-offs → best-justified scenario → improvements`. Ulepszenia w zatwierdzonym scope wdrażaj automatycznie no-stop; stop tylko na nowej decyzji/HARD BLOCKERZE.

## 11. NORTH STAR

LUKART ROS ma zwiększać zaufanie mimo sprzecznych danych, złośliwego inputu, awarii, zmian code/schema/providerów i skali. Każdy etap ma poprawiać correctness, epistemic safety, determinism, security, provenance/replay, resilience, observability, recovery, auditability i evolvability.
