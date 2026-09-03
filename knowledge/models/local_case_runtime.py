"""Dynamic loader for private local MVROS case workspaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case, EvidenceItem, EvidenceWeight
from knowledge.models.case_workspace import CaseWorkspace
from knowledge.node import KnowledgeNode
from knowledge.types import NodeType


def _metadata(case_path: Path) -> dict[str, Any]:
    metadata_path = case_path / "case.yaml"
    if not metadata_path.is_file():
        return {}
    data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid case.yaml in {case_path}: expected mapping")
    return dict(data)


def _load_inventory(case_path: Path) -> list[dict[str, Any]]:
    inventory_path = case_path / "document_inventory.json"
    if not inventory_path.is_file():
        return []
    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Invalid document inventory in {case_path}: expected list")
    return [item for item in data if isinstance(item, dict)]


def _attach_ingested_documents(
    case: Case,
    graph: KnowledgeGraph,
    graph_case_id: str,
    inventory: list[dict[str, Any]],
) -> None:
    for item in inventory:
        document_id = str(item.get("document_id", "")).strip()
        source_name = str(item.get("source_name", "")).strip()
        original_path = str(item.get("original_path", "")).strip()
        if not document_id or not source_name:
            continue

        evidence = EvidenceItem(
            id=document_id,
            label=source_name,
            title=source_name,
            description="Original source document ingested into the private case store.",
            source_ref=original_path,
            ref=document_id,
            source=original_path,
            weight=EvidenceWeight.PRIMARY,
            kind="source_document",
            category="real_case",
            path=original_path,
            filename=source_name,
            metadata={
                "document_id": document_id,
                "sha256": str(item.get("sha256", "")),
                "document_type": str(item.get("document_type", "real_case")),
                "extraction_method": str(item.get("extraction_method", "")),
                "extracted_path": str(item.get("extracted_path", "")),
                "markdown_path": str(item.get("markdown_path", "")),
                "local_only": True,
            },
        )
        evidence.validate()
        case.evidence_items.append(evidence)

        graph.add_node(
            KnowledgeNode(
                id=f"document:{document_id}",
                type=NodeType.DOCUMENT,
                name=source_name,
                source=original_path,
                metadata={
                    "document_id": document_id,
                    "case_id": graph_case_id,
                    "sha256": str(item.get("sha256", "")),
                    "local_only": True,
                },
            )
        )


def build_local_case_workspace(
    case_key: str,
    *,
    data_root: Path | None = None,
) -> CaseWorkspace:
    """Open a private local case and attach its ingested source documents."""
    key = validate_case_key(case_key)
    root = ensure_data_root(data_root)
    case_path = case_dir(key, root)
    if not case_path.is_dir():
        raise KeyError(f"Unknown local case: {key!r} ({case_path})")

    meta = _metadata(case_path)
    case_id = str(meta.get("id") or key)
    title = str(meta.get("title") or "")
    working_title = str(meta.get("title") or meta.get("working_title") or key)
    signature_value = meta.get("signature") or meta.get("case_number") or None
    signature = str(signature_value) if signature_value else None

    case = Case(
        id=case_id,
        title=title,
        working_title=working_title,
        signature=signature,
        metadata=meta,
    )
    graph_case_id = f"case:{case_id}"
    graph = KnowledgeGraph()
    graph.add_node(
        KnowledgeNode(
            id=graph_case_id,
            type=NodeType.CASE,
            name=case.display_title(),
            source=str(case_path),
            metadata={"case_key": key, "local_only": True},
        )
    )

    inventory = _load_inventory(case_path)
    _attach_ingested_documents(case, graph, graph_case_id, inventory)
    workspace = CaseWorkspace(
        key=key,
        graph_case_id=graph_case_id,
        case=case,
        graph=graph,
        root=root,
    )
    workspace.meta.update(meta)
    workspace.meta["document_inventory"] = inventory
    workspace.meta["document_count"] = len(inventory)
    return workspace
