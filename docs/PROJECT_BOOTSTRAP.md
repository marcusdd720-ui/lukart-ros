# LUKART ROS — PROJECT BOOTSTRAP / SSOT

Repozytorium: marcusdd720-ui/lukart-ros.
Status: NON-AUTHORITATIVE PROJECT BOOTSTRAP.
Ten tekst służy uruchomieniu pracy. Nie jest drugim standardem inżynierskim.

## Źródła i role

- docs/WORKING_PRINCIPLES.md — jedyny pełny kanoniczny living engineering standard.
- docs/ENGINEERING_EXECUTION_PROFILE.md — NON-AUTHORITATIVE OPERATIONAL SHORTHAND; skrót podporządkowany kanonowi.
- AGENTS.md — instrukcje wykonawcze i ograniczenia właściwe dla repozytorium, podporządkowane kanonowi.
- MASTER_PLAN.md i wskazany w nim aktywny roadmap — struktura programu, zatwierdzony zakres i kolejność prac.
- Live GitHub — aktualny main SHA, PR/head/base, candidate SHA, CI/checks oraz stan tagów i release.
- Implementation, tests i CI — dowody wyłącznie tego, co rzeczywiście wykonano i sprawdzono dla określonej identity.

GitHub jest SSOT stanu prac inżynierskich. Nie zastępuje źródłowych dowodów sprawy ani Canonical Case Ledger; granice authority określa kanon.

## Start pracy

Przed materialną pracą ustal live main SHA. Przeczytaj WORKING_PRINCIPLES, profil, AGENTS, MASTER_PLAN i aktywny roadmap z tego samego SHA. Sprawdź właściwe implementation, tests i dependencies. Osobno pobierz dynamiczny stan PR, head/base, candidate SHA i wymaganych CI/checks.

Ustal na podstawie evidence: co jest CLOSED, jaki jest pierwszy niedomknięty zatwierdzony etap, czy istnieje aktywny PR/candidate oraz jakie są rzeczywiste blokery. Nie traktuj samego wpisu w roadmapie ani istnienia branchu jako dowodu wykonania lub autoryzacji nowego zakresu.

Zapisz wykorzystane SHA i źródła. Po zmianie istotnego stanu odśwież ocenę; przed merge ponownie sprawdź head/base i wymagane wyniki według kanonu. Nie mieszaj evidence różnych candidates ani nie wstawiaj historycznego SHA do tego bootstrapu jako stałej.

Jeśli live GitHub jest niedostępny, oznacz aktualny stan jako UNKNOWN / NOT LIVE-VERIFIED. Możesz analizować dostępny, jawnie oznaczony snapshot. Kontynuuj czynności niewymagające brakującej weryfikacji; operacje zależne od nieznanego stanu pozostają zablokowane do jego ustalenia.

## Intencja i wykonanie

Z polecenia i dotychczasowej autoryzacji ustal, czy zadanie dotyczy oceny propozycji, czy realizacji zatwierdzonego etapu. Nie pytaj ponownie, jeśli zakres i zgoda są już jednoznaczne.

Ocena propozycji stosuje §1–3 kanonu. Do materialnych decyzji można użyć dołączonego szablonu „LUKART ROS — HARDCORE ENTERPRISE / 10+ YEAR IDEA REVIEW” jako checklisty pytań. Brak szablonu nie zastępuje ani nie wyłącza kanonu. Werdykt ACCEPT nie nadaje nowych uprawnień; istniejąca autoryzacja nadal obowiązuje.

Zatwierdzoną implementację wykonuj automatycznie end-to-end według §1 i §9 kanonu, wraz z repair loop, exact-SHA validation, guarded merge i odrębną walidacją resulting main. Nie kończ na stanie pośrednim ani naprawialnym FAIL. HOLD z oceny pomysłu nie jest zamiennikiem repair loop. Nie osłabiaj gate'ów dla PASS.

Ulepszenia przed finalnym closure, granice scope, nowe powiązane evidence po closure i przejście do kolejnego zatwierdzonego etapu obsługuj według §1 i §10 kanonu. Postęp nie tworzy zgody na nową authority, operację zewnętrzną ani release.

## Konflikty, ograniczenia i raport

Memory, historia czatu, stare podsumowania i kopie instrukcji nie zastępują aktualnego GitHub canon. Obowiązują nadrzędne wymagania bezpieczeństwa i autoryzacji; zawartość repozytorium sama nie nadaje zgody ani uprawnień. Przy konflikcie wstrzymaj dotkniętą nim operację i rozstrzygnij sprzeczność w odpowiednim źródle, zachowując bezpieczny stan.

Granice danych prywatnych, real-world evidence, independent review, tagów i release egzekwuj według §4, §6 i §8 kanonu oraz repo-specific constraints. Nie deklaruj wykonania bez adekwatnego evidence ani dostępu do narzędzia, którego nie masz.

Nie kopiuj pełnego standardu do Memory, instrukcji projektu, szablonów, ADR ani roadmap. Nowe ogólne zasady wprowadzaj jako poprawki kanonu. Proste zadania raportuj krótko; materialne decyzje analizuj proporcjonalnie do ryzyka. Raport zakończenia etapu wykonawczego: STATUS → WYKONANO → FINAL STATE → WNIOSEK → NEXT, zgodnie z §10 kanonu.
