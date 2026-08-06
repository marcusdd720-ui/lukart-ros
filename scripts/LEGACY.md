# Legacy scripts (do not extend)

These scripts predate CaseWorkspace and duplicate the case pipeline.
They remain only for historical runs / comparison.

## Do not use for new work

| Script | Replaced by |
|--------|-------------|
| `export_case_authorities.py` | `CaseWorkspace.build_authorities()` + LegalQuery |
| `export_authorities_docx.py` | Workspace dossier / authorities via `run()` |
| `export_dossier_with_authorities.py` | `CaseWorkspace.run()` / `run(stage="DOSSIER")` |
| `export_dossier_with_authorities_docx.py` | `CaseWorkspace.export_dossier_docx()` |

## Canonical path (current)

```text
CaseSpec (case_registry)
    → CaseWorkspace.open / run / run(stage=…)
    → outbound + CaseSnapshot (OPEN → FREEZE → RELEASE)
    → publish.py --prefer freeze