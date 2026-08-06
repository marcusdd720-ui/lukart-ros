# New case checklist (LukArt ROS)

Copy this list for every new matter. One pipeline only — no new export scripts.

## 1. Keys

- [ ] Folder key: `CASES_STYLE_KEY` (e.g. `II_Kp_459_26`, `DS_3960_2025`)
- [ ] Graph case id: `case:…`
- [ ] Court / prosecutor signature in `Case.signature` / metadata

## 2. Files to create

- [ ] `scripts/build_case_<KEY>.py` — `def build_case() -> Case`
- [ ] `scripts/link_case_<KEY>.py` — `def link_<…>() -> tuple[KnowledgeGraph, str]`
- [ ] `open_<key>()` in `knowledge/models/case_workspace.py`
- [ ] `CaseSpec(...)` in `knowledge/models/case_registry.py`

## 3. Do not create

- [ ] ~~export_*.py~~
- [ ] ~~run_<case>_pipeline.py~~
- [ ] second copy of FactAgent / LawAgent

## 4. Verify

```powershell
python scripts/build_case_<KEY>.py
python scripts/link_case_<KEY>.py
python scripts/run_case_pipeline.py --list
python scripts/run_case_pipeline.py --case <KEY> --stage FACT
python scripts/run_case_pipeline.py --case <KEY> --stage LAW
python scripts/run_case_pipeline.py --case <KEY>
python scripts/publish.py --case <KEY> --prefer freeze --dry-run
python -m pytest tests/test_case_platform.py -q