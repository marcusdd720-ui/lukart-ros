# KMeta-1.0 — Kanon Kanonów

Canonical ID: KMeta-1.0
Title: Kanon Kanonów
Version: 1.0
Status: CANDIDATE CANON
Class: METHODOLOGY
Stability Index: 4
Owner: Core Architecture
Depends On: FOUNDATION.md; accepted ADRs
Affects: all Canon documents; canon validation
Supersedes: none
Validation Method: canonical metadata validation + dependency graph + exact-SHA CI/Audit/Stage Gate
Review Requirement: independent architectural review before CANONICAL
Change Policy: versioned semantic change only

## 1. Cel

KMeta definiuje jednolity sposób tworzenia, klasyfikowania, wersjonowania, walidowania, zamrażania, zmiany i wycofywania dokumentów Kanonu Artur OS / LUKART ROS. Zapobiega konkurencyjnym definicjom, proliferacji dokumentów oraz cichym zmianom znaczenia pojęć podstawowych.

KMeta nie definiuje treści domenowych. Definiuje reguły, według których treści domenowe mogą uzyskać status kanoniczny.

## 2. Zasada nadrzędna

Żaden dokument nie staje się Kanonem wyłącznie dlatego, że został zapisany w katalogu `canon/`.

`Proposal -> Candidate -> Validation -> Review -> Freeze -> Canonical`

Dokument bez spełnionego procesu ma status nie wyższy niż Candidate.

## 3. Klasy dokumentów

Każdy dokument Kanonu MUST deklarować dokładnie jedną klasę:

1. AXIOM — niezmiennik fundamentowy.
2. ONTOLOGY — definicje bytów i relacji podstawowych.
3. EPISTEMOLOGY — reguły poznania, statusów i niepewności.
4. ALGEBRA — dozwolone operatory i kontrakty transformacji.
5. METHODOLOGY — reguły budowania, badania i walidacji Kanonu.
6. ARCHITECTURE — granice systemowe i kontrakty domen.
7. STANDARD — normy implementacyjne i interoperacyjne.
8. VALIDATION — reguły testów, pomiarów, benchmarków i certyfikacji.
9. RUNTIME — dokumentacja wykonawcza; nie może nadpisywać wyższych klas.

## 4. Poziomy stabilności

Każdy dokument MUST deklarować `Stability Index` w skali 1–5:

- 5 — ekstremalnie stabilny.
- 4 — bardzo stabilny.
- 3 — stabilny.
- 2 — umiarkowanie stabilny.
- 1 — zmienny / implementacyjny.

Wyższy Stability Index oznacza silniejszy obowiązek kompatybilności wstecznej i mocniejszy proces review.

## 5. Wymagane metadane

Każdy dokument Candidate lub Canonical MUST zawierać:

- `Canonical ID`
- `Title`
- `Version`
- `Status`
- `Class`
- `Stability Index`
- `Owner`
- `Depends On`
- `Affects`
- `Supersedes`
- `Validation Method`
- `Review Requirement`
- `Change Policy`

Brak wymaganych metadanych powoduje FAIL procesu kanonizacji.

## 6. Single Ownership Rule

Każdy dokument Kanonu ma dokładnie jednego właściciela odpowiedzialnego za jego znaczenie. Delegowanie implementacji lub review nie tworzy drugiego źródła prawdy.

Jeżeli dwa dokumenty próbują definiować ten sam byt, kontrakt lub operator, konflikt musi zostać rozwiązany przez rozdzielenie zakresów, wskazanie nadrzędności albo formalne wycofanie jednego dokumentu.

## 7. Dependency Graph

Każdy dokument MUST jawnie deklarować zależności.

1. zależność wskazuje konkretny Canonical ID i wersję lub jawnie zewnętrzne authority;
2. zależności cykliczne pomiędzy dokumentami normatywnymi są zabronione;
3. dokument niższego poziomu nie może nadpisywać dokumentu wyższego poziomu;
4. zmiana dokumentu uruchamia analizę propagacji do `Affects`;
5. brak jawnej zależności nie zwalnia z odpowiedzialności za wykryty konflikt semantyczny.

## 8. Status lifecycle

Dozwolone statusy:

- DRAFT
- PROPOSED
- CANDIDATE CANON
- VALIDATED CANDIDATE
- CANONICAL
- DEPRECATED
- SUPERSEDED
- REJECTED

Automatyzacja może wykonać testy i przygotować evidence, ale nie może sama nadać statusu CANONICAL tam, gdzie wymagane jest niezależne review.

## 9. Validation Before Canon

Przed statusem CANONICAL dokument MUST posiadać metodę walidacji adekwatną do klasy. Może to być spójność formalna, poligon syntetyczny, local private pilot bez publikacji PII, test kontraktowy, dependency graph, failure/adversarial cases lub niezależne review.

Pozytywny CI nie oznacza automatycznie walidacji semantycznej Kanonu.

## 10. Freeze

Freeze wiąże konkretną wersję dokumentu z niezmiennym identyfikatorem treści. Minimalne evidence freeze obejmuje Canonical ID, wersję, exact Git SHA, SHA-256 dokumentu lub manifestu review, datę freeze, wymagane review i wynik walidacji.

Zmiana zamrożonego dokumentu wymaga nowej wersji.

## 11. Change Propagation

Każda zmiana Candidate/Canonical MUST analizować wpływ co najmniej na zależne dokumenty Kanonu, ADR, modele danych, schematy, API/kontrakty operatorów, testy, walidację i benchmarki, Case Replay oraz Renderer, jeżeli zmiana wpływa na semantykę wyniku.

Zmiana o wpływie nieznanym nie może być uznana za bezpieczną zmianę kanoniczną.

## 12. Evidence Before Standard

Norma lub reguła nie może być promowana wyłącznie dlatego, że jest elegancka teoretycznie. Dla Architecture, Standard i Validation wymagane jest obserwowalne evidence zastosowania albo jawny status niewalidowany.

## 13. Canon != Implementation

Kanon definiuje znaczenie, granice i invarianty. Implementacja jest realizacją kontraktu. Wymiana modelu AI, biblioteki, języka, renderera lub infrastruktury nie powinna wymuszać zmiany Kanonu, jeśli semantyka i kontrakt pozostają niezmienione.

## 14. Authority order

KMeta podlega zaakceptowanym ADR oraz niezmiennikom safety/privacy/quality obowiązującym w repozytorium. Do czasu osobnego ADR formalnie włączającego KMeta do authority order, KMeta pozostaje Candidate i nie może nadpisać `FOUNDATION.md` ani `AGENTS.md`.

## 15. Minimalny szablon

```text
Canonical ID:
Title:
Version:
Status:
Class:
Stability Index:
Owner:
Depends On:
Affects:
Supersedes:
Validation Method:
Review Requirement:
Change Policy:
```

Dokument SHOULD zawierać Purpose, Definitions, Scope, Invariants, Contracts/Rules, Failure Modes, Validation, Dependencies i Change Policy odpowiednio do swojej klasy.

## 16. Failure modes KMeta

Kanonizacja MUST FAIL przy konkurencyjnym źródle prawdy, braku właściciela, cyklicznej zależności normatywnej, naruszeniu wyższego authority, braku metody walidacji, promocji bez wymaganego review, zmianie zamrożonej wersji bez nowej wersji, niejawnej zmianie semantycznej lub braku analizy propagacji.

## 17. Walidacja KMeta-1.0

KMeta-1.0 pozostaje CANDIDATE CANON do czasu:

1. zastosowania szablonu do co najmniej dwóch kolejnych dokumentów Kanonu;
2. automatycznego sprawdzenia metadata/dependency graph;
3. potwierdzenia braku konfliktu z Accepted ADR i FOUNDATION;
4. przejścia repozytoryjnych CI/Audit/Stage Gate na exact SHA;
5. niezależnego architectural review przed promocją do CANONICAL.
