"""Validation for Candidate/Canonical documents governed by KMeta-1.0."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FIELDS = (
    "Canonical ID",
    "Title",
    "Version",
    "Status",
    "Class",
    "Stability Index",
    "Owner",
    "Depends On",
    "Affects",
    "Supersedes",
    "Validation Method",
    "Review Requirement",
    "Change Policy",
)

ALLOWED_STATUSES = frozenset(
    {
        "DRAFT",
        "PROPOSED",
        "CANDIDATE CANON",
        "VALIDATED CANDIDATE",
        "CANONICAL",
        "DEPRECATED",
        "SUPERSEDED",
        "REJECTED",
    }
)
ALLOWED_CLASSES = frozenset(
    {
        "AXIOM",
        "ONTOLOGY",
        "EPISTEMOLOGY",
        "ALGEBRA",
        "METHODOLOGY",
        "ARCHITECTURE",
        "STANDARD",
        "VALIDATION",
        "RUNTIME",
    }
)
CANON_ID_RE = re.compile(r"^[A-Z][A-Za-z0-9]*-\d+\.\d+$")
METADATA_RE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]+):\s*(?P<value>.*)$")


@dataclass(frozen=True, slots=True)
class CanonDocument:
    path: Path
    canonical_id: str
    metadata: dict[str, str]
    dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanonViolation:
    path: str
    code: str
    message: str


def parse_canon_document(path: Path) -> tuple[CanonDocument | None, tuple[CanonViolation, ...]]:
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    violations: list[CanonViolation] = []

    for line in text.splitlines()[1:80]:
        if line.startswith("## "):
            break
        match = METADATA_RE.match(line.strip())
        if match:
            metadata[match.group("key")] = match.group("value").strip()

    for field in REQUIRED_FIELDS:
        if not metadata.get(field, "").strip():
            violations.append(
                CanonViolation(str(path), "MISSING_METADATA", f"missing metadata field: {field}")
            )

    canonical_id = metadata.get("Canonical ID", "").strip()
    if canonical_id:
        if not CANON_ID_RE.fullmatch(canonical_id):
            violations.append(
                CanonViolation(
                    str(path),
                    "INVALID_CANON_ID",
                    f"invalid Canonical ID: {canonical_id}",
                )
            )
        expected_name = f"{canonical_id}.md"
        if path.name != expected_name:
            violations.append(
                CanonViolation(
                    str(path),
                    "ID_FILENAME_MISMATCH",
                    f"Canonical ID {canonical_id} must use filename {expected_name}",
                )
            )

    status = metadata.get("Status", "")
    if status and status not in ALLOWED_STATUSES:
        violations.append(CanonViolation(str(path), "INVALID_STATUS", f"invalid Status: {status}"))

    doc_class = metadata.get("Class", "")
    if doc_class and doc_class not in ALLOWED_CLASSES:
        violations.append(CanonViolation(str(path), "INVALID_CLASS", f"invalid Class: {doc_class}"))

    stability = metadata.get("Stability Index", "")
    if stability:
        try:
            value = int(stability)
        except ValueError:
            value = 0
        if value not in range(1, 6):
            violations.append(
                CanonViolation(str(path), "INVALID_STABILITY", "Stability Index must be 1..5")
            )

    dependencies = tuple(
        item.strip()
        for item in metadata.get("Depends On", "").split(";")
        if item.strip() and item.strip().lower() != "none"
    )
    document = CanonDocument(path, canonical_id, metadata, dependencies) if canonical_id else None
    return document, tuple(violations)


def validate_canon_directory(canon_dir: Path) -> tuple[CanonViolation, ...]:
    documents: list[CanonDocument] = []
    violations: list[CanonViolation] = []

    for path in sorted(canon_dir.glob("*.md")):
        document, parsed_violations = parse_canon_document(path)
        violations.extend(parsed_violations)
        if document is not None:
            documents.append(document)

    by_id: dict[str, CanonDocument] = {}
    for document in documents:
        if document.canonical_id in by_id:
            violations.append(
                CanonViolation(
                    str(document.path),
                    "DUPLICATE_CANON_ID",
                    f"duplicate Canonical ID: {document.canonical_id}",
                )
            )
        else:
            by_id[document.canonical_id] = document

    graph: dict[str, tuple[str, ...]] = {}
    for document in documents:
        internal_dependencies: list[str] = []
        for dependency in document.dependencies:
            if CANON_ID_RE.fullmatch(dependency):
                internal_dependencies.append(dependency)
                if dependency not in by_id:
                    violations.append(
                        CanonViolation(
                            str(document.path),
                            "MISSING_CANON_DEPENDENCY",
                            f"missing canonical dependency: {dependency}",
                        )
                    )
        graph[document.canonical_id] = tuple(internal_dependencies)

    violations.extend(_find_cycles(graph, by_id))
    return tuple(violations)


def _find_cycles(
    graph: dict[str, tuple[str, ...]],
    by_id: dict[str, CanonDocument],
) -> tuple[CanonViolation, ...]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    found: set[tuple[str, ...]] = set()
    violations: list[CanonViolation] = []

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            index = stack.index(node)
            cycle = tuple(stack[index:] + [node])
            if cycle not in found:
                found.add(cycle)
                path = by_id[node].path if node in by_id else Path(node)
                violations.append(
                    CanonViolation(
                        str(path),
                        "DEPENDENCY_CYCLE",
                        "canonical dependency cycle: " + " -> ".join(cycle),
                    )
                )
            return

        visiting.add(node)
        stack.append(node)
        for dependency in graph.get(node, ()):
            if dependency in graph:
                visit(dependency)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return tuple(violations)
