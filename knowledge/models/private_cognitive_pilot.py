"""Privacy-safe Cognitive Chain baseline for a local private Case.

This adapter deliberately abstains from substantive legal/operational selection.
It projects only the existence and integrity metadata of source documents already
admitted to the private local Case workspace. Document contents and Case data
remain outside the public repository.
"""

from __future__ import annotations

import hashlib
import string
from dataclasses import dataclass

from knowledge.epistemic import KnowledgeStatus
from knowledge.models.case_model_projection import (
    CaseModelProjection,
    ProjectedCognitiveRef,
)
from knowledge.models.case_scope import (
    CaseEpistemicState,
    CaseOperationalState,
    CaseReference,
    CaseScope,
    ReferenceAuthorization,
    ReferenceSet,
    ScopePolicy,
)
from knowledge.models.case_workspace import CaseWorkspace
from knowledge.models.decision_model import DecisionModel, DecisionStatus
from knowledge.models.document_binding import ArtifactRef, DocumentBinding, DocumentStatus
from knowledge.models.evidence_assessment import AssessmentState, EvidenceAssessment
from knowledge.models.problem_model import ProblemModel, ProblemStatus
from knowledge.models.strategy_model import StrategyModel, StrategyStatus


@dataclass(frozen=True, slots=True)
class PrivateCognitiveBaseline:
    """Non-substantive cognitive baseline for one private Case run."""

    scope: CaseScope
    case_model: CaseModelProjection
    problem: ProblemModel
    evidence_assessment: EvidenceAssessment
    decision: DecisionModel
    strategy: StrategyModel
    document_binding: DocumentBinding

    @property
    def abstained(self) -> bool:
        return (
            self.decision.status is DecisionStatus.ABSTAIN
            and self.strategy.status is StrategyStatus.ABSTAIN
        )


def _safe_digest(parts: tuple[str, ...]) -> str:
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in string.hexdigits for character in value)


def build_private_cognitive_baseline(
    workspace: CaseWorkspace,
    *,
    owner: str = "local-human-review",
    decision_need: str = "Determine whether the private Case is ready for substantive decision.",
) -> PrivateCognitiveBaseline:
    """Build a fail-closed baseline from a private workspace's document inventory.

    Only document identity/integrity metadata is projected. No document contents,
    extracted facts, legal conclusions, strategy selection or action plan are
    synthesized by this function.
    """

    inventory = tuple(workspace.meta.get("document_inventory", ()))
    policy = ScopePolicy(
        allowed_reference_types=frozenset({"source_document"}),
        permitted_source_classes=frozenset({"private_local_case"}),
        cross_case_allowed=False,
        require_authorization=True,
    )
    references: list[CaseReference] = []
    projected: list[ProjectedCognitiveRef] = []

    for raw in inventory:
        if not isinstance(raw, dict):
            continue
        document_id = str(raw.get("document_id", "")).strip()
        sha256 = str(raw.get("sha256", "")).strip().lower()
        source_name = str(raw.get("source_name", "")).strip()
        if not document_id or not _valid_sha256(sha256):
            continue

        reference_id = f"source:{document_id}"
        reference = CaseReference(
            reference_id=reference_id,
            reference_type="source_document",
            source_ref=source_name or document_id,
            reason="Private source document admitted from the local Case inventory.",
            authorization=ReferenceAuthorization.AUTHORIZED,
            integrity_sha256=sha256,
        )
        references.append(reference)
        projected.append(
            ProjectedCognitiveRef(
                object_id=f"document:{document_id}",
                object_version=sha256,
                case_reference_id=reference_id,
                epistemic_status=KnowledgeStatus.FACT,
                provenance_refs=(reference_id,),
            )
        )

    scope = CaseScope(
        case_id=workspace.case.id,
        scope_policy=policy,
        reference_set=ReferenceSet(tuple(references)),
        owner=owner,
        operational_state=CaseOperationalState.ANALYSIS,
        epistemic_state=(
            CaseEpistemicState.OPEN_QUESTIONS
            if projected
            else CaseEpistemicState.INSUFFICIENT_EVIDENCE
        ),
        goals=("Assess readiness without inventing substantive Case conclusions.",),
    )
    case_model = CaseModelProjection.build(
        scope,
        object_refs=tuple(projected),
        unresolved_items=(
            "Substantive facts, propositions and legal conclusions require verified extraction.",
        ),
    )
    problem = ProblemModel.build(
        "private-readiness",
        case_model,
        decision_need,
        open_questions=(
            "Have substantive facts and contradictions been independently verified?",
            "Has a human authority selected or approved a decision path?",
        ),
        success_criteria=(
            "No substantive decision is selected from source inventory alone.",
            "All source references remain traceable to the private Case inventory.",
        ),
        status=ProblemStatus.ACTIVE,
    )

    support_refs = tuple(ref.reference_id for ref in references)
    assessment = EvidenceAssessment.build(
        "private-source-readiness",
        problem,
        "source-corpus-readiness",
        support_refs=support_refs,
        provenance_state=(
            AssessmentState.SATISFIED if support_refs else AssessmentState.INSUFFICIENT
        ),
        authenticity_state=AssessmentState.UNKNOWN,
        relevance_state=AssessmentState.UNKNOWN,
        completeness_state=(
            AssessmentState.PARTIAL if support_refs else AssessmentState.INSUFFICIENT
        ),
        strength_state=AssessmentState.UNKNOWN,
        missing_evidence=(
            "verified-substantive-facts",
            "human-decision-authority",
        ),
        limitations=(
            "Inventory integrity does not prove the truth of document contents.",
            "This baseline does not perform substantive legal reasoning.",
        ),
    )
    abstain_reason = (
        "Source inventory and integrity metadata alone are insufficient for a substantive "
        "decision; verified facts and human authority are required."
    )
    decision = DecisionModel.build(
        "private-readiness-decision",
        problem,
        evidence_assessments=(assessment,),
        rationale=abstain_reason,
        status=DecisionStatus.ABSTAIN,
    )
    strategy = StrategyModel.build(
        "private-readiness-strategy",
        decision,
        rationale=abstain_reason,
        status=StrategyStatus.ABSTAIN,
    )

    source_digest = _safe_digest(
        tuple(sorted(f"{ref.reference_id}:{ref.integrity_sha256}" for ref in references))
    )
    binding = DocumentBinding(
        document_id="private-readiness-dossier",
        renderer_id="kdoc-dumb-renderer",
        renderer_version="1.0",
        template_id="private-readiness",
        template_version="1.0",
        input_refs=(
            ArtifactRef("case_model", case_model.case_id, case_model.version, source_digest),
            ArtifactRef("problem", problem.problem_id, problem.version, source_digest),
            ArtifactRef("evidence", assessment.assessment_id, assessment.version, source_digest),
            ArtifactRef("decision", decision.decision_id, decision.version, source_digest),
            ArtifactRef("strategy", strategy.strategy_id, strategy.version, source_digest),
        ),
        source_digest=source_digest,
        generated_at="local-runtime",
        communication_target="local-human-review",
        required_sections=("scope", "evidence", "abstention", "open_questions"),
        unresolved_refs=problem.open_questions,
        limitation_refs=assessment.limitations,
        approval_required=True,
        status=DocumentStatus.REVIEW_REQUIRED,
    )

    return PrivateCognitiveBaseline(
        scope=scope,
        case_model=case_model,
        problem=problem,
        evidence_assessment=assessment,
        decision=decision,
        strategy=strategy,
        document_binding=binding,
    )
