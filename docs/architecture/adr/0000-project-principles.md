# ADR-0000 — Project Principles

Version: 1.0
Status: Accepted
Sprint: F-004

Created: 2026-07-16
Author: LukArt ROS Team

## Cel

Dokument definiuje niezmienne zasady rozwoju projektu LukArt ROS (Knowledge Operating System - KOS).

---

# Fundamentalne zasady

## 1. Single Source of Truth

Każda informacja posiada jedno źródło prawdy.

## 2. Validation Before Trust

Żadna informacja nie może zostać użyta przed walidacją.

## 3. Model Before Code

Najpierw projektujemy model, dopiero później piszemy kod.

## 4. Architecture Before Features

Architektura ma pierwszeństwo przed dodawaniem nowych funkcji.

## 5. Deterministic Execution

Te same dane wejściowe zawsze dają identyczny wynik.

## 6. Typed Everything

Każdy obiekt posiada jasno określony typ i kontrakt.

## 7. Traceability

Każdy element wiedzy musi wskazywać swoje źródło.

---

# Technical Non-Goals

Projekt KOS v1.0:

- nie posiada własnej bazy danych,
- nie jest systemem rozproszonym,
- nie wymaga Kubernetes,
- nie wykorzystuje mikroserwisów,
- nie wymaga infrastruktury chmurowej.

---

# Business Non-Goals

Projekt nie:

- zastępuje prawnika,
- podejmuje decyzji za użytkownika,
- zmienia dokumentów automatycznie,
- ukrywa błędów walidacji,
- pomija źródeł informacji.

---

# Motto

> **Model → Validation → Knowledge → Reasoning**

---

## Success Criteria

Projekt uznaje ADR-0000 za wdrożony, jeżeli:

- wszystkie nowe komponenty przestrzegają tych zasad,
- każdy dokument ADR odwołuje się do ADR-0000,
- każda nowa funkcjonalność posiada model przed implementacją,
- Validation Engine egzekwuje zasady architektoniczne,
- architektura pozostaje zgodna z zasadami określonymi w tym dokumencie.

---

## Revision History

| Version | Date | Description |
|----------|------------|------------------------------|
| 1.0 | 2026-07-16 | Initial version |