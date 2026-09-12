# LUKART ROS — Engineering Execution Profile

Status: **NON-AUTHORITATIVE OPERATIONAL SHORTHAND**

Ten plik nie jest drugim standardem. Pełny living standard to wyłącznie `docs/WORKING_PRINCIPLES.md`.

## Authority order

1. live GitHub — aktualne `main`, PR/head/base, CI/checks, roadmap, tag/release;
2. `docs/WORKING_PRINCIPLES.md` — kanoniczny standard inżynierski;
3. `MASTER_PLAN.md` i aktywny roadmap — struktura programu i kolejność prac;
4. ten profil — skrót wykonawczy.

Przy konflikcie wygrywa aktualny GitHub canon i `docs/WORKING_PRINCIPLES.md`.

## Execution shorthand

Przed materialną pracą ustal live `main SHA` i czytaj kanon, profil, `AGENTS.md` oraz plan/roadmap z tego samego SHA; osobno sprawdź relevant implementation/tests oraz aktualny PR/head/base/CI state. Bootstrap do ustawień projektu: `docs/PROJECT_BOOTSTRAP.md`.

Dla oceny propozycji stosuj §1–3 kanonu: ustal realny gap, a werdykt oddziel od autoryzacji wykonania. Brak potwierdzonego gapu może zakończyć review; nie zastępuje to repair loop zatwierdzonej implementacji.

Po zatwierdzeniu wykonuj etap end-to-end według §1 i §9 kanonu. FAIL uruchamia repair loop i fresh SHA. Exact-SHA PASS wymaga terminalnego dozwolonego `SUCCESS` wszystkich required checks jednego SHA. Potem: unchanged head/base → guarded merge → resulting main → post-merge validation → release/baseline guard → evidence → closure.

Nie fabrykuj human/independent/security/external review ani real-world evidence. CI/symulacja nie dowodzi fizycznej separacji, custody, real DR drill, provider durability, geographic redundancy ani real-case execution.

Ulepszenia przed finalnym closure i dalszą pracę prowadź według §1 i §10 kanonu: nowe trust boundaries, decyzje biznesowe, nieodwracalne/zewnętrzne operacje lub odrębne capabilities trafiają do ordered follow-up. Kolejne zmiany po opublikowanym closure wymagają nowych powiązanych SHA/evidence; nie przepisuj historii.
