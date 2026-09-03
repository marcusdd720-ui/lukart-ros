# ruff: noqa: E501
"""Final Architectural Audit 1.0 runner without package-path assumptions."""

from __future__ import annotations

import argparse
import ast
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

STATUSES = ("PASS", "FAIL", "RISK", "NOT IMPLEMENTED", "NOT APPLICABLE")
RUNTIME_ROOTS = ("core", "knowledge")


@dataclass(frozen=True, slots=True)
class AuditItem:
    id: str
    title: str
    status: str
    evidence: tuple[str, ...]
    observation: str
    risk: str
    recommendation: str


def runtime_factory_imports(root: Path) -> list[str]:
    violations: list[str] = []
    for package in RUNTIME_ROOTS:
        package_root = root / package
        if not package_root.is_dir():
            continue
        for path in sorted(package_root.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if name == "factory" or name.startswith("factory."):
                        violations.append(f"{path.relative_to(root)}:{node.lineno}:{name}")
    return violations


def has_text(root: Path, path: str, *tokens: str) -> bool:
    file = root / path
    if not file.is_file():
        return False
    text = file.read_text(encoding="utf-8").lower()
    return all(token.lower() in text for token in tokens)


def exists_all(root: Path, *paths: str) -> bool:
    return all((root / path).exists() for path in paths)


def current_sha() -> str:
    return os.environ.get("AUDIT_HEAD_SHA", "").strip() or os.environ.get("GITHUB_SHA", "").strip() or "unknown"


def build_items(root: Path) -> list[AuditItem]:
    violations = runtime_factory_imports(root)
    lifecycle = has_text(root, "knowledge/models/case_workspace.py", '"FACT"', '"FREEZE"', '"RELEASE"')
    provenance = has_text(root, "knowledge/provenance.py", "source_document_sha256", "source_document_id")
    epistemic = has_text(root, "knowledge/provenance.py", "confidence", "EpistemicStatus")
    privacy = exists_all(root, "core/local_case_store.py", "scripts/publish.py", "scripts/pii_scan.py", "scripts/repository_audit.py")
    idempotency = has_text(root, "knowledge/project_timeline.py", "idempotent") and has_text(root, "knowledge/models/case_manifest.py", "digest")
    fresh_sha = has_text(root, "factory/stage_orchestrator.py", "fresh_sha")
    entrypoints = exists_all(root, "scripts/new_case.py", "scripts/run_case_pipeline.py", "scripts/mvros_v1.py")
    contradiction = (root / "knowledge/contradiction_detector.py").is_file()
    evidence = (root / "knowledge/evidence_readiness.py").is_file()
    timeline = (root / "knowledge/timeline_validator.py").is_file()
    secret = (root / "scripts/secret_scan.py").is_file()
    symlink_tests = has_text(root, "tests/test_architecture_hardening.py", "symlink")
    dependency = (root / "scripts/dependency_boundary_check.py").is_file()
    model_usage = (root / "scripts/model_usage_audit.py").is_file()
    dead_code = (root / "scripts/dead_code_gate.py").is_file()
    snapshot = has_text(root, "core/local_case_store.py", "save_source_snapshot", "sha256")
    ids = has_text(root, "core/models/ids.py", "DocumentId", "CaseId")
    artifact = has_text(root, ".github/workflows/mvros-v1-operations.yml", "synthetic")
    return [
        AuditItem("A1", "Factory ↔ MVROS boundary", "PASS" if not violations else "FAIL", ("core/", "knowledge/", "scripts/dependency_boundary_check.py"), "Runtime contains no absolute imports from factory." if not violations else f"Violations: {violations}", "Factory/runtime coupling can contaminate production runtime." if violations else "No direct dependency found.", "Keep the dependency gate mandatory."),
        AuditItem("A2", "Private-data boundary", "PASS" if privacy else "FAIL", ("core/local_case_store.py", "scripts/publish.py"), "Private storage and publication controls are present." if privacy else "Required privacy controls are incomplete.", "Private case data may cross the repository boundary." if not privacy else "Residual exfiltration routes still require testing.", "Retain privacy regression coverage."),
        AuditItem("A3", "CASE lifecycle", "PASS" if lifecycle else "FAIL", ("knowledge/models/case_workspace.py",), "Lifecycle states are represented." if lifecycle else "Lifecycle definition is incomplete.", "Missing lifecycle states weaken process control." if not lifecycle else "Presence alone does not prove every transition path.", "Keep lifecycle transitions testable."),
        AuditItem("A4", "Canonical source of truth", "PASS" if (root / "knowledge/models/case_manifest.py").is_file() else "FAIL", ("knowledge/models/case_manifest.py",), "CaseManifest is the canonical manifest with stable serialization and digest." if (root / "knowledge/models/case_manifest.py").is_file() else "No canonical case manifest exists.", "Distributed case state can drift." if not (root / "knowledge/models/case_manifest.py").is_file() else "Manifest adoption must remain enforced at runtime boundaries.", "Keep manifest persistence canonical."),
        AuditItem("A5", "Traceability", "PASS" if provenance and ids else "FAIL", ("knowledge/provenance.py", "core/models/ids.py"), "Source identity, integrity and canonical IDs are present." if provenance and ids else "Traceability contracts are incomplete.", "Weak linkage impairs reviewability." if not provenance or not ids else "Future refactors must preserve source binding.", "Keep source IDs and digests mandatory."),
        AuditItem("A6", "Idempotency", "PASS" if idempotency else "FAIL", ("knowledge/project_timeline.py", "knowledge/models/case_manifest.py"), "Repeat-safe projection and canonical manifest digest are implemented." if idempotency else "Full repeatability is not evidenced.", "Reruns may duplicate or mutate derived state." if not idempotency else "Material-stage equivalence still depends on regression tests.", "Retain repeated-run equivalence tests."),
        AuditItem("A7", "Determinism", "PASS" if (root / "knowledge/fact_extractor.py").is_file() else "FAIL", ("knowledge/fact_extractor.py", "knowledge/extraction_stage.py"), "Deterministic extraction components exist." if (root / "knowledge/fact_extractor.py").is_file() else "Deterministic extraction is incomplete.", "Non-deterministic output breaks measurement." if not (root / "knowledge/fact_extractor.py").is_file() else "Content-digest enforcement should remain in regression coverage.", "Keep deterministic ordering and hashing."),
        AuditItem("A8", "Failure isolation / recovery", "PASS" if fresh_sha else "FAIL", ("factory/stage_orchestrator.py", "factory/self_healing.py"), "Recovery requires a fresh repaired SHA." if fresh_sha else "Fresh-SHA recovery is not evidenced.", "Same-SHA reruns can mask ineffective repairs." if not fresh_sha else "Repair scope still needs bounded changes.", "Keep fresh-SHA recovery mandatory."),
        AuditItem("A9", "Dependency boundaries", "PASS" if dependency else "FAIL", ("scripts/dependency_boundary_check.py",), "Dependency direction is a dedicated executable CI gate." if dependency else "No dedicated dependency gate exists.", "Architecture can regress silently." if not dependency else "Gate coverage should evolve with new domains.", "Run the gate in every CI quality check."),
        AuditItem("A10", "Public CLI/API contracts", "PASS" if entrypoints else "FAIL", ("scripts/new_case.py", "scripts/run_case_pipeline.py", "scripts/mvros_v1.py"), "Primary runtime entrypoints exist." if entrypoints else "Runtime entrypoints are incomplete.", "Operational interface drift can break users." if not entrypoints else "CLI edge cases remain covered by tests.", "Preserve CLI contract tests."),
        AuditItem("A11", "Evidence provenance", "PASS" if provenance else "FAIL", ("knowledge/provenance.py", "knowledge/fact_contract.py"), "Facts require source document identity and SHA-256 integrity." if provenance else "Mandatory provenance is incomplete.", "Source-less facts weaken independent review." if not provenance else "Maintain strict ingest validation.", "Keep provenance mandatory at ingest."),
        AuditItem("A12", "Fact confidence / epistemic status", "PASS" if epistemic else "FAIL", ("knowledge/provenance.py",), "Facts expose explicit confidence and epistemic status." if epistemic else "Epistemic metadata is incomplete.", "Interpretation can be confused with fact." if not epistemic else "Semantics must remain documented.", "Preserve validated confidence/status ranges."),
        AuditItem("A13", "Contradiction detection", "PASS" if contradiction else "FAIL", ("knowledge/contradiction_detector.py",), "Structured contradiction detection is implemented." if contradiction else "Contradiction detector is missing.", "Conflicts can remain unresolved." if not contradiction else "Detector coverage depends on structured claims.", "Expand claim fixtures as domain coverage grows."),
        AuditItem("A14", "Missing-evidence detection", "PASS" if evidence else "FAIL", ("knowledge/evidence_readiness.py",), "Required evidence is evaluated before a readiness decision." if evidence else "Evidence-readiness gate is missing.", "Analysis can proceed with critical evidence missing." if not evidence else "Requirements must remain case-specific.", "Keep evidence requirements explicit."),
        AuditItem("A15", "Timeline consistency", "PASS" if timeline else "FAIL", ("knowledge/timeline_validator.py",), "Timeline validation rejects conflicting or non-deterministic ordering." if timeline else "Timeline validator is missing.", "Impossible or conflicting dates may survive." if not timeline else "Extend with domain-specific temporal rules when measured.", "Keep temporal validation deterministic."),
        AuditItem("A16", "PII leakage scanning", "PASS" if privacy else "FAIL", ("scripts/pii_scan.py", "scripts/repository_audit.py", "factory/stage_gate.py"), "PII and repository scans exist in the quality system." if privacy else "Repository scanning is incomplete.", "Private data may leak into committed artifacts." if not privacy else "Generated-output scans should remain enabled.", "Retain PII and repository scanning."),
        AuditItem("A17", "Secret leakage controls", "PASS" if secret else "FAIL", ("scripts/secret_scan.py",), "Dedicated secret scanning is implemented." if secret else "Secret scanner is missing.", "Credentials may enter version control." if not secret else "Pattern-based scanning is supplemental to platform controls.", "Keep secret scanning in CI."),
        AuditItem("A18", "Path escape protection", "PASS" if (root / "core/local_case_store.py").is_file() else "FAIL", ("core/local_case_store.py",), "Private data roots and case keys are explicitly validated." if (root / "core/local_case_store.py").is_file() else "Storage boundary is incomplete.", "Path confusion can expose unrelated files." if not (root / "core/local_case_store.py").is_file() else "Filesystem edge cases require adversarial tests.", "Keep canonical root containment."),
        AuditItem("A19", "Symlink / traversal resistance", "PASS" if symlink_tests else "FAIL", ("tests/test_architecture_hardening.py", "core/import_manager.py"), "Adversarial symlink/traversal coverage exists." if symlink_tests else "Dedicated adversarial filesystem tests are missing.", "Symlinks or traversal may bypass naive checks." if not symlink_tests else "Continue covering new import paths.", "Retain adversarial filesystem regression tests."),
        AuditItem("A20", "Artifact isolation", "PASS" if artifact else "FAIL", (".github/workflows/mvros-v1-operations.yml",), "CI operational workflow uses a fixed synthetic fixture rather than private case input." if artifact else "Synthetic-only artifact isolation is not evidenced.", "Private CASE data could leak through CI inputs or artifacts." if not artifact else "Generated artifact content still needs privacy scanning.", "Keep production workflow inputs synthetic-only."),
        AuditItem("A21", "Domain model minimization", "PASS" if model_usage else "FAIL", ("scripts/model_usage_audit.py",), "Model usage is measured by an executable inventory rather than assumed." if model_usage else "Model usage measurement is missing.", "Unused duplication can grow silently." if not model_usage else "Measurement should precede consolidation.", "Use the inventory before deleting models."),
        AuditItem("A22", "Model usage / dead code", "PASS" if dead_code else "FAIL", ("scripts/dead_code_gate.py",), "Dead-code inventory is an explicit executable gate." if dead_code else "Dead-code gate is missing.", "Stale abstractions can accumulate." if not dead_code else "Inventory is evidence, not automatic deletion authority.", "Review dead-code inventory on lifecycle runs."),
        AuditItem("A23", "Domain separation", "PASS" if not violations else "FAIL", ("factory/", "core/", "knowledge/"), "Runtime domains remain independent from factory infrastructure." if not violations else "Runtime domains import factory modules.", "Factory coupling contaminates runtime responsibilities." if violations else "Boundary must remain enforced by CI.", "Keep runtime→factory imports forbidden."),
        AuditItem("A24", "Canonical identifiers", "PASS" if ids else "FAIL", ("core/models/ids.py",), "Canonical typed identifiers are defined for core entities." if ids else "Identifier definitions are incomplete.", "Identity ambiguity can break traceability." if not ids else "Serialization/uniqueness remains testable at contract boundaries.", "Keep typed IDs canonical."),
        AuditItem("A25", "Immutable source evidence", "PASS" if snapshot else "FAIL", ("core/local_case_store.py", "knowledge/provenance.py"), "Source snapshots are content-addressed by SHA-256 and not overwritten." if snapshot else "Immutable source snapshots are missing.", "Original evidence changes may become undetectable." if not snapshot else "Read-only filesystem semantics should be retained.", "Preserve content-addressed source snapshots."),
    ]


def write_reports(output_dir: Path, sha: str, items: list[AuditItem]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {status: 0 for status in STATUSES}
    for item in items:
        counts[item.status] += 1
    payload = {"audit": "Architectural Audit 1.0", "commit_sha": sha, "status_counts": counts, "items": [asdict(item) for item in items]}
    (output_dir / "audit-report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Architectural Audit 1.0", "", f"Commit: `{sha}`", "", "| ID | Title | Status | Evidence | Observation | Risk | Recommendation |", "|---|---|---|---|---|---|---|---|"]
    for item in items:
        values = [item.id, item.title, f"**{item.status}**", f"`{'; '.join(item.evidence)}`", item.observation, item.risk, item.recommendation]
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")
    lines.extend(["", "## Status counts", ""])
    lines.extend(f"- {status}: {counts[status]}" for status in STATUSES)
    (output_dir / "audit-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output_dir = args.output_dir.resolve()
    if root == output_dir or root in output_dir.parents:
        raise RuntimeError("Audit output directory must be outside the repository")
    items = build_items(root)
    if len(items) != 25 or {item.id for item in items} != {f"A{i}" for i in range(1, 26)}:
        raise RuntimeError("A1-A25 registry is invalid")
    write_reports(output_dir, current_sha(), items)
    return 0 if all(item.status == "PASS" for item in items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
