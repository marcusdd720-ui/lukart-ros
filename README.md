# lukart-ros

Projekt Artur 2.0 - System bazowy.

## MVROS v1

MVROS v1.0.0 udostępnia jeden punkt wejścia do uruchomienia produkcyjnego pipeline'u wiedzy:

```bash
python scripts/mvros_v1.py --root <katalog-z-dokumentami>
```

Pipeline wykonuje kolejno budowę grafu, deterministyczną ekstrakcję faktów, walidację kontraktu, deduplikację, projekcję faktów, budowę relacji oraz walidację grafu.

Ten sam proces można uruchomić z GitHub Actions przez workflow `MVROS v1 Operations`, podając katalog źródłowy jako parametr `root`.

Warstwa `factory/` pozostaje infrastrukturą wytwarzania i walidacji; nie jest runtime'em MVROS v1.
