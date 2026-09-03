"""Dynamic loader for private local MVROS case workspaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
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


def build_local_case_workspace(
    case_key: str,
    *,
    data_root: Path | None = None,
) -> CaseWorkspace:
    """Open a case created in the private local store without static registration."""
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
    workspace = CaseWorkspace(
        key=key,
        graph_case_id=graph_case_id,
        case=case,
        graph=graph,
        root=root,
    )
    workspace.meta.update(meta)
    return workspace
