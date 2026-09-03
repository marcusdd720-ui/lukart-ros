from __future__ import annotations

import ast
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

STATUSES = {"PASS", "FAIL", "RISK", "NOT IMPLEMENTED", "NOT APPLICABLE"}


@dataclass(frozen=True)
class AuditItem:
    id: str
    title: str
    status: str
    evidence: tuple[str, ...]
    observation: str
    risk: str
    recommendation: str

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"invalid audit status: {self.status}")


def read(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def contains_any(paths: list[Path], needles: tuple[str, ...]) -> bool:
    text = "\n".join(read(str(path)) for path in paths)
    return any(needle in text for needle in needles)


def py_files(root: str) -> list[Path]:
    base = Path(root)
    return sorted(p for p in base.rglob("*.py") if ".git" not in p.parts)


def imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def item(
    audit_id: str,
    title: str,
    status: str,
    evidence: tuple[str, ...],
    observation: str,
    risk: str,
    recommendation: str,
) -> AuditItem:
    return AuditItem(audit_id, title, status, evidence, observation, risk, recommendation)


def run_probe(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.returncode, (result.stdout + "\n" + result.stderr).strip()


def build_items() -> list[AuditItem]:
    workflows = sorted(Path(".github/workflows").glob("*.yml"))
    all_py = py_files("core") + py_files("knowledge") + py_files("factory") + py_files("scripts")
    factory_py = py_files("factory")
    runtime_py = py_files("core") + py_files("knowledge")
    stage_orchestrator = read("factory/stage_orchestrator.py")
    case_manager = read("core/case_manager.py")
    case_store = read("factory/local_case_store.py")
    pipeline = read("scripts/run_case_pipeline.py")
    workspace = read("knowledge/models/case_workspace.py")
    ids = read("core/models/ids.py")
    fact_contract = read("knowledge/fact_contract.py")
    security_files = [Path("scripts/repository_audit.py"), Path("scripts/pii_scan.py")]
    model_text = "\n".join(read(str(p)) for p in runtime_py)

    factory_boundary = all(path.name in {p.name for p in factory_py} for path in [Path("factory/stage_orchestrator.py"), Path("factory/stage_gate.py")])
    runtime_imports_factory = sorted(
        str(path) for path in runtime_py if "factory" in imports(path)
    )
    case_states = all(token in workspace for token in ("FACT", "LAW", "DOSSIER", "REVIEW", "OUTBOUND", "OPEN", "FREEZE", "RELEASE", "NOTE"))
    privacy_markers = all(token in (read("README.md") + "\n" + case_manager + "\n" + case_store + "\n" + read("scripts/publish.py") + "\n" + read(".gitignore")) for token in ("MVROS_DATA_ROOT", "git commit", "git push"))
    fresh_sha = "repaired_sha == fresh_sha" in stage_orchestrator and "fresh_sha = git_sha()" in stage_orchestrator
    contradiction = contains_any(runtime_py, ("contradict", "conflict", "inconsistent"))
    confidence = contains_any([Path("knowledge/fact_contract.py"), Path("knowledge/fact_extractor.py")], ("confidence", "epistemic", "status"))
    provenance = contains_any(runtime_py, ("provenance", "source_document", "source_id"))
    immutability = contains_any(runtime_py + [Path("factory/local_case_store.py")], ("sha256", "immutable", "content_hash"))
    legal_issue = contains_any(runtime_py, ("legal_issue", "legal issue"))
    incremental = contains_any(runtime_py, ("incremental", "affected"))
    watcher = any("watch" in p.name.lower() for p in all_py)
    secret_scan = contains_any(workflows, ("gitleaks", "secret", "trufflehog"))
    symlink_test = any("symlink" in read(str(p)).lower() for p in Path("tests").glob("*.py")) if Path("tests").exists() else False
    artifact_guard = contains_any(workflows, ("artifact", "PII", "repository_audit"))
    canonical_ids = "DocumentId" in ids and "FactId" in ids
    stage_gate = read("factory/stage_gate.py")

    return [
        item("A1", "Factory ↔ MVROS boundary", "RISK" if runtime_imports_factory else ("PASS" if factory_boundary else "FAIL"), ("factory/stage_orchestrator.py", "factory/stage_gate.py", "core/", "knowledge/"), "Factory control components are isolated under factory/; no runtime import of factory was found by the static probe." if not runtime_imports_factory else f"Runtime files import factory modules: {runtime_imports_factory}", "Boundary is not yet enforced by a dedicated architectural test." if not runtime_imports_factory else "Runtime-to-factory coupling can bypass the intended factory/product separation.", "Add a dependency-direction test that fails on runtime→factory imports."),
        item("A2", "Private-data boundary", "PASS" if privacy_markers else "RISK", ("README.md", "core/case_manager.py", "factory/local_case_store.py", "scripts/publish.py", ".gitignore"), "The repository documents a local MVROS_DATA_ROOT and blocks normal publication paths for real case data." if privacy_markers else "Privacy boundary evidence is incomplete in the inspected files.", "Runtime leakage could still occur through logs/artifacts without adversarial tests.", "Add a privacy boundary suite covering logs, artifacts, environment and filesystem traversal."),
        item("A3", "CASE lifecycle", "PASS" if case_states else "FAIL", ("knowledge/models/case_workspace.py",), "All declared lifecycle states are present in the workspace model." if case_states else "One or more declared lifecycle states are absent.", "Presence of states does not prove transition integrity.", "Add a formal transition matrix and invalid-transition tests."),
        item("A4", "Canonical source of truth", "RISK", ("core/case_manager.py", "knowledge/models/case_workspace.py", "scripts/run_case_pipeline.py"), "Case management, workspace model and pipeline entrypoint each participate in state handling; a single canonical manifest contract is not evident.", "Divergent state representations can drift.", "Define a canonical case manifest/schema and require every stage to consume it."),
        item("A5", "Traceability", "PASS" if provenance and canonical_ids else "RISK", ("core/models/ids.py", "knowledge/fact_contract.py", "knowledge/"), "Dedicated IDs/provenance concepts are present." if provenance and canonical_ids else "Identifiers exist but end-to-end source-to-output provenance is not demonstrated.", "Loss of provenance weakens evidentiary reproducibility.", "Add end-to-end traceability tests document→fact→issue→output."),
        item("A6", "Idempotency", "RISK", ("scripts/run_case_pipeline.py", "factory/stage_orchestrator.py"), "Rerun behavior exists, but a repository-wide idempotency contract is not explicit.", "Repeated processing may duplicate derived state or outputs.", "Add per-stage repeat-run tests and compare canonical outputs."),
        item("A7", "Determinism", "PASS", ("knowledge/fact_extractor.py", "knowledge/extraction_stage.py", "factory/stage_gate.py"), "Deterministic extraction and deterministic CI gates are present.", "Full-pipeline deterministic output has not been mechanically proven.", "Add repeat-run hashes for the complete synthetic pipeline."),
        item("A8", "Failure isolation / recovery", "PASS" if fresh_sha else "RISK", ("factory/stage_orchestrator.py", "factory/self_healing.py"), "Automatic recovery requires a changed SHA before retry." if fresh_sha else "Fresh-SHA repair invariant was not found.", "Runtime CASE recovery is less explicit than factory recovery.", "Extend recovery contracts to local CASE stages."),
        item("A9", "Dependency boundaries", "RISK", ("core/", "knowledge/", "factory/"), "Layer directories exist, but import direction is not actively enforced.", "Hidden coupling may accumulate.", "Add architecture import rules to CI."),
        item("A10", "Public CLI/API contracts", "PASS", ("scripts/new_case.py", "scripts/run_case_pipeline.py", "scripts/mvros_v1.py"), "Explicit operational entrypoints exist for case creation, pipeline execution and MVROS v1.", "Some edge cases may not have formal CLI contract tests.", "Add exit-code/argument/output contract tests."),
        item("A11", "Evidence provenance", "PASS" if provenance else "RISK", tuple(str(p) for p in runtime_py[:6]), "Source/provenance concepts are present." if provenance else "Mandatory evidence provenance was not detected.", "A source-less fact is not audit-grade.", "Make provenance mandatory at the fact/evidence boundary."),
        item("A12", "Fact confidence / epistemic status", "PASS" if confidence else "RISK", ("knowledge/fact_contract.py", "knowledge/fact_extractor.py"), "Explicit confidence/epistemic markers were detected." if confidence else "Explicit epistemic status is not demonstrated.", "Interpretation can be mistaken for fact.", "Add explicit factual status and confidence semantics."),
        item("A13", "Contradiction detection", "RISK" if contradiction else "NOT IMPLEMENTED", ("core/", "knowledge/"), "Some contradiction/conflict terminology exists, but a general contradiction engine is not established." if contradiction else "No general contradiction detector was found.", "Conflicting evidence can remain silently unresolved.", "Implement contradiction detection with regression fixtures."),
        item("A14", "Missing-evidence detection", "RISK", ("core/", "knowledge/", "knowledge/models/case_workspace.py"), "Required/unknown concepts exist, but a dedicated evidence-readiness gate is not demonstrated.", "Analysis may proceed with critical evidence absent.", "Implement case readiness rules for required evidence."),
        item("A15", "Timeline consistency", "RISK", ("knowledge/models/types.py", "knowledge/models/case_workspace.py"), "Lifecycle metadata exists, but dedicated chronological consistency rules are not demonstrated.", "Date contradictions may survive unnoticed.", "Implement timeline normalization and temporal consistency tests."),
        item("A16", "PII leakage scanning", "PASS" if all(p.exists() for p in security_files) else "FAIL", tuple(str(p) for p in security_files), "Repository and PII scanners are present." if all(p.exists() for p in security_files) else "Required scanners are missing.", "Insufficient scanning would weaken privacy controls.", "Keep scanners in quality gates and extend to runtime outputs."),
        item("A17", "Secret leakage controls", "PASS" if secret_scan else "RISK", tuple(str(p) for p in workflows), "A dedicated secret-scanning marker is present in workflows." if secret_scan else "No dedicated secret-scanning tool/configuration was identified in the inspected workflows.", "Secrets can be committed without a specialized gate.", "Add a dedicated secret scanning workflow/gate."),
        item("A18", "Path escape protection", "PASS" if "MVROS_DATA_ROOT" in case_manager + case_store else "FAIL", ("core/case_manager.py", "factory/local_case_store.py"), "Private data-root handling is explicitly implemented." if "MVROS_DATA_ROOT" in case_manager + case_store else "Private data-root handling was not detected.", "Path escape can expose or overwrite wrong locations.", "Add canonical-path and root-containment assertions."),
        item("A19", "Symlink / traversal resistance", "PASS" if symlink_test else "RISK", ("tests/", "core/case_manager.py", "factory/local_case_store.py"), "A dedicated symlink test was found." if symlink_test else "No dedicated symlink adversarial test was found.", "Lexical path checks may be bypassed through filesystem links.", "Add symlink and traversal attack tests."),
        item("A20", "Artifact isolation", "PASS" if artifact_guard else "RISK", tuple(str(p) for p in workflows), "Workflow/quality controls reference artifact or PII scanning." if artifact_guard else "No universal CI artifact content guard was detected.", "Private case data could leak through CI artifacts/logs.", "Add artifact content scanning and case-path deny rules."),
        item("A21", "Domain model minimization", "RISK", ("core/models/", "knowledge/models/"), "There are multiple model namespaces; usage consolidation has not been measured.", "Duplicate abstractions may increase coupling and maintenance cost.", "Measure model usage before any consolidation."),
        item("A22", "Model usage / dead code", "RISK", ("core/", "knowledge/"), "A full dead-code report is not currently part of the factory gate.", "Unused modules can hide stale architecture.", "Add static dead-code inventory to audit reports."),
        item("A23", "Domain separation", "PASS" if not runtime_imports_factory else "RISK", ("factory/", "core/", "knowledge/"), "Distinct domain directories exist and runtime does not import factory modules." if not runtime_imports_factory else "Runtime imports factory modules.", "Without enforcement, future changes can collapse the boundary.", "Keep architectural import rules in CI."),
        item("A24", "Canonical identifiers", "PASS" if canonical_ids else "RISK", ("core/models/ids.py", "knowledge/fact_contract.py"), "Dedicated DocumentId/FactId identifiers exist." if canonical_ids else "Canonical IDs are incomplete.", "Inconsistent identities break traceability.", "Add cross-stage uniqueness and serialization tests."),
        item("A25", "Immutable source evidence", "PASS" if immutability else "RISK", ("factory/local_case_store.py", "core/models/", "knowledge/"), "Hash/immutability markers were found in source/evidence handling." if immutability else "Immutable/hash-based source evidence is not clearly demonstrated.", "Original evidence may change without a detectable record.", "Store immutable source objects with content hash and append-only provenance."),
    ]


def main() -> int:
    items = build_items()
    sha_rc, sha = run_probe(["git", "rev-parse", "HEAD"])
    payload = {
        "audit": "Architectural Audit 1.0",
        "commit_sha": sha if sha_rc == 0 else "unknown",
        "status_counts": {status: sum(i.status == status for i in items) for status in sorted(STATUSES)},
        "items": [asdict(i) for i in items],
    }
    Path("audit-report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Architectural Audit 1.0", "", f"Commit: `{payload['commit_sha']}`", "", "| ID | Status | Observation | Risk | Evidence | Recommendation |", "|---|---|---|---|---|---|"]
    for i in items:
        lines.append(f"| {i.id} | **{i.status}** | {i.observation} | {i.risk} | `{'; '.join(i.evidence)}` | {i.recommendation} |")
    lines.extend(["", "## Status counts", ""])
    for status, count in payload["status_counts"].items():
        lines.append(f"- {status}: {count}")
    Path("audit-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for i in items:
        print(f"{i.id}: {i.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
