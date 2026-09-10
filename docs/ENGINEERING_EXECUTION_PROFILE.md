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

Przed materialną pracą pobierz live `main`, kanon, plan/roadmap, relevant implementation/tests oraz PR/CI state. Ustal `Problem → Evidence → Measurement → existing capability → real gap`. Dla materialnej decyzji zastosuj Design & Improvement Gate z §3 kanonu; preferuj brak zmiany albo smallest justified change.

Po zatwierdzeniu wykonuj etap end-to-end według §1 i §9 kanonu. FAIL uruchamia repair loop i fresh SHA. Exact-SHA PASS wymaga terminalnego dozwolonego `SUCCESS` wszystkich required checks jednego SHA. Potem: unchanged head/base → guarded merge → resulting main → post-merge validation → release/baseline guard → evidence → closure.

Nie fabrykuj human/independent/security/external review ani real-world evidence. CI/symulacja nie dowodzi fizycznej separacji, custody, real DR drill, provider durability, geographic redundancy ani real-case execution.

Po closure stosuj §10: poprawki wdrażaj w tym samym etapie tylko gdy są materialne i jednoznacznie w zatwierdzonym scope; nowe trust boundaries, decyzje biznesowe, nieodwracalne/zewnętrzne operacje lub odrębne capabilities trafiają do ordered follow-up.
