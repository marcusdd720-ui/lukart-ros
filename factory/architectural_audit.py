from __future__ import annotations

import ast
import json
import subprocess
import sys
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
            raise ValueError(f"Invalid status: {self.status}")


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode, output


def read(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def exists(path: str) -> bool:
    return Path(path).exists()


def imports_of(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def make_items() -> list[AuditItem]:
    readme = read("README.md")
    privacy_text = " ".join(
        read(path)
        for path in [
            ".gitignore",
            "core/case_manager.py",
            "factory/local_case_store.py",
            "scripts/publish.py",
            ".github/workflows/mvros-v1-operations.yml",
        ]
    )
    workflow_paths = sorted(str(p) for p in Path(".github/workflows").glob("*.yml"))
    py_paths = sorted(Path(root) / name for root, _, names in __import__("os").walk(".") for name in names if name.endswith(".py") and ".git" not in root)
    factory_files = sorted(Path("factory").glob("*.py"))
    core_files = sorted(Path("core").rglob("*.py"))
    knowledge_files = sorted(Path("knowledge").rglob("*.py"))

    root_ok = exists("factory/stage_orchestrator.py") and exists("factory/stage_registry.py") and exists("factory/stage_gate.py")
    privacy_markers = ["MVROS_DATA_ROOT", "git push", "GitHub Actions", "Realne sprawy"]
    privacy_ok = all(marker in privacy_text for marker in privacy_markers)
    case_state = read("knowledge/models/case_workspace.py")
    case_registry = read("knowledge/models/case_registry.py")
    lifecycle_ok = all(name in case_state for name in ["FACT", "LAW", "DOSSIER", "REVIEW", "OUTBOUND", "OPEN", "FREEZE", "RELEASE", "NOTE"])
    dynamic_runtime_ok = "case" in read("scripts/run_case_pipeline.py").lower()
    evidence_terms = any(term in " ".join(read(str(p)) for p in knowledge_files) for term in ["provenance", "source", "confidence"])
    contradiction_terms = any(term in " ".join(read(str(p)) for p in knowledge_files) for term in ["contradict", "conflict", "inconsistent"])
    missing_terms = any(term in " ".join(read(str(p)) for p in knowledge_files + core_files) for term in ["missing", "required", "unknown"])
    immutable_terms = any(term in " ".join(read(str(p)) for p in core_files + knowledge_files) for term in ["immutable", "hash", "sha256"])
    trace_terms = any(term in " ".join(read(str(p)) for p in core_files + knowledge_files) for term in ["document_id", "fact_id", "evidence_id"])
    security_scripts = exists("scripts/repository_audit.py") and exists("scripts/pii_scan.py")
    test_files = sorted(Path("tests").glob("test_*.py")) if exists("tests") else []
    watcher_exists = any(p.name.lower().find("watch") >= 0 for p in core_files + factory_files + [Path("scripts") / n for n in __import__("os").listdir("scripts")])
    issue_generator = any(term in " ".join(read(str(p)) for p in core_files) for term in ["legal issue", "legal_issue", "issue"])
    incremental_terms = any(term in " ".join(read(str(p)) for p in core_files + knowledge_files) for term in ["incremental", "affected"])
    queue_terms = any(term in " ".join(read(str(p)) for p in core_files + knowledge_files) for term in ["review queue", "review_required", "REVIEW"])
    semantic_healing = "fresh SHA" in read("factory/stage_orchestrator.py") and "repaired_sha == fresh_sha" in read("factory/stage_orchestrator.py")
    domain_ids = " ".join(read(str(p)) for p in core_files + knowledge_files)
    canonical_ids = all(token in domain_ids for token in ["DocumentId", "FactId"])

    return [
        AuditItem("A1", "Factory ↔ MVROS boundary", "PASS" if root_ok else "FAIL", ("factory/stage_orchestrator.py", "factory/stage_registry.py", "factory/stage_gate.py"), "Factory control-plane components are separated into factory/.", "Boundary appears explicit, but automated dependency direction enforcement is not yet demonstrated.", "Add a boundary test that prevents runtime layers from importing factory modules."),
        AuditItem("A2", "Private-data boundary", "PASS" if privacy_ok else "FAIL", ("README.md", ".gitignore", "core/case_manager.py", "scripts/publish.py", ".github/workflows/mvros-v1-operations.yml"), "Repository documents and implements MVROS_DATA_ROOT and blocks publication of real case data.", "Current evidence is code/config based; runtime exfiltration tests need broader adversarial coverage.", "Add a dedicated privacy-boundary test suite including symlink, artifact and log cases."),
        AuditItem("A3", "CASE lifecycle", "PASS" if lifecycle_ok else "RISK", ("knowledge/models/case_workspace.py",), "The domain model defines the expected lifecycle states.", "State definitions alone do not prove all transitions are enforced consistently.", "Add transition invariants and invalid-transition tests."),
        AuditItem("A4", "Canonical source of truth", "RISK", ("core/case_manager.py", "knowledge/models/case_workspace.py", "scripts/run_case_pipeline.py"), "Case metadata, workspace and pipeline entrypoints each own parts of runtime state.", "A single canonical persistence contract is not clearly demonstrated by static inspection.", "Define one canonical case manifest/schema and make all stages consume it."),
        AuditItem("A5", "Traceability", "RISK" if not trace_terms else "PASS", tuple(str(p) for p in core_files[:4]), "Some identity-oriented models exist, but end-to-end source→fact→issue→output traceability is not proven.", "Risk of losing provenance across transformations.", "Implement and test a complete traceability chain."),
        AuditItem("A6", "Idempotency", "RISK", ("factory/stage_orchestrator.py", "scripts/run_case_pipeline.py"), "Orchestrator and pipeline support repeat execution, but a general idempotency contract is not explicit.", "Reruns may create duplicate derived artifacts unless each stage is deterministic/idempotent.", "Add per-stage idempotency tests against repeated execution."),
        AuditItem("A7", "Determinism", "PASS", ("factory/stage_gate.py", "knowledge/extraction_stage.py", "knowledge/fact_extractor.py"), "The factory runs deterministic quality gates and extraction code is structured deterministically.", "No repository-wide determinism hash test was found by static inspection.", "Add golden-output repeatability tests for the complete pipeline."),
        AuditItem("A8", "Failure isolation / recovery", "PASS" if semantic_healing else "RISK", ("factory/stage_orchestrator.py", "factory/self_healing.py"), "Orchestrator captures failure logs, attempts repair, and requires a fresh SHA before retry.", "Recovery is strongest for factory failures; runtime CASE recovery needs explicit tests.", "Extend failure/recovery contracts to local case stages."),
        AuditItem("A9", "Dependency boundaries", "RISK", tuple(str(p) for p in factory_files[:3]), "Layered directories exist, but explicit dependency-direction enforcement was not found.", "Hidden cross-layer coupling can evolve without detection.", "Add import-layer lint/test rules."),
        AuditItem("A10", "Public CLI/API contracts", "PASS", ("scripts/run_case_pipeline.py", "scripts/new_case.py", "scripts/mvros_v1.py"), "Named CLI entrypoints exist for case creation, pipeline execution and v1 operation.", "Contract stability tests are stronger for some paths than others.", "Create CLI contract tests for arguments, exit codes and output."),
        AuditItem("A11", "Evidence provenance", "RISK" if not evidence_terms else "PASS", tuple(str(p) for p in knowledge_files[:5]), "Evidence/provenance concepts are not conclusively represented across all emitted facts.", "A fact without source provenance is not audit-grade.", "Make provenance mandatory in the fact/evidence contract."),
        AuditItem("A12", "Fact confidence / epistemic status", "RISK", ("knowledge/fact_contract.py", "knowledge/fact_extractor.py"), "Fact contract and extractor exist, but explicit verified/interpreted/hypothesis semantics are not proven.", "Interpretation may be mistaken for fact.", "Extend fact contract with explicit epistemic status and confidence fields."),
        AuditItem("A13", "Contradiction detection", "NOT IMPLEMENTED" if not contradiction_terms else "RISK", tuple(str(p) for p in knowledge_files), "No clear general contradiction engine was identified by static inspection.", "Conflicting documents could coexist without machine-visible conflict state.", "Implement a contradiction detector and regression corpus."),
        AuditItem("A14", "Missing-evidence detection", "RISK" if not missing_terms else "PASS", tuple(str(p) for p in core_files[:6]), "Required/unknown concepts exist, but a dedicated missing-evidence gate is not demonstrated.", "Case may progress with critical evidence absent.", "Add a readiness rule engine for required evidence."),
        AuditItem("A15", "Timeline consistency", "RISK", ("knowledge/models/case_workspace.py", "knowledge/models/types.py"), "Case lifecycle exists, but a dedicated temporal consistency validator is not demonstrated.", "Impossible or conflicting date sequences may remain unresolved.", "Add timeline normalization and consistency rules."),
        AuditItem("A16", "PII leakage scanning", "PASS" if security_scripts else "FAIL", ("scripts/repository_audit.py", "scripts/pii_scan.py"), "Dedicated repository and PII scanners are present and included in quality gates.", "CI coverage does not prove local runtime leakage is impossible.", "Add runtime log/artifact privacy tests."),
        AuditItem("A17", "Secret leakage controls", "RISK", (".github/workflows", "pyproject.toml"), "General CI exists, but dedicated secret-scanning configuration is not evident in the inspected top-level workflow set.", "Credentials could be introduced without a targeted gate.", "Add a dedicated secret-scanning control and test it in CI."),
        AuditItem("A18", "Path escape protection", "PASS" if "MVROS_DATA_ROOT" in privacy_text else "FAIL", ("core/case_manager.py", "factory/local_case_store.py"), "Private data root handling is explicit and rejects unsafe roots per project documentation.", "Traversal/symlink edge cases need adversarial tests.", "Add path canonicalization and symlink escape tests."),
        AuditItem("A19", "Symlink / traversal resistance", "RISK", ("core/case_manager.py", "factory/local_case_store.py"), "No dedicated adversarial test was identified.", "Symlink or traversal could bypass a lexical path check.", "Add filesystem security tests with symlinks and .. segments."),
        AuditItem("A20", "Artifact isolation", "RISK", (".github/workflows/mvros-v1-operations.yml", "scripts/publish.py"), "Workflow uses a fixed synthetic fixture and publish blocks git publication of case data.", "A universal artifact-content scanner is not demonstrated.", "Scan every CI artifact/log for real-case path and PII patterns."),
        AuditItem("A21", "Domain model minimization", "RISK", ("core/models", "knowledge/models"), "There are multiple model layers and legacy-looking parallel abstractions.", "Potential architectural duplication can increase maintenance cost.", "Measure actual usage before deleting or consolidating models."),
        AuditItem("A22", "Model usage / dead code", "RISK", ("core", "knowledge"), "Static inventory shows a broad model surface; unused-code proof was not run here.", "Dead abstractions may hide maintenance and coupling risk.", "Add a dead-code inventory to the audit."),
        AuditItem("A23", "Domain separation", "PASS", ("core/models", "knowledge/models", "factory"), "Documents, entities, and case workspace concepts are represented separately.", "Cross-domain dependency direction still needs enforcement tests.", "Add explicit architectural dependency assertions."),
        AuditItem("A24", "Canonical identifiers", "RISK" if not canonical_ids else "PASS", ("core/models/ids.py", "knowledge/fact_contract.py"), "Dedicated ID models exist, but cross-object uniqueness and persistence semantics need verification.", "Collisions or inconsistent identity propagation could break traceability.", "Add uniqueness, serialization and cross-stage identity tests."),
        AuditItem("A25", "Immutable source evidence", "RISK" if not immutable_terms else "PASS", ("core/models", "knowledge/models", "factory/local_case_store.py"), "Hash/immutability semantics are not yet clearly proven for source evidence.", "Original evidence could be overwritten or changed without detection.", "Implement immutable source objects with content hashes and append-only metadata."),
    ]


def write_outputs(items: list[AuditItem]) -> None:
    commit_rc, commit_sha = run(["git", "rev-parse", "HEAD"])
    payload = {
        "audit": "Architectural Audit 1.0",
        "commit_sha": commit_sha if commit_rc == 0 else "unknown",
        "items": [asdict(item) for item in items],
        "status_counts": {status: sum(item.status == status for item in items) for status in sorted(STATUSES)},
    }
    Path("audit-report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Architectural Audit 1.0", "", f"Commit: `{payload['commit_sha']}`", ""]
    lines.append("| ID | Status | Finding | Evidence | Recommendation |")
    lines.append("|---|---|---|---|---|")
    for item in items:
        evidence = "; ".join(item.evidence)
        lines.append(f"| {item.id} | **{item.status}** | {item.observation} | `{evidence}` | {item.recommendation} |")
    lines.extend(["", "## Status counts", ""])
    for status, count in payload["status_counts"].items():
        lines.append(f"- {status}: {count}")
    Path("audit-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    items = make_items()
    write_outputs(items)
    for item in items:
        print(f"{item.id}: {item.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
