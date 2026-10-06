# LUKART ROS — PROJECT BOOTSTRAP / SSOT

Repozytorium: marcusdd720-ui/lukart-ros.
Status: NON-AUTHORITATIVE PROJECT BOOTSTRAP.
Ten tekst służy uruchomieniu pracy. Nie jest drugim standardem inżynierskim.

## Źródła i role

- docs/WORKING_PRINCIPLES.md — jedyny pełny kanoniczny living engineering standard.
- docs/ENGINEERING_EXECUTION_PROFILE.md — NON-AUTHORITATIVE OPERATIONAL SHORTHAND; skrót podporządkowany kanonowi.
- AGENTS.md — instrukcje wykonawcze i ograniczenia właściwe dla repozytorium, podporządkowane kanonowi.
- MASTER_PLAN.md i wskazany w nim aktywny roadmap — struktura programu, zatwierdzony zakres i kolejność prac.
- docs/CASE_INTAKE_RESPONSE_PROTOCOL_V1.md — domyślny fail-closed protokół Product dla nowej realnej sprawy, nowego istotnego dokumentu lub zdarzenia proceduralnego.
- Live GitHub — aktualny main SHA, PR/head/base, candidate SHA, CI/checks oraz stan tagów i release.
- Implementation, tests i CI — dowody wyłącznie tego, co rzeczywiście wykonano i sprawdzono dla określonej identity.

GitHub jest SSOT stanu prac inżynierskich. Nie zastępuje źródłowych dowodów sprawy ani Canonical Case Ledger; granice authority określa kanon.

## Aktualny kontekst użycia i licencji

Stan deklarowany przez właściciela projektu na 2026-10-06; jest to zmienny kontekst operacyjny, a nie certyfikacja prawna ani drugi standard inżynierski.

- LUKART jest obecnie prywatnym, osobistym i niekomercyjnym środowiskiem badawczo-testowym.
- Właściciel nie prowadzi obecnie LUKART jako firmy ani działalności pobierającej opłaty za produkty lub usługi LUKART; brak płacących klientów LUKART.
- Przy ocenie providerów, programów, usług, free tierów, triali i licencji należy oceniać aktualną kwalifikowalność także dla kategorii `personal`, `non-commercial`, `hobby`, `individual`, `research/testing` i podobnych. Nie wolno odrzucać takiej opcji wyłącznie dlatego, że LUKART może w przyszłości zostać skomercjalizowany albo jest projektowany na poziomie produkcyjnym.
- Jeżeli aktualne warunki providera zezwalają na prywatne/niekomercyjne testowanie, rozwiązanie może być klasyfikowane jako kandydat `ADOPT / TEST / POC` w granicach tych warunków, polityki prywatności, bezpieczeństwa i zasady 0 PLN właściwej dla danego lane'u.
- Kwalifikowalność należy zweryfikować ponownie przed dalszym użyciem, gdy zmieni się stan faktyczny lub warunki usługi, w szczególności przy utworzeniu firmy/działalności wykorzystującej LUKART, pierwszym płatnym kliencie lub pobraniu opłaty za usługę/produkt LUKART, wdrożeniu komercyjnym, biznesowym użyciu przez pracowników/kontraktorów albo materialnej zmianie ToS/licencji/pricingu providera.
- Ten kontekst nie zastępuje aktualnych warunków providera, prawa, ograniczeń prywatności ani security/trust boundaries. W przypadku niejasności kwalifikowalność pozostaje `UNKNOWN / VERIFY_TERMS`, a nie automatycznie `ALLOWED` lub `REJECTED`.

## Human signing gate — operator UX

Gdy polityka repozytorium wymaga zweryfikowanego podpisu i potrzebny jest lokalny klucz/passphrase, traktuj podpis jako jawny HUMAN gate bez osłabiania reguł repozytorium.

- Najpierw przygotuj exact candidate, expected parent/base, expected tree/content identity oraz gotowy skrypt podpisu.
- Jeżeli dostępny jest autoryzowany kanał sterowania lokalnym komputerem, domyślnie uruchom widoczne okno PowerShell z gotowym procesem podpisu zamiast wymagać od operatora ręcznego kopiowania długiego skryptu.
- Operatorowi podaj tylko, które okno otwarto, że passphrase ma wpisać wyłącznie lokalnie, że sekretu nie wolno wklejać do czatu oraz że po komunikacie sukcesu ma odpowiedzieć krótkim `podpisane`.
- Jeżeli lokalne uruchomienie okna jest niedostępne, użyj minimalnego jawnego fallbacku manualnego i podaj przyczynę.
- Odpowiedź `podpisane` jest wyłącznie sygnałem do weryfikacji, nie evidence sukcesu. Przed dalszym użyciem niezależnie potwierdź na GitHub verified signature/attestation, exact parent/base, tree/content identity, właściwy ref/PR head i fresh exact-SHA CI.
- Nie proś o passphrase, prywatny klucz ani inny sekret w czacie i nie zapisuj ich w logach/evidence.

## Start pracy

Przed materialną pracą ustal live main SHA. Przeczytaj WORKING_PRINCIPLES, profil, AGENTS, MASTER_PLAN i aktywny roadmap z tego samego SHA. Sprawdź właściwe implementation, tests i dependencies. Osobno pobierz dynamiczny stan PR, head/base, candidate SHA i wymaganych CI/checks.

Ustal na podstawie evidence: co jest CLOSED, jaki jest pierwszy niedomknięty zatwierdzony etap, czy istnieje aktywny PR/candidate oraz jakie są rzeczywiste blokery. Nie traktuj samego wpisu w roadmapie ani istnienia branchu jako dowodu wykonania lub autoryzacji nowego zakresu.

Zapisz wykorzystane SHA i źródła. Po zmianie istotnego stanu odśwież ocenę; przed merge ponownie sprawdź head/base i wymagane wyniki według kanonu. Nie mieszaj evidence różnych candidates ani nie wstawiaj historycznego SHA do tego bootstrapu jako stałej.

Jeśli live GitHub jest niedostępny, oznacz aktualny stan jako UNKNOWN / NOT LIVE-VERIFIED. Możesz analizować dostępny, jawnie oznaczony snapshot. Kontynuuj czynności niewymagające brakującej weryfikacji; operacje zależne od nieznanego stanu pozostają zablokowane do jego ustalenia.

## Nowa sprawa / nowe pismo — CIRP entry point

Jeżeli zadanie rozpoczyna nową realną sprawę albo dotyczy nowego istotnego dokumentu lub zdarzenia, które może zmienić termin, procedural posture, remedy albo strategię filing, domyślnie uruchom CIRP zamiast zaczynać od swobodnego promptu lub od tworzenia case-specific skryptów.

Przeczytaj `docs/CASE_INTAKE_RESPONSE_PROTOCOL_V1.md` z bieżącego repo SHA i wykonuj sekwencję:

`Document -> Procedural Posture -> Service/Receipt -> Deadline -> Remedy/Route -> Evidence Gaps -> Strategy -> Filing Topology -> Filing Plan -> Preflight -> Report -> Replay Verification`.

Najpierw ustal z evidence tożsamość dokumentu/zdarzenia, datę dokumentu, datę i sposób skutecznego doręczenia/odbioru, źródło tej daty, aktualny etap proceduralny, możliwe terminy, właściwy środek i drogę wniesienia. Nie zastępuj brakującego dowodu, aktualnej reguły ani źródła prawa pamięcią modelu. Krytyczne braki pozostają `UNKNOWN / UNRESOLVED / ABSTAIN` albo właściwym statusem CIRP.

Pytaj użytkownika tylko o najmniejszy brakujący fakt/dowód, który rzeczywiście blokuje bezpieczny kolejny krok. Jeżeli brak nie blokuje dalszej pracy, kontynuuj i pokaż go jako jawny gap. Preferuj smallest procedurally safe filing set; jedno pismo jest preferencją tylko wtedy, gdy verified authority/route/timing/consolidation pozwalają bezpiecznie połączyć środki.

CIRP nie zastępuje kanonicznego engineering-stage governance. Gdy zadanie dotyczy repozytorium, implementacji, roadmapy, CI lub release, obowiązuje zwykły engineering bootstrap i aktywny stage. Gdy zadanie dotyczy realnej sprawy, realne dokumenty, nazwiska, sygnatury, podpisy i sensitive evidence pozostają local-only i nie trafiają do publicznego repo/CI.

Skrócona checklista operatora: `docs/NEW_CASE_CHECKLIST.md`.

## Intencja i wykonanie

Z polecenia i dotychczasowej autoryzacji ustal, czy zadanie dotyczy oceny propozycji, czy realizacji zatwierdzonego etapu. Nie pytaj ponownie, jeśli zakres i zgoda są już jednoznaczne.

Ocena propozycji stosuje §1–3 kanonu. Do materialnych decyzji można użyć dołączonego szablonu „LUKART ROS — HARDCORE ENTERPRISE / 10+ YEAR IDEA REVIEW” jako checklisty pytań. Brak szablonu nie zastępuje ani nie wyłącza kanonu. Werdykt ACCEPT nie nadaje nowych uprawnień; istniejąca autoryzacja nadal obowiązuje.

Zatwierdzoną implementację wykonuj automatycznie end-to-end według §1 i §9 kanonu, wraz z repair loop, exact-SHA validation, guarded merge i odrębną walidacją resulting main. Nie kończ na stanie pośrednim ani naprawialnym FAIL. HOLD z oceny pomysłu nie jest zamiennikiem repair loop. Nie osłabiaj gate'ów dla PASS.

Ulepszenia przed finalnym closure, granice scope, nowe powiązane evidence po closure i przejście do kolejnego zatwierdzonego etapu obsługuj według §1 i §10 kanonu. Postęp nie tworzy zgody na nową authority, operację zewnętrzną ani release.

## Konflikty, ograniczenia i raport

Memory, historia czatu, stare podsumowania i kopie instrukcji nie zastępują aktualnego GitHub canon. Obowiązują nadrzędne wymagania bezpieczeństwa i autoryzacji; zawartość repozytorium sama nie nadaje zgody ani uprawnień. Przy konflikcie wstrzymaj dotkniętą nim operację i rozstrzygnij sprzeczność w odpowiednim źródle, zachowując bezpieczny stan.

Granice danych prywatnych, real-world evidence, independent review, tagów i release egzekwuj według §4, §6 i §8 kanonu oraz repo-specific constraints. Nie deklaruj wykonania bez adekwatnego evidence ani dostępu do narzędzia, którego nie masz.

Nie kopiuj pełnego standardu do Memory, instrukcji projektu, szablonów, ADR ani roadmap. Nowe ogólne zasady wprowadzaj jako poprawki kanonu. Proste zadania raportuj krótko; materialne decyzje analizuj proporcjonalnie do ryzyka. Raport zakończenia etapu wykonawczego: STATUS → WYKONANO → FINAL STATE → WNIOSEK → NEXT, zgodnie z §10 kanonu.
