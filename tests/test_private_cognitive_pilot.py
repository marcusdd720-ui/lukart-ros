from __future__ import annotations

from pathlib import Path

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
from knowledge.models.case_scope import CaseEpistemicState
from knowledge.models.case_workspace import CaseWorkspace
from knowledge.models.decision_model import DecisionStatus
from knowledge.models.document_binding import DocumentStatus
from knowledge.models.private_cognitive_pilot import build_private_cognitive_baseline
from knowledge.models.strategy_model import StrategyStatus


def _workspace(tmp_path: Path, inventory: list[dict[str, object]]) -> CaseWorkspace:
    workspace = CaseWorkspace(
        key="LOCAL-001",
        graph_case_id="case:LOCAL-001",
        case=Case(id="LOCAL-001", title="", working_title="Private Case"),
        graph=KnowledgeGraph(),
        root=tmp_path,
    )
    workspace.meta["document_inventory"] = inventory
    return workspace


def test_private_cognitive_baseline_abstains_without_documents(tmp_path: Path) -> None:
    baseline = build_private_cognitive_baseline(_workspace(tmp_path, []))

    assert baseline.abstained
    assert baseline.decision.status is DecisionStatus.ABSTAIN
    assert baseline.strategy.status is StrategyStatus.ABSTAIN
    assert baseline.scope.epistemic_state is CaseEpistemicState.INSUFFICIENT_EVIDENCE
    assert baseline.case_model.object_refs == ()
    assert baseline.document_binding.status is DocumentStatus.REVIEW_REQUIRED
    assert baseline.document_binding.approval_required is True


def test_private_cognitive_baseline_projects_only_document_identity(tmp_path: Path) -> None:
    sha256 = "a" * 64
    workspace = _workspace(
        tmp_path,
        [
            {
                "document_id": "DOC-001",
                "source_name": "private-source.pdf",
                "sha256": sha256,
                "original_path": "/private/client/private-source.pdf",
                "secret_note": "must never be projected",
            }
        ],
    )

    baseline = build_private_cognitive_baseline(workspace)

    assert baseline.abstained
    assert baseline.scope.epistemic_state is CaseEpistemicState.OPEN_QUESTIONS
    assert len(baseline.case_model.object_refs) == 1
    projected = baseline.case_model.object_refs[0]
    assert projected.object_id == "document:DOC-001"
    assert projected.object_version == sha256
    assert baseline.decision.options == ()
    assert baseline.decision.selected_option is None
    assert baseline.strategy.selected_approach is None

    rendered = repr(baseline)
    assert "secret_note" not in rendered
    assert "must never be projected" not in rendered
    assert "/private/client/private-source.pdf" not in rendered


def test_private_cognitive_baseline_does_not_treat_inventory_as_content_truth(
    tmp_path: Path,
) -> None:
    baseline = build_private_cognitive_baseline(
        _workspace(
            tmp_path,
            [
                {
                    "document_id": "DOC-001",
                    "source_name": "statement.pdf",
                    "sha256": "b" * 64,
                }
            ],
        )
    )

    assert baseline.evidence_assessment.authenticity_state.value == "unknown"
    assert baseline.evidence_assessment.relevance_state.value == "unknown"
    assert baseline.evidence_assessment.strength_state.value == "unknown"
    assert "verified-substantive-facts" in baseline.evidence_assessment.missing_evidence
    assert "human-decision-authority" in baseline.evidence_assessment.missing_evidence
