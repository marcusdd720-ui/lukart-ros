"""Dynamic loader for private local MVROS case workspaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.local_case_store import case_dir, ensure_data_root, validate_case_key
from core.private_case_runtime_bridge_v1 import (
    PrivateCaseRuntimeBridgeError,
    VerifiedLocalEvidenceProjectionV1,
    load_verified_projection,
)
from core.private_evidence_v1 import PrivateEvidenceStore
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


def _attach_verified_documents(
    case: Case,
    graph: KnowledgeGraph,
    graph_case_id: str,
    projection: VerifiedLocalEvidenceProjectionV1,
) -> None:
    for item in projection.documents:
        private_ref = f"private-evidence:{item.evidence_id}"
        evidence = EvidenceItem(
            id=item.document_id,
            label=item.document_id,
            title=item.document_id,
            description="Verified encrypted source document referenced by immutable evidence identity.",
            source_ref=private_ref,
            ref=item.document_id,
            source=private_ref,
            weight=EvidenceWeight.PRIMARY,
            kind="source_document",
            category="real_case",
            path=private_ref,
            filename=None,
            metadata={
                "document_id": item.document_id,
                "evidence_id": item.evidence_id,
                "manifest_digest": item.manifest_digest,
                "receipt_digest": item.receipt_digest,
                "derived_evidence_id": item.derived_evidence_id,
                "derived_manifest_digest": item.derived_manifest_digest,
                "derived_receipt_digest": item.derived_receipt_digest,
                "case_scope_digest": item.case_scope_digest,
                "runtime_projection_id": projection.projection_id,
                "local_only": True,
                "encrypted_at_rest": True,
                "verified_private_evidence": True,
            },
        )
        evidence.validate()
        case.evidence_items.append(evidence)

        graph.add_node(
            KnowledgeNode(
                id=f"document:{item.document_id}",
                type=NodeType.DOCUMENT,
                name=item.document_id,
                source=private_ref,
                metadata={
                    "document_id": item.document_id,
                    "case_id": graph_case_id,
                    "evidence_id": item.evidence_id,
                    "manifest_digest": item.manifest_digest,
                    "receipt_digest": item.receipt_digest,
                    "runtime_projection_id": projection.projection_id,
                    "local_only": True,
                    "encrypted_at_rest": True,
                    "verified_private_evidence": True,
                },
            )
        )


def build_local_case_workspace(
    case_key: str,
    *,
    data_root: Path | None = None,
    evidence_store: PrivateEvidenceStore | None = None,
) -> CaseWorkspace:
    """Open a private local case; encrypted evidence requires CASE-OPS-02 verification."""
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

    legacy_inventory = case_path / "document_inventory.json"
    projection: VerifiedLocalEvidenceProjectionV1 | None = None
    if evidence_store is None:
        if legacy_inventory.is_file():
            raise ValueError(
                "encrypted private evidence requires a verified CASE-OPS-02 evidence_store"
            )
    else:
        if evidence_store.case_id != case_id:
            raise ValueError("private evidence store case_id does not match local case")
        try:
            projection = load_verified_projection(evidence_store)
        except PrivateCaseRuntimeBridgeError as exc:
            raise ValueError("private evidence runtime verification failed") from exc
        _attach_verified_documents(case, graph, graph_case_id, projection)

    workspace = CaseWorkspace(
        key=key,
        graph_case_id=graph_case_id,
        case=case,
        graph=graph,
        root=root,
    )
    workspace.meta.update(meta)
    workspace.meta["document_count"] = len(projection.documents) if projection else 0
    workspace.meta["verified_private_evidence"] = projection is not None
    workspace.meta["runtime_projection_id"] = projection.projection_id if projection else None
    return workspace
