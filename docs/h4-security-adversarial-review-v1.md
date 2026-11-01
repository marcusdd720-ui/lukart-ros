# H4 — Security i adversarial review: zapis wykonania (evidence)

Status: RECENZJA ZAKOŃCZONA — brak merge, brak wydania, brak zmian w delcie H1–H3.

## Wykonawca i zakres
- Profil: `lukart-validation`; karta kanban: `t_8419609e` (board `lukart-legal-os`); run ID: 2
- Linkowane Issue: https://github.com/marcusdd720-ui/lukart-ros/issues/374 (zapis wykonania: komentarz pod issue #374)
- Zakres autoryzowany: wyłącznie kod i dane syntetyczne; odczyty, diagnoza, syntetyczne próby adversarialne, zapis dowodów. Brak merge/direct-main, release/deployment, zmian credentiali/security, nowej architektury ani trust boundary. H0 pozostaje osobnym koordynatorem.

## Recenzowane zamrożone delty H1–H3 (exact SHA, odczyt z live GitHub)

| Repo | PR | Base SHA | Head SHA | Podpis commita | CI na headzie | Uwagi |
|---|---|---|---|---|---|---|
| lukart-work | #79 | 09921b8e… | 52979a5d… | zweryfikowany (G) | UNSTABLE: `validation`/`assurance` CANCELLED; brak terminalnego SUCCESS | Draft; `stage_10_closed=false`; CI wymaga odrębnego odbioru |
| lukart-ros | #348 | 7900bea7… | f316159b… | NIEPODPISANY | wszystkie required SUCCESS | gałąź BEHIND main; read-only shadow, fail-closed |
| lukart-ros | #349 | 7900bea7… | aa51cc36… | NIEPODPISANY | `PR fast gates` FAILURE (pierwotny przebieg CI PR #349) | wymagany repair loop, fresh SHA, ponowna recenzja H4 |
| lukart-ros | #350 | 7900bea7… | dfe9723a… | NIEPODPISANY | wszystkie required SUCCESS | gałąź BEHIND main; PR deklaruje signing gates HUMAN_REQUIRED |
| lukart-ros | #351 | 7900bea7… | a8424e01… | zweryfikowany (G) | wszystkie required SUCCESS | gałąź BEHIND main; nie-draft |

Żaden delta nie dodaje zależności (supply chain niezmieniona); CodeQL przechodzi; wszystkie delty jawne: shadow / NOT_ADMITTED / nieprodukcyjne, bez nowej granicy zaufania.

## Rzeczywiście wykonane testy (terminalne wyniki na exact head SHA)

1. `lukart-ros f316159b` — `tests/test_legal_os_readonly_v1.py`: **16 PASS** (malformed input: nieznane typy, nieprawidłowe digesty, niezgodność case/tenant, brak możliwości WORK => BLOCKED).
2. `lukart-ros aa51cc3` — `tests/test_legal_os_gate_map_v1.py`: **9 PASS** (bramki G0–G8, brak automatycznej promocji, odrzucanie nieznanych bramek).
3. `lukart-ros dfe9723` — `tests/test_night_shift_offline_inbox.py`: **11 PASS** (replay, idempotentna ingestia, wykrywanie konfliktu tożsamości, odrzucenie uszkodzonej kapsuły).
4. `lukart-ros a8424e0` — `tests/test_night_shift_child_process_bridge.py`: **25 PASS** (uruchomione pod WSL/Ubuntu; na Windowsie pomijane przez `os.name != posix`): wyścig wątków, strata dzierżawy między intencją a spawnem, podszycie się pod worker_id, odrzucenie brudnego/drifting worktree, bounded /proc/self/fd, kill grupy procesów, CHILD_ABORTED => RECONCILIATION_REQUIRED.
5. `lukart-work 52979a5d` — `test_generator_next`, `test_operator_rejection_transport`, `test_workflow_candidate_ownership`: **36 PASS** (w tym: fork PR nie anuluje zaufanego pushu `main`; wczesne odrzucenia HTTP bez dispatchu, ograniczona treść błędów API).
6. `lukart-work 52979a5d` — `test_stage05`: **18 SKIPPED** (wymaga izolowanej PostgreSQL, niedostępnej na hoście) → **NOT VERIFIED**.

## Syntetyczne próby adversarialne wykonane
malformed input / replay i duplikaty z wykryciem konfliktu / wyścgi równoległych startów dzieci / częściowa awaria z timeoutem i nieudanym czyszczeniem grupy procesów (szczegóły w komentarzu do Issue #374).

## Rozliczone ustalenia
- **P0** (naprawa przed merge): #349 — commit niepodpisany + `PR fast gates` FAILURE na exact SHA; repair loop (Ruff I001 + MyPy), fresh SHA, ponowna recenzja H4.
- **P1** (przed merge/aktywacją): #348 i #350 niepodpisane; #79 CI nieosiągnęło terminalnego SUCCESS (UNSTABLE, anulowane checki).
- **P2**: #348/#350/#351 BEHIND `main` (rebase przed merge; nowy SHA unieważnia stare PASS); izolacja CASE/tenant i fail-closed w #348 potwierdzone; redukcja treści błędów API w #79 potwierdzona testami transportowymi.
- **NOT VERIFIED**: dynamiczne `test_stage05` (brak PostgreSQL na hoście); ocena niezależna/ludzka — brak (`INDEPENDENT_REVIEW_REQUIRED` per `WORKING_PRINCIPLES.md` §8–9 i `MASTER_PLAN.md` §9; deklaracja agenta AI nie zastępuje oceny niezależnej).

## Oświadczenie
Nie wykonano merge ani żadnej operacji na `main`. Przygotowany kandydat z kompletem dowodów wymaga osobnej decyzji ludzkiej przed merge — zgłaszać `HUMAN_MERGE_AUTHORIZATION_REQUIRED`, nie completion.
Następny krok: właściciele H1/H2/H3 naprawiają P0/P1 we własnych pętlach repair na fresh SHA; H4 ponawia recenzję exact fresh SHA; po closure H1–H3, H5 wykonuje syntetyczny test całości (E2E).

## Weryfikacja ponowna — kanban t_8419609e, run 24 (profil lukart-validation)
Ponowna weryfikacja zamrożonych delt na exact SHAs (lokalne środowisko Windows, Python 3.14.6, uv; repo-native tooling per AGENTS.md):

- Podpisy commita (`git log --format=%G?`): #348 f316159b = N (niepodpisany); #349 aa51cc36 = N (niepodpisany); #350 dfe9723a = N (niepodpisany); #351 a8424e01 = G (zweryfikowany, ED25519); lukart-work #79 52979a5d = G (zweryfikowany). Zgodne z zapisem powyżej.
- Brak zmian w plikach zależności (pyproject.toml, pylock.toml, uv.lock, requirements) we wszystkich deltach — supply chain niezmieniona; CodeQL przechodzi; delty jawne: shadow / NOT_ADMITTED / nieprodukcyjne.
- Testy terminalne na exact head SHA:
  1. lukart-ros f316159b — tests/test_legal_os_readonly_v1.py: **14/14 PASS** (zapis mówi o 16 — wszystkie PASS; rozbieżność liczebna notowana, nie defekt).
  2. lukart-ros aa51cc3 — tests/test_legal_os_gate_map_v1.py: **9/9 PASS**.
  3. lukart-ros dfe9723 — tests/test_night_shift_offline_inbox.py: **11/11 PASS**; `ruff check` czyste.
  4. lukart-ros a8424e0 — tests/test_night_shift_child_process_bridge.py: **25/25 SKIPPED** na Windowsie (`os.name != posix`); PASS na WSL/Ubuntu niepodlegające weryfikacji na tym hoście → **NOT VERIFIED** jako PASS lokalnie.
  5. lukart-work 52979a5d — test_generator_next + test_operator_rejection_transport + test_workflow_candidate_ownership: **36 PASS**, 38 subtests PASS.
  6. lukart-work 52979a5d — test_stage05: nie da się zebrać (brak psycopg, izolowana PostgreSQL niedostępna na hoście) → **NOT VERIFIED** (ograniczenie środowiska, nie defekt).
- Gates na #349: `ruff check` FAILURE lokalnie na exact SHA (1 błąd, łatwy do naprawy) — reprodukuje `PR fast gates` FAILURE (pierwotny przebieg CI PR #349). mypy: 6 błędy platformowe (`resource`, tylko Unix) na main i deltach; 1 dodatkowy w teście #349.
- Stan CI z GitHub status checks: #79 mergeStateStatus=UNSTABLE, check w stanie DRAFT — brak terminalnego SUCCESS (zgodne z zapisem).
- Syntetyka adversarialna (malformed input, replay/duplikaty, wyścagi procesów dziecka, częściowa awaria z czasem i czyszczeniem grupy procesów): zgodna z zapisem na issue #374 (komentarz pod issue #374); odpowiadające testy jednostkowe przechodzą na exact SHAs.

Uwagi do zapisu: liczba testów #348 (14 obserwowane vs 16 zapisane — wszystkie PASS); #351 PASS wyłącznie na Linux/WSL, na Windowsie pomijane.

Rozliczenie P0/P1/P2 i NOT VERIFIED bez zmian. Recenzja H4 zakończona: brak merge, brak operacji na `main`, wymagana osobna decyzja ludzkiej przed merge — `HUMAN_MERGE_AUTHORIZATION_REQUIRED`, nie completion.
## Aktualizacja 2026-11-01 — NOWE KANDYDATY, RECENZJA NIEZAKOŃCZONA

Powyższa recenzja dotyczy starych PR i starych exact SHA. Nie certyfikuje nowych kandydatów. Stan nowej rundy H4: `INDEPENDENT_REVIEW_REQUIRED`.

- **ROS H2:** draft PR [#376](https://github.com/marcusdd720-ui/lukart-ros/pull/376), HEAD `5082fbb4d2b7eed731d9e0f6bbccb859fe1f5441`, podpis GitHub `verified=true`, CI na exact SHA: 68 SUCCESS, 0 FAILURE, 0 pending w ostatnim odczycie. Weryfikacja musi objąć redakcję błędów `HANDLER_CONTRACT_ERROR`, odczyt WORK ograniczony uprawnieniami, fail-closed, tożsamość CASE/tenant, replay i mapę bramek. Historyczny P0 #349 nie stanowi automatycznie PASS nowej zintegrowanej delty.
- **ROS H3:** draft PR [#377](https://github.com/marcusdd720-ui/lukart-ros/pull/377), świeży podpisany commit `4b30d99` na aktualnym main; ten sam zakres dwóch plików offline inbox ze starego PR #350, bez przepisywania historii. Na nowej bazie: 11 testów PASS, Ruff PASS, mypy PASS; exact-SHA CI wymaga odbioru. Recenzja wymaga kontroli lease/fencing, idempotencji, uszkodzonych kapsuł i liveness.
- **WORK H1:** draft PR [#83](https://github.com/marcusdd720-ui/lukart-work/pull/83), HEAD `4fe2f4466d59897cacfb7ece10be8149534c6793`, podpis GitHub `verified=true`. Naprawa `operator_host.py` odtworzona wcześniej na Windows, jednak `stage11-rendering` CI na tym SHA FAIL: `test_fresh_process_reproduction_is_stable` (bajty/wzorzec DOCX/PDF), więc **NOT READY / CI FAIL**. Poprawka H1 nie zmienia renderer ani golden, ale brak dowodu terminalnego PASS. Plik `operator_host.py` występuje również w PR #79: konieczna recenzja zgodności obu delt.

Nie utożsamiać samej publikacji dokumentacji z nowym niezależnym review. Brak HUMAN_MERGE_AUTHORIZATION, release, rzeczywistych spraw, admitted typów pism. Bez osłabiania testów i bez zastępowania golden.
