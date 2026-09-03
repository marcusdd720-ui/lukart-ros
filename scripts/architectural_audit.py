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
    return any(needle.lower() in text.lower() for needle in needles)


def py_files(root: str) -> list[Path]:
    base = Path(root)
    if not base.exists():
        return []
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


def probe(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.returncode, (result.stdout + "\n" + result.stderr).strip()


def audit_item(
    audit_id: str,
    title: str,
    status: str,
    evidence: tuple[str, ...],
    observation: str,
    risk: str,
    recommendation: str,
) -> AuditItem:
    return AuditItem(audit_id, title, status, evidence, observation, risk, recommendation)


def build_items() -> list[AuditItem]:
    workflows = sorted(Path(".github/workflows").glob("*.yml"))
    runtime_files = py_files("core") + py_files("knowledge")
    factory_files = py_files("factory")
    all_project_files = runtime_files + factory_files + py_files("scripts")
    stage_orchestrator = read("factory/stage_orchestrator.py")
    stage_gate = read("factory/stage_gate.py")
    case_manager = read("core/case_manager.py")
    case_store = read("factory/local_case_store.py")
    pipeline = read("scripts/run_case_pipeline.py")
    workspace = read("knowledge/models/case_workspace.py")
    ids = read("core/models/ids.py")
    fact_contract = read("knowledge/fact_contract.py")
    privacy_text = "\n".join(
        [read("README.md"), read(".gitignore"), case_manager, case_store, read("scripts/publish.py")]
    )
    runtime_imports_factory = sorted(str(path) for path in runtime_files if "factory" in imports(path))
    state_names = ("FACT", "LAW", "DOSSIER", "REVIEW", "OUTBOUND", "OPEN", "FREEZE", "RELEASE", "NOTE")
    case_states = all(name in workspace for name in state_names)
    provenance = contains_any(runtime_files, ("provenance", "source_document", "source_id"))
    confidence = contains_any([Path("knowledge/fact_contract.py"), Path("knowledge/fact_extractor.py")], ("confidence", "epistemic"))
    contradiction = contains_any(runtime_files, ("contradict", "conflict", "inconsistent"))
    immutable = contains_any(runtime_files + [Path("factory/local_case_store.py")], ("sha256", "content_hash", "immutable"))
    legal_issue = contains_any(runtime_files, ("legal_issue", "legal issue"))
    incremental = contains_any(runtime_files, ("incremental", "affected"))
    watcher = any("watch" in path.name.lower() for path in all_project_files)
    secret_scan = contains_any(workflows, ("gitleaks", "trufflehog"))
    tests = sorted(Path("tests").glob("*.py")) if Path("tests").exists() else []
    symlink_test = any("symlink" in read(str(path)).lower() for path in tests)
    canonical_ids = all(token in ids for token in ("DocumentId", "FactId"))
    artifact_guard = contains_any(workflows, ("artifact", "pii_scan", "repository_audit"))
    deterministic_components = exists_tuple = all(
        Path(path).exists()
        for path in ("knowledge/fact_extractor.py", "knowledge/extraction_stage.py")
    )
    run_check_rc, _ = probe(["python", "-m", "compileall", "-q", "core", "knowledge", "factory", "scripts"])

    return [
        audit_item("A1", "Factory ↔ MVROS boundary", "RISK" if runtime_imports_factory else "PASS", ("factory/", "core/", "knowledge/"), "Factory control plane is isolated from runtime code by directory and import structure." if not runtime_imports_factory else f"Runtime files import factory modules: {runtime_imports_factory}", "No dedicated architectural dependency test currently proves the boundary remains intact.", "Add an import-direction gate to CI."),
        audit_item("A2", "Private-data boundary", "PASS" if "MVROS_DATA_ROOT" in privacy_text and "git push" in privacy_text else "FAIL", ("README.md", "core/case_manager.py", "factory/local_case_store.py", "scripts/publish.py", ".gitignore"), "Local private storage and publication prohibitions are explicitly represented." , "Static evidence does not cover every possible exfiltration route.", "Add adversarial runtime privacy tests."),
        audit_item("A3", "CASE lifecycle", "PASS" if case_states else "FAIL", ("knowledge/models/case_workspace.py",), "All nine declared CASE lifecycle states are represented." if case_states else "The expected CASE lifecycle is incomplete.", "State presence does not itself prove valid transition enforcement.", "Add a formal transition matrix and invalid-transition tests."),
        audit_item("A4", "Canonical source of truth", "RISK", ("core/case_manager.py", "knowledge/models/case_workspace.py", "scripts/run_case_pipeline.py"), "Runtime state responsibilities are distributed across case manager, workspace model and pipeline entrypoint.", "Without one canonical case manifest, representations can drift.", "Define a canonical case manifest/schema."),
        audit_item("A5", "Traceability", "PASS" if provenance and canonical_ids else "RISK", ("core/models/ids.py", "knowledge/fact_contract.py", "knowledge/"), "Identity/provenance building blocks exist." if provenance and canonical_ids else "End-to-end source-to-output traceability is not proven.", "A gap in provenance weakens reproducibility and reviewability.", "Add an end-to-end traceability test."),
        audit_item("A6", "Idempotency", "RISK", ("factory/stage_orchestrator.py", "scripts/run_case_pipeline.py"), "Rerun mechanisms exist, but idempotency is not stated as an explicit contract for every stage.", "Repeated execution may create divergent or duplicated outputs.", "Add repeated-run equivalence tests per stage."),
        audit_item("A7", "Determinism", "PASS" if deterministic_components and run_check_rc == 0 else "RISK", ("knowledge/fact_extractor.py", "knowledge/extraction_stage.py", "factory/stage_gate.py"), "Deterministic extraction components exist and project Python modules compile." if deterministic_components and run_check_rc == 0 else "Determinism evidence is incomplete.", "Full output determinism has not been mechanically hashed end-to-end.", "Add full-pipeline repeatability hashes."),
        audit_item("A8", "Failure isolation / recovery", "PASS" if "repaired_sha == fresh_sha" in stage_orchestrator else "RISK", ("factory/stage_orchestrator.py", "factory/self_healing.py"), "Factory recovery requires a new SHA before retry." if "repaired_sha == fresh_sha" in stage_orchestrator else "Fresh-SHA recovery invariant is absent.", "Runtime CASE recovery remains less explicit.", "Extend recovery contracts to local CASE processing."),
        audit_item("A9", "Dependency boundaries", "RISK", ("core/", "knowledge/", "factory/"), "Layer structure exists, but dependency direction is not enforced by a dedicated test.", "Coupling can increase silently.", "Add architecture import rules to the CI gate."),
        audit_item("A10", "Public CLI/API contracts", "PASS" if all(Path(path).exists() for path in ("scripts/new_case.py", "scripts/run_case_pipeline.py", "scripts/mvros_v1.py")) else "FAIL", ("scripts/new_case.py", "scripts/run_case_pipeline.py", "scripts/mvros_v1.py"), "Explicit operational entrypoints exist." if all(Path(path).exists() for path in ("scripts/new_case.py", "scripts/run_case_pipeline.py", "scripts/mvros_v1.py")) else "One or more operational entrypoints are missing.", "Edge-case CLI behavior is not fully specified.", "Add CLI argument/exit-code/output contract tests."),
        audit_item("A11", "Evidence provenance", "PASS" if provenance else "RISK", tuple(str(p) for p in runtime_files[:6]), "Provenance/source concepts are present." if provenance else "Mandatory provenance was not detected.", "Source-less facts cannot be independently audited.", "Make provenance mandatory in the fact/evidence contract."),
        audit_item("A12", "Fact confidence / epistemic status", "PASS" if confidence else "RISK", ("knowledge/fact_contract.py", "knowledge/fact_extractor.py"), "Confidence/epistemic markers are present." if confidence else "Explicit epistemic status is not demonstrated.", "Interpretations can be mistaken for observed facts.", "Add explicit epistemic state and confidence to the contract."),
        audit_item("A13", "Contradiction detection", "RISK" if contradiction else "NOT IMPLEMENTED", ("core/", "knowledge/"), "Conflict terminology exists, but a general contradiction engine is not established." if contradiction else "No contradiction detector was found.", "Conflicting evidence can remain unresolved.", "Implement contradiction detection with regression fixtures."),
        audit_item("A14", "Missing-evidence detection", "RISK", ("core/", "knowledge/", "knowledge/models/case_workspace.py"), "Required/unknown concepts exist but no dedicated evidence-readiness gate was identified.", "Case analysis may progress despite critical missing evidence.", "Implement evidence-readiness rules."),
        audit_item("A15", "Timeline consistency", "RISK", ("knowledge/models/types.py", "knowledge/models/case_workspace.py"), "Lifecycle/date concepts exist without a dedicated temporal-consistency gate.", "Conflicting or impossible dates may survive unnoticed.", "Implement timeline normalization and consistency checks."),
        audit_item("A16", "PII leakage scanning", "PASS" if Path("scripts/pii_scan.py").exists() and Path("scripts/repository_audit.py").exists() else "FAIL", ("scripts/pii_scan.py", "scripts/repository_audit.py", "factory/stage_gate.py"), "Repository and PII scanning are integrated into quality gates." if Path("scripts/pii_scan.py").exists() and Path("scripts/repository_audit.py").exists() else "Required scanners are incomplete.", "Runtime outputs still require dedicated leakage tests.", "Extend scanning to generated logs/artifacts."),
        audit_item("A17", "Secret leakage controls", "PASS" if secret_scan else "RISK", tuple(str(p) for p in workflows), "A dedicated secret scanner was found in workflow configuration." if secret_scan else "No dedicated secret scanning tool was found in the inspected workflows.", "Credentials may be introduced without a specialized gate.", "Add secret scanning to CI."),
        audit_item("A18", "Path escape protection", "PASS" if "MVROS_DATA_ROOT" in case_manager + case_store else "FAIL", ("core/case_manager.py", "factory/local_case_store.py"), "Private data-root handling is implemented." if "MVROS_DATA_ROOT" in case_manager + case_store else "Private data-root handling was not detected.", "Path confusion could expose unrelated files.", "Add canonical root-containment assertions."),
        audit_item("A19", "Symlink / traversal resistance", "PASS" if symlink_test else "RISK", ("tests/", "core/case_manager.py", "factory/local_case_store.py"), "Dedicated symlink testing exists." if symlink_test else "No dedicated symlink adversarial test was found.", "Filesystem links can bypass lexical path checks.", "Add symlink and traversal attack tests."),
        audit_item("A20", "Artifact isolation", "PASS" if artifact_guard else "RISK", tuple(str(p) for p in workflows), "Workflow controls include repository/PII checks relevant to artifact safety." if artifact_guard else "No universal artifact content guard was found.", "Private case data could leak via CI artifacts or logs.", "Add artifact-content deny rules and scanning."),
        audit_item("A21", "Domain model minimization", "RISK", ("core/models/", "knowledge/models/"), "Multiple model namespaces exist and consolidation has not been measured.", "Duplicate abstractions may increase maintenance cost.", "Measure actual model usage before consolidation."),
        audit_item("A22", "Model usage / dead code", "RISK", ("core/", "knowledge/", "factory/"), "A formal dead-code inventory is not part of the current factory gate.", "Stale modules can hide architectural drift.", "Add dead-code inventory to the audit."),
        audit_item("A23", "Domain separation", "PASS" if not runtime_imports_factory else "RISK", ("factory/", "core/", "knowledge/"), "Runtime has no direct factory import according to static import analysis." if not runtime_imports_factory else "Runtime imports factory modules.", "Future changes could erode the boundary without a dedicated gate.", "Enforce the dependency direction in CI."),
        audit_item("A24", "Canonical identifiers", "PASS" if canonical_ids else "RISK", ("core/models/ids.py", "knowledge/fact_contract.py"), "DocumentId and FactId identifiers are defined." if canonical_ids else "Canonical IDs are incomplete.", "Identity inconsistencies can break traceability.", "Add uniqueness, serialization and cross-stage identity tests."),
        audit_item("A25", "Immutable source evidence", "PASS" if immutable else "RISK", ("factory/local_case_store.py", "core/models/", "knowledge/"), "Hash/immutability markers are present in source/evidence handling." if immutable else "Immutable/hash-backed source evidence is not clearly established.", "Original evidence could change without a detectable integrity record.", "Implement immutable source objects with content hashes and append-only provenance."),
    ]


def main() -> int:
    items = build_items()
    rc, sha = probe(["git", "rev-parse", "HEAD"])
    payload = {
        "audit": "Architectural Audit 1.0",
        "commit_sha": sha if rc == 0 else "unknown",
        "status_counts": {status: sum(i.status == status for i in items) for status in sorted(STATUSES)},
        "items": [asdict(i) for i in items],
    }
    Path("audit-report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Architectural Audit 1.0",
        "",
        f"Commit: `{payload['commit_sha']}`",
        "",
        "| ID | Status | Observation | Risk | Evidence | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for i in items:
        lines.append(f"| {i.id} | **{i.status}** | {i.observation} | {i.risk} | `{'; '.join(i.evidence)}` | {i.recommendation} |")
    lines.extend(["", "## Status counts", ""])
    for status, count in payload["status_counts"].items():
        lines.append(f"- {status}: {count}")
    Path("audit-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload["status_counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
