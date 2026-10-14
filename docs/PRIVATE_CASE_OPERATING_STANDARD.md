# LUKART ROS — Standard operacyjny spraw prywatnych

Wersja: **1.5.0 (PROPOZYCJA / DRAFT PR)**  
Status: **NIEOBOWIĄZUJĄCY PROJEKT — do zatwierdzenia i scalenia do main**  
Planowane wejście w życie: **po zatwierdzonym scaleniu do main**  
Zakres: **wszystkie rzeczywiste sprawy prywatne CASE**

## 1. Hierarchia źródeł nadrzędnych i rola dokumentu

Niniejszy dokument jest jedynym aktualizowanym **standardem operacyjnym prowadzenia prywatnych spraw CASE**. Łączy obowiązujące zasady LUKART ROS; nie zastępuje kanonicznego standardu inżynieryjnego ani nie tworzy drugiego źródła prawdy o historii sprawy.

Kolejność pierwszeństwa:

1. `docs/WORKING_PRINCIPLES.md` — jedyny kanoniczny, aktualizowany standard inżynieryjny i zaufania;
2. Canonical Case Ledger — jedyne autorytatywne, zapisywalne źródło prawdy (SSOT) o historii sprawy;
3. `docs/CASE_INTAKE_RESPONSE_PROTOCOL_V1.md` — semantyka produktu CIRP;
4. kanoniczne kontrakty architektoniczne w `canon/`, zwłaszcza kontrakty Case, Problem, Evidence, Decision/Strategy oraz Document/Renderer;
5. niniejszy plik — obowiązkowe zasady organizacji i wykonywania czynności w rzeczywistych sprawach prywatnych;
6. nieautorytatywne kopie, listy kontrolne i szablony służące wyłącznie ułatwieniu pracy.

Jeżeli niniejszy dokument jest sprzeczny ze źródłem o wyższym pierwszeństwie, należy zastosować zasadę bezpiecznej odmowy działania (fail-closed) i rozstrzygnąć sprzeczność w nadrzędnym źródle kanonicznym, zamiast tworzyć konkurencyjną listę reguł.

## 2. Granice prywatności

Dokumenty rzeczywistych spraw, nazwiska, podpisy, adresy, numery telefonów, sygnatury, dokumentacja medyczna i finansowa oraz inne wrażliwe dowody mogą znajdować się **wyłącznie w środowisku lokalnym lub prywatnym**.

Publiczne repozytoria GitHub, systemy CI, nazwy gałęzi, komunikaty commitów, dokumentacja oraz dane testowe MUSZĄ zawierać wyłącznie zatwierdzony kod, ogólne reguły, przykłady syntetyczne lub materiały zanonimizowane.

Prywatna sprawa CASE stanowi odrębną granicę poznawczą i prywatności. Faktów, dokumentów i wniosków z innej sprawy NIE WOLNO włączać do bieżącej sprawy bez wyraźnie autoryzowanego powiązania między sprawami.

## 3. Tryby rozpoczęcia pracy

### 3.1 NEW CASE — nowa sprawa

Nowa sprawa prywatna rozpoczyna się w nowym czacie lub obszarze roboczym i otrzymuje stały identyfikator CASE. Operator nie musi ponownie przytaczać całego standardu.

Minimalne polecenie:

`LUKART ROS — NEW CASE: <nazwa>. CIRP REAL CASE RUN. Dokumenty załączone.`

Dopuszczalne jest równoważne, krótsze sformułowanie, jeżeli intencja jest jasna.

### 3.2 CONTINUE CASE — kontynuacja sprawy

Istniejącą sprawę kontynuuje się od jej aktualnego stanu, bez ponownej analizy od zera.

Minimalne polecenie:

`LUKART ROS — CASE <nazwa> — CONTINUE.`

Przed sformułowaniem nowych wniosków należy odtworzyć aktualny stan CASE na podstawie autoryzowanych dowodów i wcześniejszych artefaktów sprawy, a następnie przeanalizować zmiany wynikające z nowego materiału lub zdarzenia.

## 4. Obowiązkowy cykl prowadzenia sprawy

Każda prywatna sprawa CASE przebiega według poniższej kolejności, chyba że dany krok rzeczywiście nie ma zastosowania, co należy wyraźnie odnotować:

`Zakres → Potrzeba decyzyjna → Inwentaryzacja → Granica dowodowa → Model epistemiczny → Chronologia → Sprzeczności → Terminy → Legitymacja/Umocowanie → Mapa proceduralna → Badanie aktualnego prawa → Środek ochrony/Strategia → Struktura czynności procesowych → Draft A → Red Team → Draft B → Hardcore Preflight → Renderowanie → Kontrola FINISH → SEND_READY → Zatwierdzenie przez człowieka/operatora, gdy wymagane → Wysłanie/Złożenie → Potwierdzenie → Analiza nowych odpowiedzi i zmian → Odtworzenie przebiegu → Następna czynność/Zamknięcie`.

Tworzenie dokumentów następuje dopiero po czynnościach przygotowawczych. Polecenie „napisz pismo” nie upoważnia do pominięcia wcześniejszych kontroli dowodowych i proceduralnych.

## 5. Model bramek kontrolnych

### G0 — Zakres i potrzeba decyzyjna

Status `PASS` wymaga:
- określonego zakresu CASE;
- wyraźnie zdefiniowanego problemu lub potrzeby podjęcia decyzji;
- wskazania pożądanego rezultatu i minimalnego rezultatu ochronnego;
- ustalenia znanych zainteresowanych podmiotów lub reprezentowanego interesu;
- określenia granic prywatności.

Jeżeli potrzeba decyzyjna pozostaje istotnie niejednoznaczna, należy zastosować `DECISION_REQUIRED` albo `OPEN_QUESTION`.

### G1 — Inwentaryzacja dowodów

Przed wyciągnięciem wniosków należy zinwentaryzować wszystkie dostępne materiały. Każdy dowód POWINIEN posiadać:
- stały identyfikator `evidence_id` / `document_id`;
- oryginalną nazwę pliku lub oznaczenie źródła;
- źródło i pochodzenie;
- datę pozyskania;
- datę źródłową, jeżeli jest znana;
- informację, czy jest oryginałem czy kopią;
- skrót integralności (SHA-256), gdy jest to praktyczne;
- klasę wrażliwości/prywatności;
- znaczenie dla sprawy;
- fakty i twierdzenia, na poparcie których jest powoływany;
- sprzeczności lub ograniczenia.

Oryginały pozostają niezmienione. Kopie z anonimizacją, kadrowaniem lub adnotacjami są osobnymi artefaktami pochodnymi.

### G2 — Granica dowodowa i model epistemiczny

Przed wyborem strategii lub sporządzeniem projektu należy wskazać, co dostępny materiał pozwala ustalić, a czego nie pozwala potwierdzić.

Stosuje się jawne kategorie:
- `FACT` — fakt odpowiednio potwierdzony dopuszczonymi dowodami;
- `CLAIM` — twierdzenie strony lub źródła, które nie zostało niezależnie ustalone;
- `HYPOTHESIS` — możliwe do sprawdzenia wyjaśnienie;
- `INTERPRETATION` — analityczna interpretacja faktów i dowodów;
- `UNKNOWN` — brak wymaganej informacji;
- `UNRESOLVED` — nierozstrzygnięta sprzeczność lub otwarta kwestia;
- `ABSTAIN` — brak możliwości sformułowania bezpiecznego wniosku.

**Brak dowodu → brak ustalonego faktu.** Dokument dowodzi, że zawiera określone stwierdzenie, ale nie dowodzi automatycznie prawdziwości tego stwierdzenia.

Bezpośrednie oświadczenie użytkownika, klienta, strony lub świadka jest dowodem złożenia takiego oświadczenia, lecz **samo w sobie nie przekształca jego treści w `FACT`**. Dopóki twierdzenie nie zostanie niezależnie potwierdzone lub odpowiednio wykazane w obowiązującym modelu dowodowym, należy zaklasyfikować je jako `CLAIM`. Przykład: `FACT: użytkownik oświadczył X`; `CLAIM: X rzeczywiście nastąpiło/jest prawdziwe`. Ta sama zasada obowiązuje przy analizie zmian w trybie `CONTINUE`: nowa informacja od użytkownika jest nowym twierdzeniem lub oświadczeniem źródłowym, chyba że nowy materiał niezależnie potwierdza jej treść.

### G3 — Chronologia, sprzeczności i terminy

Należy sporządzić chronologię powiązaną z dowodami i zachować niepewność co do dat.

Dla każdego możliwego terminu trzeba rozróżnić:
- datę zdarzenia lub dokumentu;
- datę odbioru lub doręczenia;
- dowód odbioru lub doręczenia;
- zdarzenie uruchamiające bieg terminu;
- tożsamość przepisu lub źródła reguły;
- obliczony termin;
- bezpieczny termin wewnętrzny;
- status (`VERIFIED`, `PROVISIONAL`, `UNKNOWN_RULE`, `MISSING_INPUT`, `CONFLICTING_EVIDENCE` itd.).

Nie wolno uznawać pamięci modelu, szacunku ani niezweryfikowanej daty odbioru za zweryfikowany termin prawny.

### G4 — Legitymacja, umocowanie i procedura

Przed złożeniem pisma należy ustalić:
- kto jest stroną, pokrzywdzonym, wnioskodawcą, wierzycielem, dłużnikiem itd.;
- kto może podpisać dokument lub działać w sprawie i na jakiej podstawie;
- właściwy organ;
- organ rozpoznający środek zaskarżenia, organ przyjmujący pismo oraz drogę jego wniesienia;
- aktualny stan postępowania;
- dopuszczalność i wymagania formalne;
- czy równoległe tryby postępowania są niezależne, czy powiązane.

Nieustalona legitymacja lub reprezentacja, jeżeli wpływa na ważność czynności, stanowi bezwzględną przeszkodę w pozytywnym zakończeniu kontroli przed wysłaniem lub złożeniem pisma.

### G5 — Badanie aktualnego prawa i źródeł autorytatywnych

W odniesieniu do istotnych twierdzeń prawnych lub proceduralnych należy:
- korzystać z aktualnych, obowiązujących źródeł autorytatywnych;
- powiązać regułę z konkretnym źródłem i datą obowiązywania, jeżeli ma to znaczenie;
- odróżniać ustawę i rozporządzenie od orzecznictwa, wytycznych i komentarzy;
- weryfikować cytaty i rzeczywistą treść rozstrzygnięć;
- nie przypisywać organowi lub sądowi szerszego stanowiska niż rzeczywiście wyrażone;
- odnotowywać istotne poglądy lub źródła przeciwne i ograniczające.

Sama pamięć modelu nie wystarcza do zweryfikowania terminu, środka prawnego ani aktualnej normy prawnej.

### G6 — Środek ochrony, strategia i struktura czynności procesowych

Najpierw problem, następnie dokument.

Należy wskazywać istotnie różne bezpieczne rozwiązania tylko wtedy, gdy mogą wpłynąć na decyzję. Dla każdego znaczącego wariantu trzeba rozważyć:
- dopuszczalność prawną i proceduralną;
- rozstrzygające dowody i braki dowodowe;
- ryzyko terminowe;
- ciężar i standard dowodu, jeżeli są znane;
- właściwy organ i drogę działania;
- ryzyko finansowe i egzekucyjne;
- ryzyko naruszenia prywatności lub reputacji;
- odwracalność działania;
- zależności między postępowaniami.

Gdy jest to uzasadnione, należy stosować strategię wielotorową (np. karną, cywilną, administracyjną, finansową i dowodową). Jedno pismo jest możliwym usprawnieniem, a nie zasadą.

Statusy obejmują `RECOMMENDED`, `DECISION_REQUIRED`, `NEEDS_EVIDENCE`, `NO_SAFE_OPTION`, `ABSTAIN`.

### G7 — Projekt, Red Team i rygorystyczna kontrola przed wysłaniem lub złożeniem pisma

Końcowe dokumenty profesjonalne powstają w kontrolowanym łańcuchu integralności. Żaden etap nie może po cichu usuwać ani zmieniać istotnej treści zatwierdzonej na wcześniejszym etapie.

**Niezmiennik ciągłej integralności dokumentu — ZERO SILENT LOSS**

Od `Draft A` każda operacja tworząca lub przekształcająca dokument MUSI porównać artefakt wynikowy jednocześnie z:
1. aktualnym autorytatywnym stanem CASE i zatwierdzonym planem pisma;
2. bezpośrednio poprzednim zatwierdzonym etapem dokumentu.

Porównanie ma charakter znaczeniowy, nie tylko tekstowy. Elementy krytyczne obejmują co najmniej:
- tożsamość i adres składającego/nadawcy;
- wszystkie strony i ich role;
- adresata/organ i adres do wniesienia pisma;
- identyfikatory sprawy, sygnatury i numery referencyjne;
- żądania i petitum;
- istotne fakty i twierdzenia wraz z powiązaniami dowodowymi;
- istotne podstawy prawne i cytowania;
- daty i terminy mające wpływ na pismo;
- wykaz załączników i dowodów;
- wymogi podpisu, reprezentacji i odpisów;
- decyzje dotyczące prywatności i minimalizacji danych.

Każde istotne usunięcie, zmianę lub dodanie należy zaklasyfikować jako `INTENTIONAL_APPROVED`, `DERIVED_FORMATTING_ONLY` albo `UNEXPLAINED_REGRESSION`. `UNEXPLAINED_REGRESSION` oznacza krytyczny `FAIL`. Dopuszczalna utrata treści krytycznej wynosi **zero**.

POWINIEN być utrzymywany lekki **Manifest integralności dokumentu (Document Integrity Manifest)** jako deterministyczne, nieautorytatywne odwzorowanie zatwierdzonego stanu CASE i planu pisma. Manifest zapisuje wymagane pola i sekcje, ich pochodzenie, krytyczność i oczekiwaną obecność. Jest narzędziem walidacji, nigdy nowym źródłem prawdy.

**Etap A — projekt prawny i dowodowy**
- żądanie;
- twierdzenia faktyczne ze statusem dowodowym;
- podstawy prawne;
- orzecznictwo i inne źródła autorytatywne;
- wnioski dowodowe;
- załączniki;
- wymogi drogi wniesienia i podpisu.

**Red Team** podważa projekt z perspektywy adresata lub przeciwnika:
- niepoparte dowodami twierdzenia faktyczne;
- błędne lub nieaktualne prawo;
- nadinterpretacja orzecznictwa;
- brak legitymacji lub umocowania;
- błędny adresat lub droga wniesienia;
- brak załącznika, podpisu lub odpisu;
- przedwczesny wniosek prawny;
- sprzeczność ukryta w sformułowaniu;
- możliwe do uniknięcia ujawnienie danych lub naruszenie prywatności;
- żądanie wykraczające poza kompetencję adresata;
- niepotrzebnie agresywny język obniżający wiarygodność.

**Hardcore Preflight — rygorystyczna kontrola przed wysłaniem lub złożeniem pisma** musi obejmować co najmniej:
- tożsamość składającego lub osoby reprezentowanej;
- kompletny blok identyfikacyjny składającego/nadawcy wymagany dla adresata i rodzaju pisma, w tym pełne imię i nazwisko lub nazwę podmiotu oraz aktualny adres pocztowy/siedziby; wymagane identyfikatory stron i dane kontaktowe, gdy są niezbędne prawnie lub operacyjnie;
- pochodzenie i aktualność adresów oraz danych kontaktowych nadawcy i odbiorcy względem najnowszego autoryzowanego źródła CASE; dane istotne, nieaktualne, sprzeczne lub niezweryfikowane pozostają `UNKNOWN/UNRESOLVED`;
- legitymację i umocowanie;
- adresata, jego pełny adres i drogę wniesienia;
- status terminów;
- wyraźne żądania;
- mapowanie twierdzeń na dowody;
- mapowanie podstaw prawnych na reguły i źródła;
- wymagane załączniki;
- podpisy i odpisy;
- sprzeczności i pytania otwarte;
- bezpieczeństwo struktury i łączenia czynności;
- prywatność i minimalizację danych;
- aktualną datę i dane kontaktowe;
- brak krytycznych `UNKNOWN/UNRESOLVED` ukrytych w piśmie.

G7 weryfikuje zatwierdzoną treść i dane potrzebne do wniesienia pisma przed renderowaniem. Brak lub niezgodność wymaganych danych tożsamościowych albo adresowych nadawcy lub odbiorcy oznacza na tym etapie **krytyczny FAIL**. Utratę lub uszkodzenie treści podczas renderowania bada osobno G7.5 `FINISH`.

Krytyczny `FAIL` → `NOT_READY`. Krytyczny `UNKNOWN` → `ABSTAIN` / `REVIEW_REQUIRED`. Zaliczenie G7 pozwala renderować dokument, ale **nie** nadaje statusu `SEND_READY`.

### G7.5 — Kontrola FINISH — integralność końcowego artefaktu i regresji

`FINISH` jest ostatnią obowiązkową kontrolą jakości po renderowaniu i przed `SEND_READY`. Ma wykrywać błędy wprowadzone podczas redagowania, edycji, stosowania szablonów, konwersji, renderowania lub końcowych poprawek, nawet jeżeli wcześniejsze etapy zostały zaliczone.

FINISH MUSI ponownie odczytać końcowy artefakt widoczny dla człowieka jako nowego kandydata i porównać go z:
- zatwierdzonym `Draft B` i planem pisma;
- Manifestem integralności dokumentu, jeżeli jest stosowany;
- bezpośrednio poprzednim zatwierdzonym artefaktem lub wersją;
- aktualnym stanem CASE w zakresie tożsamości, umocowania, dat i drogi wniesienia.

FINISH sprawdza co najmniej:
- **Zgodność tożsamości:** składający/nadawca, adres, strony, role, reprezentacja;
- **Zgodność adresata:** organ, wydział, adres, kanał;
- **Zgodność oznaczeń:** sygnatura, numery sprawy i referencyjne, daty;
- **Zgodność żądań:** żadne żądanie ani petitum nie zostało osłabione, rozszerzone, zdublowane lub utracone;
- **Zgodność faktów:** żaden istotny fakt, twierdzenie ani związek z dowodem nie został po cichu usunięty ani awansowany ponad swój status dowodowy;
- **Zgodność prawna:** żadna istotna podstawa prawna ani cytowanie nie zostały po cichu usunięte, zastąpione nieaktualnym źródłem lub istotnie zmienione;
- **Zgodność załączników:** każdy przywołany załącznik występuje w wykazie, a wszystkie wymagane załączniki pozostają obecne;
- **Zgodność podpisów i odpisów:** zachowano miejsce podpisu, uprawnienie podpisującego, odpisy i formalne wymagania wykonania;
- **Zgodność prywatności:** renderowanie nie spowodowało przypadkowego ujawnienia danych;
- **Zgodność renderowania:** brak obcięć, utraty treści przy podziale stron, ukrytego tekstu, błędnych znaków, pustych stron, osieroconych nagłówków, brakujących stopek lub numerów stron, gdy są wymagane, oraz uszkodzonej pierwszej lub ostatniej strony;
- **Regresję między wersjami:** żadne krytyczne pole zatwierdzone wcześniej nie znika bez wyraźnego, zaakceptowanego powodu;
- **Aktualność dat i danych kontaktowych:** data oraz istotne dane kontaktowe i adresowe odpowiadają najnowszym autoryzowanym wartościom.

Gdy jest to technicznie wykonalne, FINISH POWINIEN łączyć:
1. automatyczne sprawdzenia tekstu wyodrębnionego z DOCX/PDF oraz oczekiwanych pól krytycznych;
2. semantyczne porównanie z wcześniej zatwierdzonym etapem;
3. oględziny pierwszej strony, stron zawierających żądania, obszaru załączników i podpisu oraz każdej strony objętej zmianą;
4. powiązanie wersji i skrótu artefaktu, aby bajty sprawdzone w FINISH były identyczne z bajtami przekazanymi do `SEND_READY`.

Każda modyfikacja po `FINISH_PASS` unieważnia ten wynik i wymaga ponownej kontroli FINISH na zmienionych bajtach. `SEND_READY` jest zatem właściwością konkretnego, zweryfikowanego artefaktu lub wersji, a nie ogólnej koncepcji projektu.

Wyłącznie `FINISH_PASS`, przy zaliczeniu wszystkich kontroli krytycznych, pozwala nadać dokładnie temu artefaktowi status `SEND_READY`.

### G8 — Wykonanie, potwierdzenie i odtworzenie przebiegu

Stan artefaktu jest jawny:

`DRAFT_A → RED_TEAMED → DRAFT_B → PREFLIGHTED → RENDERED → FINISH_PASS → SEND_READY → APPROVED → SENT/FILED → RECEIVED/DELIVERED → RESPONDED → ASSESSED → CLOSED/ARCHIVED`

`PREPARED != SENT != RECEIVED != EFFECTIVE`.

Dla każdej czynności zewnętrznej należy zarejestrować potwierdzenie obejmujące:
- dokładny dokument, wersję i skrót;
- datę i godzinę;
- nadawcę;
- odbiorcę;
- kanał lub drogę wniesienia;
- dowód złożenia;
- dowód odbioru lub doręczenia, jeżeli jest dostępny;
- termin odpowiedzi lub datę kontroli;
- odpowiedź i wynikającą z niej zmianę stanu CASE.

Odpowiedź lub istotne zdarzenie uruchamia analizę zmian. Historyczne analizy zachowuje się, a nie przepisuje po cichu.

## 6. Standard dokumentu — SEND_READY

Końcowe pismo musi być profesjonalnym artefaktem, a nie projektem z czatu.

O ile miejsce docelowe nie narzuca innego formatu, mechanizm renderujący POWINIEN zapewnić:
- format A4;
- czytelną, profesjonalną czcionkę;
- spójną hierarchię akapitów;
- odpowiedni lewy margines do fizycznego złożenia lub wpięcia dokumentu, gdy jest to istotne;
- numerację stron;
- poprawny blok nadawcy, w tym pełny aktualny adres pocztowy lub siedziby, gdy jest to właściwe dla danego pisma;
- poprawny blok adresata, w tym pełny adres do wniesienia pisma;
- aktualną datę;
- sygnaturę lub numer sprawy, gdy ma zastosowanie;
- miejsce podpisu;
- uporządkowany wykaz załączników;
- brak wewnętrznych komentarzy CASE, informacji diagnostycznych, etykiet spekulacyjnych i nieużywanych pól zastępczych;
- DOCX lub PDF, albo oba formaty, gdy są żądane lub właściwe.

Samo renderowanie nigdy nie nadaje statusu `SEND_READY`. Wygenerowany DOCX/PDF MUSI przejść G7.5 `FINISH` dla dokładnie tych bajtów artefaktu, które mają zostać przekazane. Kontrola musi potwierdzić, że zatwierdzone bloki tożsamościowe i adresowe, strony, adresat, data, sygnatura, żądania, istotna treść faktyczna i prawna, obszar podpisu oraz wykaz załączników są obecne, czytelne i nie zostały obcięte, podmienione ani pominięte. Każda niezgodność cofa artefakt do najwcześniejszego etapu, którego dotyczy, i unieważnia wcześniejsze statusy FINISH/SEND_READY.

Szablony określają wygląd, a nie prawdę. Mechanizm renderujący NIE MOŻE wymyślać faktów, samodzielnie rozstrzygać sprzeczności ani zmieniać strategii. Jeśli podczas renderowania ujawni się brak istotnej informacji, należy wrócić do odpowiedniej kontroli.

### 6.1 Zasady redagowania pism prawnych — domyślnie język procesowy

O ile miejsce docelowe, jurysdykcja lub polecenie użytkownika nie wymagają istotnie innego stylu, profesjonalne pisma CASE MUSZĄ posługiwać się **językiem prawnym i procesowym skierowanym do organu**, a nie stylem potocznym, emocjonalnym czy ozdobnym.

Domyślne cechy pisma:
- profesjonalny język prawniczy w języku polskim, dostosowany do adresata i etapu postępowania;
- stanowczy, powściągliwy i precyzyjny ton — **asertywny, nigdy niepotrzebnie agresywny**;
- żądanie na pierwszym planie: adresat ma od razu rozumieć, czego się żąda, na jakiej podstawie i jakiej czynności się oczekuje;
- zwięzły opis stanu faktycznego ograniczony do okoliczności istotnych dla żądanego skutku;
- jednoznaczne role stron, umocowanie, sygnatura i stan postępowania;
- wyraźne oddzielenie ustalonych faktów, twierdzeń stron, interpretacji i kwestii nierozstrzygniętych;
- brak retoryki, oburzenia, moralizowania, gróźb, sarkazmu i zbędnych przymiotników;
- brak wewnętrznych etykiet CASE, języka diagnostycznego i znaczników epistemicznych w piśmie zewnętrznym, chyba że mają znaczenie prawne.

### 6.2 Najpierw petitum — struktura przydatna decydentowi

Dokument ma służyć osobie podejmującej decyzję, a nie autorowi.

Preferowana kolejność, jeżeli jest prawnie właściwa:
1. tożsamość, strony, organ i oznaczenie sprawy;
2. precyzyjny tytuł odpowiadający żądanej czynności procesowej;
3. numerowane **petitum i żądania**;
4. najkrótsza wystarczająca podstawa faktyczna;
5. podstawa prawna i skutek proceduralny;
6. dowody i załączniki, gdy są potrzebne;
7. podpis i wymagane elementy formalne.

Każde żądanie MUSI:
- mieścić się w kompetencji adresata;
- być prawnie i proceduralnie dopuszczalne zgodnie z najlepiej zweryfikowanym stanem wiedzy;
- być na tyle konkretne, aby można je było wykonać lub rozstrzygnąć;
- odpowiadać granicy dowodowej i strukturze czynności procesowych;
- nie zawierać ukrytych żądań alternatywnych, chyba że strategia świadomie je przewiduje.

Obszerne uzasadnienie NIE MOŻE przesłaniać żądania.

### 6.3 Oszczędność powoływania źródeł prawa — przepisy mają pełnić funkcję

Źródła prawne służą argumentacji, a nie dekoracji. **Weryfikacja właściwych aktualnych przepisów i adekwatnego orzecznictwa jest obowiązkowa dla istotnego zagadnienia prawnego niezależnie od długości pisma; cytowanie jest selektywne i musi realnie wspierać żądanie.** Obowiązuje jeden próg jakości określony w § 8.1–8.2.

Należy preferować najmniejszy wystarczający zbiór aktualnych i autorytatywnych przepisów oraz orzeczeń, które istotnie potwierdzają:
- dopuszczalność, legitymację i kompetencję;
- żądaną czynność proceduralną;
- normę materialną rzeczywiście sporną w sprawie;
- właściwy ciężar dowodu, termin lub skutek.

Nie należy dodawać przepisów wyłącznie po to, aby pismo wyglądało bardziej prawniczo. Liczba cytatów nie świadczy o jakości.

Dla każdego powołanego przepisu lub źródła autor POWINIEN umieć odpowiedzieć:
- **Jakie twierdzenie potwierdza to źródło?**
- **Czy twierdzenie ma znaczenie dla decyzji adresata?**
- **Czy źródło jest aktualne, wiążące lub autorytatywne na deklarowanym poziomie i prawidłowo opisane?**

Orzecznictwo dodaje się tylko wtedy, gdy zmienia, wyjaśnia lub istotnie wzmacnia argument. Tezy orzeczeń należy przedstawiać wąsko i wiernie.

### 6.4 Język dostosowany do siły dowodów

Stanowczość sformułowania MUSI odpowiadać sile dowodów.

Przykłady:
- mocne dowody: „z dokumentu wynika…”, „Sąd ustalił…”, „akta wskazują…”;
- twierdzenie strony: „powód wskazuje/twierdzi…”, „według oświadczenia…”;
- wnioskowanie: „okoliczność ta przemawia za…”, „może wskazywać…”;
- kwestia nierozstrzygnięta: nie należy przekształcać jej w stwierdzenie kategoryczne.

Nie wolno używać silniejszych sformułowań procesowych wyłącznie dla efektu retorycznego, gdy nie uzasadniają tego dowody.

### 6.5 Kontradyktoryjny test każdego zdania

Każde istotne zdanie `Draft B` POWINNO przejść cztery pytania:
1. **Dowód:** jaki dowód lub zweryfikowane źródło je potwierdza?
2. **Istotność:** dlaczego adresat potrzebuje tego zdania do rozstrzygnięcia żądanej czynności?
3. **Podstawa:** jeżeli zdanie ma charakter prawny, jaka norma lub źródło je potwierdza?
4. **Związek z żądaniem:** jak zdanie wspiera, chroni lub ogranicza żądanie?

Jeżeli zdanie nie przechodzi żadnego z czterech testów, należy je usunąć. Jeśli przechodzi je tylko częściowo, należy je zawęzić lub odpowiednio zastrzec.

Jest to kontrola jakości redakcji, a nie nakaz wydłużania pism. Najlepsze pismo to najkrótsze pismo, które bezpiecznie wykazuje i żąda tego, co niezbędne.

### 6.6 Kalibracja stanowczości procesowej

„Stanowczość” oznacza:
- jednoznaczne żądania;
- precyzyjne określenie skutków prawnych i proceduralnych;
- wyraźne zastrzeżenie praw, gdy jest strategicznie uzasadnione;
- jasne oczekiwanie odpowiedzi lub dalszej czynności, gdy jest właściwe;
- brak osłabiania uzasadnionego stanowiska sformułowaniami niejasnymi lub przepraszającymi.

„Stanowczość” **nie oznacza**:
- oskarżeń bez dowodów;
- gróźb wykraczających poza dostępne środki prawne;
- obraźliwych lub konfrontacyjnych przymiotników;
- spekulacyjnych zarzutów;
- nadmiernego cytowania prawa;
- zbędnej eskalacji.

Celem jest **maksymalna wiarygodna siła argumentacji przy minimalnych niepotrzebnych tarciach**.

### 6.7 Zachowanie treści między etapami dokumentu

`Draft A` może zawierać pomocnicze wyjaśnienia, które później zostaną skrócone, lecz `Draft B` i artefakt końcowy MUSZĄ zachować każdy istotny element zatwierdzonego planu pisma.

Skracanie jest dopuszczalne tylko wtedy, gdy znaczenie, tożsamość i rola stron, zakres żądań, powiązania dowodowe oraz skutek prawny pozostają niezmienione.

Pole lub sekcję obecną na wcześniejszym zatwierdzonym etapie można usunąć wyłącznie po jawnym zaklasyfikowaniu zmiany zgodnie z zasadą ZERO SILENT LOSS. Istotne pominięcie wskutek uproszczenia to `UNEXPLAINED_REGRESSION`.

### 6.8 Architektura argumentacji — od zagadnienia do żądania

Dla istotnych pism proces redakcyjny POWINIEN utrzymywać wewnętrzną mapę argumentacji przed przygotowaniem `Draft A` lub podczas jego tworzenia:

`Problem → Zagadnienie → Fakt/Dowód → Norma/Źródło → Zastosowanie → Kontrargument → Odpowiedź → Żądanie`

Jest to model kontrolny, a nie obowiązkowy układ sekcji pisma zewnętrznego. Ostateczne pismo może skracać lub zmieniać kolejność prezentacji dla większej czytelności procesowej, lecz wewnętrzny łańcuch MUSI pozostać możliwy do prześledzenia.

Dla każdego istotnego zagadnienia należy:
- określić dokładne pytanie prawne lub proceduralne;
- powiązać z nim wyłącznie potwierdzone fakty lub odpowiednio oznaczone twierdzenia;
- wskazać aktualną normę i źródło;
- wyjaśnić zastosowanie bez wyolbrzymiania znaczenia dowodów;
- wskazać najsilniejszy istotny kontrargument, jeśli można racjonalnie oczekiwać jego podniesienia;
- odpowiedzieć na niego wąsko i precyzyjnie;
- powiązać wniosek z konkretną żądaną czynnością lub środkiem ochrony.

Pismo NIE MOŻE zawierać argumentu, którego nie da się powiązać z konkretnym zagadnieniem lub oczekiwanym rezultatem.

### 6.9 Model decyzji adresata

Każde pismo MUSI być zaprojektowane pod kątem następnej zgodnej z prawem czynności decydenta.

Przed redakcją należy wewnętrznie odpowiedzieć:
- Kto faktycznie podejmuje decyzję lub wykonuje czynność?
- Jakiej dokładnie decyzji, postanowienia, czynności, korekty, ujawnienia informacji lub odpowiedzi się żąda?
- Jakie kompetencje ma adresat?
- Jakie minimalne fakty i przesłanki prawne muszą być jasne, aby mógł działać?
- Co adresat musi znaleźć w ciągu 30–60 sekund?

Jeżeli adresat nie może szybko ustalić, **kto występuje, w jakiej sprawie, o jaką dokładnie czynność wnosi, na jakiej minimalnej podstawie faktycznej i prawnej oraz co ma nastąpić dalej**, dokument wymaga przeprojektowania.

### 6.10 Mapa ciężaru i standardu dowodu

Dla istotnych spornych twierdzeń proces redakcyjny POWINIEN utrzymywać wewnętrzną mapę ciężaru i standardu dowodu:

`Twierdzenie → Status dowodowy → Kto musi je wykazać → Obowiązujący ciężar/standard, jeśli zweryfikowany → Aktualne dowody → Brakujące dowody → Skutek niewykazania`

Mapa jest szczególnie ważna, gdy wynik zależy od:
- zapłaty lub jej braku;
- doręczenia lub odbioru;
- umocowania lub reprezentacji;
- zatrudnienia lub dochodów;
- związku przyczynowego lub szkody;
- przedawnienia;
- spełnienia przesłanek administracyjnych;
- egzekucji i księgowania;
- oszustwa, złej wiary lub innych twierdzeń o stanie świadomości.

Pismo końcowe NIE MOŻE po cichu przekształcać słabo udokumentowanego twierdzenia w kategoryczny fakt tylko dlatego, że mocniejsze sformułowanie brzmi bardziej przekonująco.

### 6.11 Hierarchia źródeł prawa i dyscyplina źródłowa

Dobór źródeł odbywa się według poniższej preferowanej kolejności, dostosowanej do jurysdykcji i zagadnienia:

1. aktualne, wiążące przepisy konstytucyjne, ustawowe i wykonawcze;
2. wiążące lub istotnie autorytatywne orzeczenia sądów wyższych instancji;
3. odpowiednie orzecznictwo sądów odwoławczych i pierwszej instancji;
4. oficjalne wytyczne instytucji i opublikowane informacje proceduralne;
5. uznane komentarze i doktryna jako wsparcie wtórne.

Dla istotnych twierdzeń źródła pierwotne mają pierwszeństwo przed opracowaniami wtórnymi.

Źródła niższego rzędu NIE WOLNO przedstawiać jako wiążącego. Komentarz NIE MOŻE zastępować dostępnego źródła pierwotnego przy istotnym zagadnieniu aktualnego prawa.

### 6.12 Standard czytelności dla sądu i organu

Profesjonalne pismo POWINNO umożliwić zajętemu sędziemu, referendarzowi, urzędnikowi sądowemu, komornikowi, urzędnikowi administracyjnemu lub innemu decydentowi ustalenie w ciągu pierwszych 30–60 sekund:
- stron, składającego i jego roli;
- adresata lub organu;
- sygnatury lub numeru sprawy;
- stanu postępowania;
- dokładnego żądania;
- 2–4 rozstrzygających faktów lub przesłanek;
- głównej podstawy prawnej;
- istotnych dowodów i załączników;
- oczekiwanej następnej czynności adresata.

Czytelność jest elementem jakości merytorycznej. Nadmiernie skomplikowany język prawniczy, rozbudowane cytaty, powtórzenia lub ozdobna formalność utrudniające zrozumienie ścieżki decyzyjnej są wadą.

**Precyzja prawna != niepotrzebna złożoność.**

### 6.13 Zasada ciągłego wzmacniania standardu

Niniejsze zasady redagowania są standardem aktualizowanym. MUSZĄ być wzmacniane, gdy dowody z rzeczywistych spraw CASE ujawniają powtarzający się lub istotny mechanizm błędu.

Cykl doskonalenia:
`Zaobserwowany błąd → Przyczyna źródłowa → Najmniejsza reguła lub kontrola możliwa do uogólnienia → Aktualizacja niniejszego standardu → Walidacja w odpowiednim procesie → Zachowanie historii zmian`.

Nie należy tworzyć konkurencyjnych pełnych standardów V2/V3 dla zwykłej ewolucji zasad.

Nowe kontrole POWINNY być dodawane wyłącznie wtedy, gdy:
- zapobiegają wykazanemu lub racjonalnie przewidywalnemu istotnemu błędowi;
- zwiększają poprawność, dyscyplinę dowodową, bezpieczeństwo proceduralne, integralność, czytelność lub odtwarzalność;
- nie powodują nieproporcjonalnej biurokracji w prostych sprawach.

Standard MUSI rozwijać się na podstawie dowodów, a nie wyłącznie preferencji stylistycznych.

## 7. Identyfikowalność powiązań między dowodem a twierdzeniem

Istotne twierdzenia faktyczne w profesjonalnym dokumencie POWINNY być możliwe do powiązania z dopuszczonymi dowodami lub wyraźnie oznaczone jako twierdzenia strony.

Preferowany schemat dla spraw złożonych:

`Dowód E-xxx → Fakt/Twierdzenie F/C-xxx → Zagadnienie prawne/proceduralne P-xxx → Środek ochrony/Strategia R/S-xxx → Żądanie pisma Q-xxx`

Gdy jest to praktyczne, należy zachowywać skróty i wersje artefaktów wystarczające do odtworzenia przyczyn sporządzenia konkretnej wersji pisma.

## 8. Adaptacyjny przebieg CASE — minimum powtórzeń, pełne kontrole krytyczne

### 8.1 Jeden niezmienny standard jakości — LUKART HARDCORE ENTERPRISE / UNIVERSUM

**Każda rzeczywista sprawa CASE i każde pismo mają jeden, najwyższy poziom wymaganej staranności prawnej, dowodowej, procesowej i redakcyjnej.** Nie ustanawia się klas jakości, poziomów usług ani uproszczonego standardu poprawności zależnego od długości pisma, liczby dokumentów, wartości sporu lub liczby postępowań. Krótkie pismo może spełniać ten sam standard co obszerne pismo procesowe: o jakości decydują trafność żądania, prawo, dowody i skuteczność, a nie długość, liczba cytatów lub czas analizy.

Dziewięć etapów (§ 13.2) jest mapą kontroli i nawigacji, a **nie** obowiązkiem wykonania dziewięciu odrębnych analiz, wyszukiwań, raportów lub rund pytań do operatora. G0–G8 i G7.5 pozostają obowiązującymi granicami bezpieczeństwa tam, gdzie mają zastosowanie; ich wynik może powstawać w jednym przebiegu lub zostać odziedziczony z wcześniej zweryfikowanego, wciąż aktualnego stanu CASE z jawnie zachowaną proweniencją. Brak rzeczywistej kontroli nigdy nie staje się `PASS`.

Interfejs operatora przedstawia domyślnie trzy **obszary pracy, a nie poziomy jakości**: **ANALIZA → PISMO → FINALIZACJA I WYKONANIE**. Pełna mapa dziewięciu etapów i statusy poszczególnych kontroli pozostają dostępne na żądanie. Nie należy tworzyć dodatkowych ekranów i raportów, gdy nie wpływają na decyzję lub bezpieczeństwo.

### 8.2 Uniwersalne kryteria jakości i proporcjonalność nakładu

Każde pismo musi przed `SEND_READY` przejść te same **kryteria jakości**, a zakres wykonanych czynności ma odpowiadać rzeczywistemu ryzyku i potrzebie decyzyjnej:

1. **Cel i dopuszczalność:** jednoznaczny adresat, strona i umocowanie, właściwość organu, etap postępowania, właściwy środek ochrony i droga wniesienia; petitum możliwe do rozpoznania i wykonania.
2. **Dowody:** każda istotna okoliczność ma źródło i właściwy status `FACT/CLAIM/INTERPRETATION/UNKNOWN/UNRESOLVED`; sprzeczności i luki są ujawnione, a nie rozstrzygane domysłem.
3. **Aktualne przepisy:** sprawdzić istotne podstawy materialne i procesowe w oficjalnych źródłach odpowiednich dla jurysdykcji i właściwej daty, w tym brzmienie oraz zastosowanie konkretnych artykułów. W piśmie wskazać przepisy realnie wspierające żądanie; jeśli przytoczenie artykułu byłoby nieadekwatne dla czynności o charakterze wyłącznie faktycznym albo formularzowym, odnotować uzasadnione `N/A` w kontroli wewnętrznej, nie dopisywać pozornej podstawy.
4. **Orzecznictwo:** dla istotnego zagadnienia prawnego sprawdzić adekwatne i przeciwne orzeczenia właściwych sądów, w pierwszej kolejności źródła pierwotne; weryfikować sygnaturę, datę, tezę, stan faktyczny i aktualność. W piśmie przywołać rzeczywiste orzeczenie, jeśli istotnie wspiera lub ogranicza argumentację; brak relewantnego orzeczenia oznaczyć wewnętrznie, nigdy nie tworzyć sygnatur ani dekoracyjnych cytatów.
5. **Argumentacja i siła procesowa:** stanowczy, profesjonalny język prawniczy, związek `żądanie → fakt/dowód → norma → zastosowanie`, właściwy ciężar dowodu oraz odpowiedź na najważniejszy realny kontrargument. Mocne petitum nie może wykraczać poza dowody ani kompetencję adresata.
6. **Terminy i wykonanie:** każda istotna data, doręczenie, termin, sygnatura, ścieżka wniesienia, podpis, załącznik i dane stron muszą mieć właściwy status weryfikacyjny; krytyczny brak blokuje zależną czynność, nie jest uzupełniany domysłem.
7. **Kontrola kontradyktoryjna i integralność:** faktyczny Red Team, Hardcore Preflight, ZERO SILENT LOSS, kontrola prywatności oraz G7.5 `FINISH` końcowego artefaktu są obowiązkowe; stopień rozbudowania testu jest proporcjonalny do ryzyka, **ale żaden krytyczny warunek dopuszczenia nie jest obniżany**. Zmiana po `FINISH_PASS` unieważnia ten wynik.
8. **Decyzja o gotowości:** `SEND_READY` tylko przy kompletnych kontrolach krytycznych, właściwych źródłach i braku blockerów; wysłanie/złożenie wyłącznie po odrębnej autoryzacji. Nie obiecywać skutku procesowego ani wyniku sprawy.

**Adaptacyjny jest tylko nakład pracy, nigdy jakość:** jedno zagadnienie i jeden komplet dowodów mogą być zweryfikowane oraz opracowane w jednym przebiegu bez mnożenia raportów. Przy wielu organach, spornych doręczeniach, rachunkach, tytułach wykonawczych, przedawnieniu, sprzecznościach lub istotnym ryzyku rozszerzyć analizę i oddzielić postępowania w sub-CASE. Oceny dokonuje się na podstawie ryzyka terminu, liczby niezależnych procedur, zależności dowodowych, rozliczeń, konfliktów i skutku możliwego błędu, a nie przez nadanie sprawie etykiety jakościowej. Krytyczny brak blokuje tylko czynności od niego zależne; reszta prac toczy się bez resetu.

### 8.3 Struktura spraw wielowątkowych

Dla spraw obejmujących kilka autonomicznych postępowań lub istotne zależności prowadzić poniższe widoki jako projekcje z Canonical Case Ledger, a nie alternatywne źródła prawdy:

1. **CASE MASTER** — wspólny cel, stan nadrzędny, mapa powiązań, priorytety i najbliższe nieodwracalne terminy; bez wielokrotnego kopiowania pełnych analiz sub-CASE.
2. **Sub-CASE** — każde odrębne postępowanie/środek ochrony ma własne żądania, termin, stronę uprawnioną, organ, drogę wniesienia, status i plan pisma. Powiązania między sprawami są jawne i autoryzowane; materiał z jednej nie przechodzi automatycznie do drugiej.
3. **Evidence Index** — pojedyncza rejestracja oryginału z identyfikatorem, źródłem, datą, skrótem/deduplikacją, zakresem i odnośnikami do wszystkich zagadnień, których dotyczy. Oryginały niezmienione; przeszukiwanie selektywne. Kopia, skan i wcześniejsze streszczenie nie stają się nowymi faktami przez samo powtórzenie.
4. **Event/Deadline Ledger** — daty czynności, doręczeń i dowodów odbioru; osobne wyzwalacze i reguły prawne dla każdego terminu oraz ich statusy VERIFIED/PROVISIONAL/UNKNOWN.
5. **Financial/Enforcement Ledger**, gdy dotyczy — każdą transakcję i czynność egzekucyjną powiązać z dowodem; rozdzielić wpłatę od jej zaksięgowania, a należność główną od odsetek i kosztów. Rozliczać według funduszu, okresu, tytułu, daty i rodzaju alokacji; stosować obliczenia deterministyczne z uzgodnieniem sald i kontrolą duplikatów. Nie wnioskować o podwójnej zapłacie ani przedawnieniu jedynie z podobieństwa kwot, tytułów lub dat.
6. **Issue/Dependency Map** — dla każdego zagadnienia: dowody, sporne twierdzenia, norma, istotne orzecznictwo, brak, zależne decyzje i pisma. Wzajemne powiązanie jest relacją dowodową, nie automatycznym połączeniem postępowań.

Dane rzeczywistych klientów, ich liczby, nazwiska, sygnatury i dokumenty pozostają lokalnie/prywatnie. Repozytorium publiczne przechowuje tylko ogólne reguły i dane syntetyczne.

### 8.4 Obsługa nowego materiału bez resetu

Domyślny mechanizm kontynuacji:

`NEW DOCUMENT → SOURCE INTAKE → DEDUP/IDENTITY → FACT/CLAIM CLASSIFICATION → DELTA → DEPENDENCY IMPACT → DEADLINE/RISK PRIORITY → ONLY AFFECTED RECHECK → NEXT ACTION`.

**Zgodność z CIRP:** nowy materialny dokument lub zmienione krytyczne wejście wymaga nowego przebiegu CIRP z własną tożsamością wejść (`CIRPRunIdentity`); nie nadpisuje to wcześniejszego przebiegu i nie resetuje CASE. Ponowne wykorzystanie wcześniejszej kontroli jest dozwolone wyłącznie po potwierdzeniu zgodności zakresu CASE, dowodów i ich pochodzenia, identyfikatorów reguł, aktualności źródeł oraz braku wpływu nowego materiału na kontrolowany wynik. Każdy odziedziczony wynik musi zachować identyfikator przebiegu źródłowego i nowego przebiegu CIRP, zakres kontroli, pochodzenie dowodów oraz jawną decyzję o aktualności; `PASS` wolno odziedziczyć wyłącznie po spełnieniu tych warunków. Stosować istniejące mechanizmy selekcji zweryfikowanych dowodów, projekcji i replay CIRP; nowa tożsamość przebiegu nie uprawnia do deklarowania `IDENTICAL` replay starego wyniku ani do odziedziczenia nieaktualnego `PASS`.

W pierwszej kolejności sprawdzić, czy nowe pismo uruchamia pilny termin albo zmienia status doręczenia. Następnie porównać je z istniejącym indeksem i ustaleniami. Nie czytać ponownie wszystkich historycznych materiałów, jeżeli nie występuje konkretna sprzeczność, brak pochodzenia, zmiana normy, brak integralności lub zależność wymagająca ponownej oceny. Nowy dowód może ponownie otworzyć zatwierdzoną kontrolę tylko gdy podważa jej przesłankę; pozostałe wyniki zachowują historię, ważność i proweniencję.

Nie wykonywać ponownie tego samego researchu prawnego przy każdej czynności, jeśli aktualność normy, stan faktyczny i zakres zastosowania są nadal zweryfikowane. **Każde nowe istotne twierdzenie prawne i każdą potencjalnie zmienioną regułę trzeba jednak zweryfikować w źródłach aktualnych dla danej daty; przegląd adekwatnego orzecznictwa jest obowiązkowy, lecz brak relewantnego orzeczenia nie uzasadnia wymyślania ani dekoracyjnego cytowania go w piśmie.**

### 8.5 Minimalny wynik operatora

Po istotnej czynności zamiast obszernego raportu podawać w jednym krótkim widoku: `CASE → OBSZAR/ETAP → CO NOWE/ZWERYFIKOWANO → STATUS → BLOKER (jeśli jest) → NASTĘPNA CZYNNOŚĆ`. Dla wielowątkowego CASE dodać mapę sub-CASE i priorytetowej kolejki. Rozwinięte kontrole lub historia pozostają dostępne na żądanie.

**Najlepiej uzasadnione rozwiązanie != najbardziej skomplikowane rozwiązanie.** Uproszczenie interfejsu i liczby powtarzanych czynności nie obniża rygoru dowodowego, prawnego, procesowego, prywatności ani FINISH.

## 9. Pytania do operatora lub użytkownika

Nie należy prosić użytkownika o ponowne podanie informacji już znajdujących się w CASE lub możliwych do pozyskania z autoryzowanych źródeł.

Pytania należy ograniczyć do najmniejszej rzeczywiście blokującej informacji, takiej jak:
- tożsamość, legitymacja lub reprezentacja;
- brakujący dokument źródłowy;
- dowód odbioru lub doręczenia;
- wymagany podpis lub umocowanie;
- brakujący dowód transakcji;
- rzeczywista decyzja między istotnie różnymi bezpiecznymi strategiami.

Braki nieblokujące pozostają jawnie oznaczone jako `UNKNOWN/UNRESOLVED`, a praca trwa do granicy dostępnych dowodów.

## 10. Rzetelność deklaracji o walidacji rzeczywistej sprawy

Nie wolno deklarować:
- walidacji rzeczywistej sprawy bez faktycznego przetworzenia prywatnych dowodów tej sprawy;
- doręczenia bez potwierdzenia;
- skutku prawnego tylko dlatego, że wygenerowano dokument;
- niezależnej, ludzkiej, bezpieczeństwa lub profesjonalnej kontroli, jeśli nie została faktycznie wykonana;
- dokładnego odtworzenia przebiegu bez kompletnych, powiązanych identyfikatorów i artefaktów.

Syntetyczne testy CI sprawdzają działanie techniczne, a nie prawdziwość lub poprawność prawną rzeczywistej sprawy.

## 11. Zamknięcie i ponowne otwarcie sprawy

CASE może zostać zamknięty, gdy:
- aktywne cele zostały osiągnięte, cofnięte, przekazane lub zaakceptowane jako nierozstrzygnięte;
- wymagane czynności i kontrole następcze zostały zakończone;
- pozostałe niewiadome wyraźnie nie blokują zamknięcia albo zostały przekazane do monitorowania;
- odnotowano powód zamknięcia, upoważnienie i stan końcowy.

Zamknięcie utrwala możliwy do audytu obraz stanu; nie usuwa historii. Nowy istotny materiał może ponownie otworzyć CASE jako nowy stan lub przebieg z zachowaniem dowodów wcześniejszego zamknięcia.

## 12. Wersjonowanie i zmiany

Niniejszy dokument jest aktualizowanym standardem operatora. Nie należy tworzyć plików `V2`, `V3` dla zwykłych ulepszeń.

Dla istotnego ulepszenia należy:
1. wskazać konkretny mechanizm błędu lub lukę jakościową;
2. sprawdzić, czy istniejąca reguła już ją obejmuje;
3. w miarę możliwości doprecyzować istniejącą regułę;
4. podnieść wersję semantyczną w tym pliku, jeżeli zmiana ma istotny charakter znaczeniowy;
5. aktualizować nieautorytatywne kopie tylko wtedy, gdy to konieczne;
6. zachować historię poprzez commity Git i PR, zamiast tworzyć konkurencyjne dokumenty.

CASE POWINIEN, gdy jest to praktyczne, zapisywać wersję standardu operacyjnego i commit repozytorium użyte przy istotnych przebiegach lub pismach.

## 13. Obowiązkowy interfejs Stage Gate dla CASE

### 13.1 Widoczny status po każdej istotnej czynności

Po każdej istotnej czynności w rzeczywistej sprawie CASE należy wyświetlić identyfikator CASE, aktywny obszar/etap, nowe lub sprawdzone ustalenia z odniesieniem do dowodów, wynik (`NOT_STARTED`, `IN_PROGRESS`, `PASS`, `FAIL`, `BLOCKED`), rzeczywiste blokery i następną czynność. Zakres widoku ma być proporcjonalny do złożoności (§ 8); nie trzeba publikować dziewięciu osobnych raportów. Wynik bez rzeczywistej walidacji i źródła nigdy nie otrzymuje statusu `PASS`.

**Intelligent UI jest domyślnie obowiązkowe w każdej rzeczywistej sprawie CASE prowadzonej w obsługującym je interfejsie ChatGPT/GPT-6**, od przyjęcia dokumentu przez analizę i projekt pisma aż po kontrolę finalną i kontynuację. Należy używać rzeczywistych interaktywnych kontrolek, gdy przynoszą wartość: widok CASE/zagadnień/sub-CASE, statusów i blockerów, zakładki **ANALIZA / PISMO / FINALIZACJA I WYKONANIE**, a także działające **Wstecz**, **Podgląd dalej** i **Wykonaj kontrolę**. Wstecz/Podgląd służą do przeglądania i nie zmieniają autorytatywnego stanu. Kontrola musi uruchamiać rzeczywistą ocenę i nie przyznaje automatycznie PASS. Widok demonstracyjny należy jednoznacznie odróżnić od odczytu faktycznego stanu CASE.

Gdy bieżący klient lub kanał technicznie nie obsługuje Intelligent UI, należy wyraźnie zgłosić ograniczenie i zapewnić równoważną, krótką nawigację tekstową; **nie wolno twierdzić, że Intelligent UI zostało użyte, jeśli go nie wyrenderowano**. Intelligent UI jest warstwą obsługi i prezentacji: samo przełączanie zakładek nie zapisuje do Canonical Case Ledger, nie zatwierdza dokumentów i nie wysyła pism.

### 13.2 Nawigacja po dziewięciu etapach z zachowaniem istniejących bramek

1. Inwentaryzacja i granica dowodowa (G0–G2).
2. Chronologia, sprzeczności, terminy, legitymacja i mapa proceduralna (G3–G4).
3. Badanie aktualnego prawa (G5).
4. Strategia, struktura czynności procesowych i Draft A (G6–początek G7).
5. Red Team i poprawki (G7).
6. Hardcore Preflight — rygorystyczna kontrola przed wysłaniem lub złożeniem pisma (G7).
7. Renderowanie DOCX/PDF, G7.5 FINISH, a następnie `SEND_READY` wyłącznie po kontroli `FINISH_PASS` konkretnego artefaktu.
8. Wyraźna autoryzacja oraz wysłanie lub złożenie pisma (G8).
9. Potwierdzenie, analiza odpowiedzi i zmian, odtworzenie przebiegu oraz zamknięcie (G8).

Są to wewnętrzne grupy kontroli, a nie dziewięć obligatoryjnych osobnych ekranów, rozmów lub ponownych analiz. Domyślny Intelligent UI agreguje je w trzy obszary (§ 8.1); pełną mapę dziewięciu etapów można rozwinąć do przeglądu lub kontroli konkretnego etapu. Dotychczasowy obowiązkowy cykl i kolejność krytycznych bramek pozostają nadrzędne, a sprawdzone, nadal aktualne wyniki są wykorzystywane bez nieuzasadnionego resetu.

### 13.3 Nawigacja nie jest walidacją

**Wstecz** i **Podgląd dalej** zmieniają wyłącznie wyświetlany etap. Nigdy nie ustawiają `PASS`, nie zapisują historii sprawy, nie omijają krytycznej bramki, nie zatwierdzają ani nie wysyłają pisma i nie stwierdzają doręczenia. **Wykonaj kontrolę etapu** uruchamia żądanie rzeczywistej oceny; nie jest przyciskiem automatycznego `PASS`. Należy pokazać dowody, ustalenia, blokery i następną dopuszczalną zmianę etapu. Trwałe zmiany stanu CASE wymagają autoryzowanej ścieżki zapisu do Canonical Case Ledger; stan widoczny tylko w interfejsie nie jest autorytatywny.

Krytyczny `FAIL/BLOCKED` uniemożliwia `SEND_READY`. Renderowanie nie oznacza `SEND_READY`. Wymagany jest `FINISH_PASS` dla konkretnego artefaktu; każda późniejsza zmiana artefaktu unieważnia ten wynik.

### 13.4 Automatyczna kontynuacja i ścieżka audytowa

W trybie `CONTINUE` należy odtworzyć ostatni autoryzowany stan i ocenić wyłącznie zmiany. Wcześniej zamknięte bramki można ponownie otworzyć tylko z wyraźnego powodu opartego na dowodach. Rutynowe kontrole i redagowanie należy wykonywać automatycznie, gdy istnieje upoważnienie; pytania ograniczać do rzeczywistych blokerów lub wyraźnej zgody na działanie zewnętrzne. Uruchomienie kontroli nigdy nie może automatycznie powodować wysłania pisma.

Dla każdej ukończonej bramki należy zapisać autoryzowanym mechanizmem: identyfikator bramki, odniesienia do dowodów i artefaktów, faktycznie wykonane kontrole, wynik, blokery, znacznik czasu, jeśli jest dostępny, oraz następną zmianę etapu. Nie wolno deklarować trwałego zapisu bez dowodu.

`DRAFT != PREFLIGHTED != RENDERED != FINISH_PASS != SEND_READY != APPROVED != SENT/FILED != RECEIVED/DELIVERED != EFFECTIVE`.

## 14. Domyślny sposób działania operatora

W projekcie ChatGPT dotyczącym prywatnych spraw CASE niniejszy standard obowiązuje domyślnie. Użytkownik nie powinien musieć wklejać długiego polecenia dla każdej sprawy.

Dla każdego polecenia `NEW CASE` lub `CONTINUE` należy:
- odczytać i stosować niniejszy standard oraz źródła nadrzędne;
- izolować dane poszczególnych spraw CASE;
- kontynuować działania od początku do końca w granicach dostępnych dowodów i upoważnień;
- nie renderować pism końcowych przed kontrolą G7;
- nigdy nie nadawać wyrenderowanemu pismu bezpośrednio statusu `SEND_READY`; najpierw wymagany jest `FINISH_PASS` dla dokładnego artefaktu;
- na każdym etapie tworzenia dokumentu egzekwować ZERO SILENT LOSS przez porównanie kandydata z zatwierdzonym stanem CASE i planem pisma oraz wcześniejszym zatwierdzonym etapem dokumentu;
- nie zatrzymywać pracy na problemie redakcyjnym lub badawczym, który można rozwiązać;
- precyzyjnie raportować blokery, zamiast pozorować pewność.
