from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

STATUSES = (
    "PASS",
    "FAIL",
    "RISK",
    "NOT IMPLEMENTED",
    "NOT APPLICABLE",
)
CASE_STATES = (
    "FACT",
    "LAW",
    "DOSSIER",
    "REVIEW",
    "OUTBOUND",
    "OPEN",
    "FREEZE",
    "RELEASE",
    "NOTE",
)


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
            raise ValueError(f"Invalid audit status: {self.status}")


class AuditContext:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._cache: dict[str, str] = {}
        self._imports: dict[str, set[str]] = {}

    def path(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"Path escapes audit root: {relative}")
        return candidate

    def exists(self, relative: str) -> bool:
        return self.path(relative).exists()

    def read(self, relative: str) -> str:
        if relative not in self._cache:
            path = self.path(relative)
            self._cache[relative] = (
                path.read_text(encoding="utf-8") if path.is_file() else ""
            )
        return self._cache[relative]

    def files(self, directory: str, suffix: str = ".py") -> list[Path]:
        path = self.path(directory)
        if not path.is_dir():
            return []
        return sorted(
            entry for entry in path.rglob(f"*{suffix}") if ".git" not in entry.parts
        )

    def imports(self, path: Path) -> set[str]:
        key = str(path)
        if key in self._imports:
            return self._imports[key]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            result: set[str] = set()
        else:
            result = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    result.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    result.add(node.module.split(".")[0])
        self._imports[key] = result
        return result

    def contains(self, paths: tuple[str, ...], needles: tuple[str, ...]) -> bool:
        text = "\n".join(self.read(path) for path in paths).lower()
        return any(needle.lower() in text for needle in needles)

    def source_digest(self, paths: list[str]) -> str:
        digest = hashlib.sha256()
        for path in sorted(paths):
            digest.update(path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(self.read(path).encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()


def make_item(
    audit_id: str,
    title: str,
    status: str,
    evidence: tuple[str, ...],
    observation: str,
    risk: str,
    recommendation: str,
) -> AuditItem:
    return AuditItem(
        audit_id,
        title,
        status,
        evidence,
        observation,
        risk,
        recommendation,
    )


def runtime_factory_imports(ctx: AuditContext) -> list[str]:
    violations: list[str] = []
    for directory in ("core", "knowledge"):
        for path in ctx.files(directory):
            if "factory" in ctx.imports(path):
                violations.append(path.relative_to(ctx.root).as_posix())
    return violations


def build_items(ctx: AuditContext) -> list[AuditItem]:
    workflows = tuple(
        path.relative_to(ctx.root).as_posix()
        for path in ctx.files(".github/workflows", suffix=".yml")
    )
    tests = tuple(
        path.relative_to(ctx.root).as_posix() for path in ctx.files("tests")
    )
    runtime_imports = runtime_factory_imports(ctx)
    workspace = ctx.read("knowledge/models/case_workspace.py")
    case_manager = ctx.read("core/case_manager.py")
    case_store = ctx.read("factory/local_case_store.py")
    orchestrator = ctx.read("factory/stage_orchestrator.py")
    fact_contract = ctx.read("knowledge/fact_contract.py")
    fact_extractor = ctx.read("knowledge/fact_extractor.py")
    provenance = ctx.read("knowledge/provenance.py")
    workflow_text = "\n".join(ctx.read(path) for path in workflows)
    test_text = "\n".join(ctx.read(path) for path in tests)

    source_reference = all(
        token in fact_contract + provenance
        for token in ("source_document_id", "source_document_sha256")
    )
    confidence = ctx.contains(
        ("knowledge/fact_contract.py", "knowledge/fact_extractor.py"),
        ("confidence", "epistemic", "certainty"),
    )
    contradiction = ctx.contains(
        ("core", "knowledge"),
        ("contradictiondetector", "conflictdetector"),
    )
    evidence_readiness = ctx.contains(
        (
            "core/case_manager.py",
            "knowledge/models/case_workspace.py",
            "scripts/run_case_pipeline.py",
        ),
        ("evidence_readiness", "missing_evidence", "required_evidence"),
    )
    timeline_validation = ctx.contains(
        ("core", "knowledge"),
        ("timeline_validator", "temporal_consistency", "date_consistency"),
    )
    secret_scan = any(
        token in workflow_text.lower()
        for token in ("gitleaks", "trufflehog", "secret-scanning")
    )
    symlink_test = any(
        token in test_text.lower()
        for token in ("symlink", "path_traversal", "directory_traversal")
    )
    has_pii_scan = ctx.exists("scripts/pii_scan.py")
    has_repo_scan = ctx.exists("scripts/repository_audit.py")
    root_guard = "MVROS_DATA_ROOT" in case_manager + case_store
    resolved_paths = "resolve()" in case_manager + case_store
    integrity_hash = ctx.contains(
        ("factory/local_case_store.py", "knowledge/provenance.py"),
        ("sha256", "content_hash"),
    )
    canonical_ids = all(
        token in ctx.read("core/models/ids.py") for token in ("DocumentId", "FactId")
    )
    entrypoints = all(
        ctx.exists(path)
        for path in (
            "scripts/new_case.py",
            "scripts/run_case_pipeline.py",
            "scripts/mvros_v1.py",
        )
    )
    lifecycle = all(state in workspace for state in CASE_STATES)
    fresh_sha = "repaired_sha == fresh_sha" in orchestrator
    artifact_controls = has_pii_scan and has_repo_scan and (
        "synthetic" in workflow_text.lower()
    )

    items = [
        make_item(
            "A1",
            "Factory ↔ MVROS boundary",
            "FAIL" if runtime_imports else "PASS",
            ("factory/", "core/", "knowledge/"),
            "Runtime code does not import factory modules."
            if not runtime_imports
            else f"Runtime imports factory modules: {runtime_imports}.",
            "Build infrastructure can leak into runtime." if runtime_imports else "No current direct coupling found.",
            "Keep dependency direction as a CI invariant.",
        ),
        make_item(
            "A2",
            "Private-data boundary",
            "PASS" if root_guard else "FAIL",
            ("README.md", "core/case_manager.py", "factory/local_case_store.py", "scripts/publish.py"),
            "Private local storage and publication restrictions are implemented."
            if root_guard
            else "Private data-root handling is not proven.",
            "Static checks cannot prove every exfiltration route.",
            "Retain adversarial privacy tests and scan generated outputs.",
        ),
        make_item(
            "A3",
            "CASE lifecycle",
            "PASS" if lifecycle else "RISK",
            ("knowledge/models/case_workspace.py",),
            "All declared CASE lifecycle states are represented."
            if lifecycle
            else "The declared lifecycle is incomplete.",
            "State presence does not prove valid transition enforcement.",
            "Add explicit valid/invalid transition tests.",
        ),
        make_item(
            "A4",
            "Canonical source of truth",
            "RISK",
            ("core/case_manager.py", "knowledge/models/case_workspace.py", "scripts/run_case_pipeline.py"),
            "Case state is distributed across runtime components without a single enforced manifest.",
            "Representations can drift.",
            "Introduce a canonical manifest only when real-case measurement shows the need.",
        ),
        make_item(
            "A5",
            "Traceability",
            "PASS" if canonical_ids and source_reference else "RISK",
            ("core/models/ids.py", "knowledge/fact_contract.py", "knowledge/provenance.py"),
            "Canonical IDs and source-document identity/integrity fields are present."
            if canonical_ids and source_reference
            else "End-to-end source linkage is not fully proven.",
            "Weak traceability reduces auditability.",
            "Add an end-to-end traceability regression test.",
        ),
        make_item(
            "A6",
            "Idempotency",
            "RISK",
            ("factory/stage_orchestrator.py", "scripts/run_case_pipeline.py", "knowledge/project_timeline.py"),
            "Some operations are explicitly repeat-safe, but full CASE-stage equivalence is not a contract.",
            "Reruns may duplicate or change derived artifacts.",
            "Add repeated-run equivalence tests for material stages.",
        ),
        make_item(
            "A7",
            "Determinism",
            "PASS" if ctx.exists("knowledge/fact_extractor.py") else "RISK",
            ("knowledge/fact_extractor.py", "knowledge/extraction_stage.py"),
            "Deterministic extraction components are present."
            if ctx.exists("knowledge/fact_extractor.py")
            else "Deterministic extraction evidence is incomplete.",
            "End-to-end output hashes are not yet enforced.",
            "Add repeated-run content digests.",
        ),
        make_item(
            "A8",
            "Failure isolation / recovery",
            "PASS" if fresh_sha else "RISK",
            ("factory/stage_orchestrator.py", "factory/self_healing.py"),
            "Automatic repair verifies a fresh SHA before retry."
            if fresh_sha
            else "Fresh-SHA recovery is not proven.",
            "Same-SHA retries can mask ineffective repairs.",
            "Keep fresh-SHA enforcement hard.",
        ),
        make_item(
            "A9",
            "Dependency boundaries",
            "RISK",
            ("core/", "knowledge/", "factory/"),
            "Architecture can be inspected, but dependency direction is not a dedicated gate.",
            "Future imports may erode boundaries.",
            "Promote dependency rules into CI.",
        ),
        make_item(
            "A10",
            "Public CLI/API contracts",
            "PASS" if entrypoints else "FAIL",
            ("scripts/new_case.py", "scripts/run_case_pipeline.py", "scripts/mvros_v1.py"),
            "Primary operational entrypoints exist."
            if entrypoints
            else "A primary entrypoint is missing.",
            "Edge behavior may remain underspecified.",
            "Add CLI argument, exit-code and output contract tests.",
        ),
        make_item(
            "A11",
            "Evidence provenance",
            "PASS" if source_reference else "RISK",
            ("knowledge/provenance.py", "knowledge/fact_contract.py"),
            "Facts are bound to a source document ID and SHA-256 integrity value."
            if source_reference
            else "Mandatory provenance is not proven.",
            "Source-less facts weaken independent review.",
            "Make provenance mandatory at every fact-ingest boundary.",
        ),
        make_item(
            "A12",
            "Fact confidence / epistemic status",
            "PASS" if confidence else "RISK",
            ("knowledge/fact_contract.py", "knowledge/fact_extractor.py"),
            "Explicit confidence/epistemic status is represented."
            if confidence
            else "Explicit confidence/epistemic status was not identified.",
            "Interpretation may be confused with fact.",
            "Define epistemic state and confidence semantics.",
        ),
        make_item(
            "A13",
            "Contradiction detection",
            "PASS" if contradiction else "NOT IMPLEMENTED",
            ("core/", "knowledge/"),
            "A dedicated contradiction detector was identified."
            if contradiction
            else "No dedicated contradiction detector was identified.",
            "Conflicting evidence can remain unresolved.",
            "Implement contradiction detection with regression fixtures.",
        ),
        make_item(
            "A14",
            "Missing-evidence detection",
            "PASS" if evidence_readiness else "NOT IMPLEMENTED",
            ("core/case_manager.py", "knowledge/models/case_workspace.py", "scripts/run_case_pipeline.py"),
            "A dedicated evidence-readiness gate is present."
            if evidence_readiness
            else "No dedicated evidence-readiness gate was identified.",
            "Analysis can proceed with critical evidence missing.",
            "Add explicit evidence-readiness rules after measured need.",
        ),
        make_item(
            "A15",
            "Timeline consistency",
            "PASS" if timeline_validation else "NOT IMPLEMENTED",
            ("core/", "knowledge/"),
            "A dedicated temporal consistency validator is present."
            if timeline_validation
            else "No dedicated temporal consistency validator was identified.",
            "Impossible or conflicting dates may survive.",
            "Add timeline consistency rules when validated by real-case needs.",
        ),
        make_item(
            "A16",
            "PII leakage scanning",
            "PASS" if has_pii_scan and has_repo_scan else "FAIL",
            ("scripts/pii_scan.py", "scripts/repository_audit.py", "factory/stage_gate.py"),
            "PII and repository scanners exist and are part of the quality gate."
            if has_pii_scan and has_repo_scan
            else "Required repository/PII scanning is incomplete.",
            "Generated outputs still need dedicated leakage validation.",
            "Extend scanning to generated artifacts and logs.",
        ),
        make_item(
            "A17",
            "Secret leakage controls",
            "PASS" if secret_scan else "NOT IMPLEMENTED",
            workflows or (".github/workflows/",),
            "A dedicated secret scanner is configured."
            if secret_scan
            else "No dedicated secret scanner is configured in inspected workflows.",
            "Credentials can enter the repository without a specialized gate.",
            "Add secret scanning to CI.",
        ),
        make_item(
            "A18",
            "Path escape protection",
            "PASS" if root_guard and resolved_paths else "RISK",
            ("core/case_manager.py", "factory/local_case_store.py"),
            "Private root handling and resolved-path checks are implemented."
            if root_guard and resolved_paths
            else "Root/path containment is incompletely evidenced.",
            "Path confusion can expose unrelated files.",
            "Add canonical root-containment tests.",
        ),
        make_item(
            "A19",
            "Symlink / traversal resistance",
            "PASS" if symlink_test else "NOT IMPLEMENTED",
            ("tests/", "core/case_manager.py", "factory/local_case_store.py"),
            "Adversarial symlink/traversal tests exist."
            if symlink_test
            else "No dedicated symlink/traversal tests were identified.",
            "Links or traversal can bypass naive path checks.",
            "Add adversarial filesystem tests.",
        ),
        make_item(
            "A20",
            "Artifact isolation",
            "PASS" if artifact_controls else "RISK",
            workflows or (".github/workflows/",),
            "CI privacy/repository controls and synthetic-only workflow evidence are present."
            if artifact_controls
            else "Universal artifact-content isolation is not fully demonstrated.",
            "Private CASE data could leak through CI artifacts or logs.",
            "Add artifact-content deny rules and generated-artifact scanning.",
        ),
        make_item(
            "A21",
            "Domain model minimization",
            "RISK",
            ("core/models/", "knowledge/models/"),
            "Multiple model namespaces exist; duplication has not yet been measured.",
            "Speculative consolidation could also remove useful boundaries.",
            "Measure actual usage before consolidation.",
        ),
        make_item(
            "A22",
            "Model usage / dead code",
            "RISK",
            ("validation/code_audit/", "factory/stage_gate.py"),
            "Dead-code analysis exists in the repository, but it is not established as a universal lifecycle gate.",
            "Stale abstractions can accumulate silently.",
            "Use the existing code-audit capability to build a measured dead-code inventory.",
        ),
        make_item(
            "A23",
            "Domain separation",
            "PASS" if not runtime_imports else "FAIL",
            ("factory/", "core/", "knowledge/"),
            "Runtime domains do not directly depend on factory modules."
            if not runtime_imports
            else "Runtime domains depend on factory modules.",
            "Factory/runtime coupling can contaminate runtime responsibilities.",
            "Keep factory dependencies outside runtime domains.",
        ),
        make_item(
            "A24",
            "Canonical identifiers",
            "PASS" if canonical_ids else "RISK",
            ("core/models/ids.py", "knowledge/fact_contract.py"),
            "Canonical DocumentId and FactId identifiers are defined."
            if canonical_ids
            else "Canonical identifiers are incomplete.",
            "Identity ambiguity breaks cross-stage traceability.",
            "Add uniqueness and serialization tests.",
        ),
        make_item(
            "A25",
            "Immutable source evidence",
            "PASS" if integrity_hash else "NOT IMPLEMENTED",
            ("factory/local_case_store.py", "knowledge/provenance.py"),
            "SHA-256 integrity information is part of evidence provenance."
            if integrity_hash
            else "Immutable/hash-backed source evidence is not clearly established.",
            "Original evidence can change without detectable integrity evidence.",
            "Make source snapshots immutable and append-only.",
        ),
    ]
    if len(items) != 25:
        raise RuntimeError(f"Expected 25 audit items, got {len(items)}")
    if {entry.id for entry in items} != {f"A{i}" for i in range(1, 26)}:
        raise RuntimeError("Audit IDs are incomplete or duplicated")
    return items


def current_sha(root: Path) -> str:
    env_sha = os.environ.get("GITHUB_SHA", "").strip()
    if env_sha:
        return env_sha
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def write_reports(output_dir: Path, sha: str, items: list[AuditItem]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {status: 0 for status in STATUSES}
    for entry in items:
        counts[entry.status] += 1
    payload = {
        "audit": "Architectural Audit 1.0",
        "commit_sha": sha,
        "status_counts": counts,
        "items": [asdict(entry) for entry in items],
    }
    (output_dir / "audit-report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Architectural Audit 1.0",
        "",
        f"Commit: `{sha}`",
        "",
        "| ID | Title | Status | Evidence | Observation | Risk | Recommendation |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in items:
        values = (
            entry.id,
            entry.title,
            f"**{entry.status}**",
            f"`{'; '.join(entry.evidence)}`",
            entry.observation,
            entry.risk,
            entry.recommendation,
        )
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")
    lines.extend(["", "## Status counts", ""])
    lines.extend(f"- {status}: {counts[status]}" for status in STATUSES)
    (output_dir / "audit-report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    default = Path(os.environ.get("RUNNER_TEMP", str(root / ".audit-output")))
    output_dir = (args.output_dir or default / "architectural-audit").resolve()
    if output_dir == root or root in output_dir.parents:
        raise RuntimeError("Audit output directory must be outside the repository")

    ctx = AuditContext(root)
    items = build_items(ctx)
    sha = current_sha(root)
    write_reports(output_dir, sha, items)
    source_paths = [
        path.relative_to(root).as_posix()
        for path in ctx.files("core") + ctx.files("knowledge") + ctx.files("factory")
    ]
    print(f"AUDIT_SHA={sha}")
    print(f"AUDIT_ITEMS={len(items)}")
    print(f"AUDIT_SOURCE_DIGEST={ctx.source_digest(source_paths)}")
    print(f"AUDIT_OUTPUT_DIR={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
