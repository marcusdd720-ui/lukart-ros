# KMeta-1.0 — Kanon Kanonów

Status: CANDIDATE CANON
Poziom: Meta-governance Kanonu
Owner: Core Architecture

## 1. Cel

KMeta definiuje jednolity sposób tworzenia, klasyfikowania, wersjonowania, walidowania, zamrażania, zmiany i wycofywania dokumentów Kanonu Artur OS / LUKART ROS. Jego zadaniem jest zapobieganie konkurencyjnym definicjom, proliferacji dokumentów oraz cichym zmianom znaczenia pojęć podstawowych.

KMeta nie definiuje treści domenowych. Definiuje reguły, według których treści domenowe mogą uzyskać status kanoniczny.

## 2. Zasada nadrzędna

Żaden dokument nie staje się Kanonem wyłącznie dlatego, że został zapisany w katalogu `canon/`.

Status kanoniczny jest wynikiem jawnego procesu:

`Proposal -> Candidate -> Validation -> Review -> Freeze -> Canonical`

Dokument bez spełnionego procesu ma status nie wyższy niż Candidate, nawet jeśli jego treść jest technicznie poprawna.

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

- 5 — ekstremalnie stabilny; zmiana wyjątkowa.
- 4 — bardzo stabilny; wymaga dowodu naruszenia lub konieczności systemowej.
- 3 — stabilny; zmiana wymaga walidacji i review.
- 2 — umiarkowanie stabilny; może ewoluować po testach kontraktowych.
- 1 — zmienny; implementacja/runtime.

Wyższy Stability Index oznacza silniejszy obowiązek kompatybilności wstecznej i mocniejszy proces review.

## 5. Wymagane metadane dokumentu

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

Każdy dokument Kanonu ma dokładnie jednego właściciela odpowiedzialnego za znaczenie dokumentu. Właściciel może delegować implementację lub review, ale nie może istnieć dwóch równorzędnych źródeł prawdy dla tej samej definicji.

Jeżeli dwa dokumenty próbują definiować ten sam byt, kontrakt lub operator, konflikt musi zostać rozwiązany przez:

1. rozdzielenie zakresów,
2. wskazanie dokumentu nadrzędnego,
3. albo formalne wycofanie jednego z dokumentów.

## 7. Dependency Graph

Każdy dokument MUST jawnie deklarować zależności.

Reguły:

1. zależność musi wskazywać konkretny Canonical ID i wersję lub zakres wersji;
2. zależności cykliczne pomiędzy dokumentami normatywnymi są zabronione;
3. dokument niższego poziomu nie może nadpisywać dokumentu wyższego poziomu;
4. zmiana dokumentu musi uruchomić analizę propagacji do wszystkich dokumentów `Affects`;
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

Przejścia statusów są jawne i audytowalne. Automatyzacja może wykonać testy i przygotować evidence, ale nie może sama nadać statusu CANONICAL tam, gdzie wymagane jest niezależne review.

## 9. Validation Before Canon

Przed statusem CANONICAL dokument MUST posiadać metodę walidacji adekwatną do klasy.

Przykładowe metody:

- spójność formalna,
- test na poligonie syntetycznym,
- test na lokalnym private pilot bez publikacji PII,
- test kontraktowy implementacji,
- analiza dependency graph,
- failure/adversarial cases,
- niezależne review.

Sam brak błędów składniowych lub pozytywny CI nie oznacza walidacji semantycznej Kanonu.

## 10. Freeze

Freeze oznacza związanie konkretnej wersji dokumentu z niezmiennym identyfikatorem treści.

Minimum evidence freeze:

- Canonical ID,
- wersja,
- exact Git SHA,
- SHA-256 dokumentu lub manifestu review,
- data freeze,
- wymagane review,
- wynik walidacji.

Zmiana zamrożonego dokumentu wymaga nowej wersji. Nie wolno nadpisywać znaczenia istniejącej wersji.

## 11. Change Propagation

Każda zmiana Candidate/Canonical MUST wykonać analizę wpływu co najmniej na:

- zależne dokumenty Kanonu,
- ADR,
- modele danych,
- schematy,
- API/kontrakty operatorów,
- testy,
- walidację i benchmarki,
- Case Replay,
- Renderer i artefakty wyjściowe, jeżeli zmiana wpływa na semantykę wyniku.

Zmiana o wpływie nieznanym nie może zostać uznana za bezpieczną zmianę kanoniczną.

## 12. Evidence Before Standard

Norma lub reguła nie może być promowana wyłącznie dlatego, że jest elegancka teoretycznie. Dla dokumentów Architecture, Standard i Validation wymagane jest co najmniej jedno obserwowalne evidence zastosowania albo jawne oznaczenie jako jeszcze niewalidowane.

## 13. Canon != Implementation

Dokument Kanonu definiuje znaczenie, granice i invarianty. Implementacja jest jednym z możliwych realizatorów kontraktu.

Wymiana modelu AI, biblioteki, języka programowania, silnika renderującego albo infrastruktury nie powinna wymuszać zmiany Kanonu, jeśli semantyka i kontrakt pozostają niezmienione.

## 14. Konflikt z istniejącym authority order

KMeta podlega zaakceptowanym ADR oraz niezmiennikom safety/privacy/quality już obowiązującym w repozytorium. Do czasu osobnego ADR formalnie włączającego KMeta do authority order, KMeta pozostaje Candidate i nie może cicho nadpisać `FOUNDATION.md` ani `AGENTS.md`.

## 15. Minimalny szablon dokumentu Kanonu

Każdy nowy dokument powinien rozpoczynać się blokiem:

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

Następnie MUST zawierać co najmniej:

1. Purpose
2. Definitions
3. Scope
4. Invariants
5. Contracts / Rules
6. Failure Modes
7. Validation
8. Dependencies
9. Change Policy

## 16. Failure modes KMeta

Kanonizacja MUST FAIL, gdy wystąpi co najmniej jeden z warunków:

- konkurencyjne źródło prawdy,
- brak właściciela,
- cykliczna zależność normatywna,
- naruszenie wyższego authority,
- brak metody walidacji,
- promocja bez wymaganego review,
- zmiana zamrożonej wersji bez nowej wersji,
- niejawna zmiana semantyczna,
- brak analizy propagacji zmiany.

## 17. Walidacja KMeta-1.0

KMeta-1.0 pozostaje CANDIDATE CANON do czasu:

1. zastosowania jego szablonu do co najmniej dwóch kolejnych dokumentów Kanonu;
2. sprawdzenia dependency graph na istniejących dokumentach;
3. potwierdzenia, że reguły nie kolidują z Accepted ADR i FOUNDATION;
4. przejścia repozytoryjnych CI/Audit/Stage Gate na exact SHA;
5. niezależnego architectural review przed promocją do CANONICAL.
