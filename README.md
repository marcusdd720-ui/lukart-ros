# lukart-ros

Projekt Artur 2.0 - System bazowy.

## MVROS v1

MVROS v1.0.0 udostępnia punkt wejścia do uruchomienia pipeline'u wiedzy.

### Granica prywatności danych

Publiczne repozytorium GitHub zawiera wyłącznie kod, testy, dokumentację oraz dane syntetyczne/non-sensitive.

**Rzeczywiste sprawy, dokumenty źródłowe, dane osobowe, sygnatury i numery spraw pozostają wyłącznie na lokalnym dysku.** Nie wolno kopiować ich do repozytorium, commitować, wysyłać do GitHub Actions ani umieszczać w logach CI.

Do lokalnych danych służy prywatny katalog wskazywany przez `MVROS_DATA_ROOT`. Gdy zmienna nie jest ustawiona, MVROS używa `~/MVROS-DATA`.

```bash
python scripts/new_case.py "MOJA_SPRAWA"
python scripts/run_case_pipeline.py --case "MOJA_SPRAWA"
```

Można wskazać własny prywatny magazyn:

```bash
python scripts/new_case.py "MOJA_SPRAWA" --data-root "D:\MVROS-DATA"
python scripts/run_case_pipeline.py --case "MOJA_SPRAWA" --data-root "D:\MVROS-DATA"
```

MVROS odmówi użycia katalogu znajdującego się wewnątrz checkoutu Git albo zawierającego własne repozytorium Git.

### GitHub Actions

Workflow `MVROS v1 Operations` uruchamia wyłącznie stały, syntetyczny fixture z repozytorium. Nie przyjmuje już ścieżki do dowolnych dokumentów. Realne case'y są uruchamiane lokalnie.

### Publikowanie

`scripts/publish.py` wykonuje lokalną walidację snapshotu. Operacje `git commit` i `git push` dla danych case'u są celowo zablokowane.

### Architektura

Warstwa `factory/` pozostaje infrastrukturą wytwarzania i walidacji; nie jest magazynem ani runtime'm prywatnych spraw.
