import pytest

from knowledge.epistemic import KnowledgeStatus
from knowledge.models.case_model_projection import (
    CaseModelProjection,
    ProjectedCognitiveRef,
    ProjectedRelationRef,
    TemporalView,
)
from knowledge.models.case_scope import (
    CaseReference,
    CaseScope,
    ReferenceAuthorization,
    ReferenceSet,
    ScopePolicy,
)


def _scope() -> CaseScope:
    reference = CaseReference(
        reference_id="REF-1",
        reference_type="document",
        source_ref="source://document/1",
        reason="directly relevant",
        authorization=ReferenceAuthorization.AUTHORIZED,
    )
    return CaseScope(
        case_id="CASE-001",
        owner="client:001",
        scope_policy=ScopePolicy(allowed_reference_types=frozenset({"document"})),
        reference_set=ReferenceSet((reference,)),
        goals=("resolve problem",),
        version=3,
    )


def _object(
    object_id: str,
    *,
    status: KnowledgeStatus = KnowledgeStatus.CLAIM,
) -> ProjectedCognitiveRef:
    return ProjectedCognitiveRef(
        object_id=object_id,
        object_version="v1",
        case_reference_id="REF-1",
        epistemic_status=status,
        provenance_refs=("source://document/1#p1",),
    )


def test_projection_preserves_scope_and_epistemic_status() -> None:
    fact = _object("OBJ-1", status=KnowledgeStatus.FACT)

    model = CaseModelProjection.build(
        _scope(),
        object_refs=(fact,),
        temporal_view=TemporalView.EVENT_TIME,
    )

    assert model.case_id == "CASE-001"
    assert model.scope_version == 3
    assert model.object_refs[0].epistemic_status is KnowledgeStatus.FACT
    assert model.source_reference_ids == ("REF-1",)
    assert model.temporal_view is TemporalView.EVENT_TIME


def test_projection_rejects_reference_not_admitted_by_case_scope() -> None:
    item = ProjectedCognitiveRef(
        object_id="OBJ-X",
        object_version="v1",
        case_reference_id="REF-NOT-IN-SCOPE",
        epistemic_status=KnowledgeStatus.HYPOTHESIS,
    )

    with pytest.raises(ValueError, match="unauthorized references"):
        CaseModelProjection.build(_scope(), object_refs=(item,))


def test_relation_endpoints_must_exist_in_same_projection() -> None:
    relation = ProjectedRelationRef(
        relation_id="REL-1",
        relation_version="v1",
        source_object_id="OBJ-1",
        target_object_id="OBJ-2",
        case_reference_id="REF-1",
        epistemic_status=KnowledgeStatus.CLAIM,
    )

    with pytest.raises(ValueError, match="outside Case Model"):
        CaseModelProjection.build(
            _scope(),
            object_refs=(_object("OBJ-1"),),
            relation_refs=(relation,),
        )


def test_relation_is_projected_when_both_endpoints_are_present() -> None:
    relation = ProjectedRelationRef(
        relation_id="REL-1",
        relation_version="v1",
        source_object_id="OBJ-1",
        target_object_id="OBJ-2",
        case_reference_id="REF-1",
        epistemic_status=KnowledgeStatus.HYPOTHESIS,
        provenance_refs=("source://document/1#p2",),
    )

    model = CaseModelProjection.build(
        _scope(),
        object_refs=(_object("OBJ-1"), _object("OBJ-2")),
        relation_refs=(relation,),
    )

    assert model.relation_refs == (relation,)
    assert model.relation_refs[0].epistemic_status is KnowledgeStatus.HYPOTHESIS


def test_projection_is_immutable() -> None:
    model = CaseModelProjection.build(_scope(), object_refs=(_object("OBJ-1"),))

    with pytest.raises(AttributeError):
        model.case_id = "CASE-OTHER"  # type: ignore[misc]


def test_unresolved_items_are_preserved() -> None:
    model = CaseModelProjection.build(
        _scope(),
        unresolved_items=("identity of contracting party remains disputed",),
    )

    assert model.unresolved_items == ("identity of contracting party remains disputed",)
