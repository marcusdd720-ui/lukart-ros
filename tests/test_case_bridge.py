import pytest

from knowledge.models.case_bridge import (
    BridgeCandidate,
    BridgeStatus,
    BridgeSubjectRef,
    CaseBridge,
    DisclosureLevel,
)
from knowledge.models.case_scope import CaseScope, ReferenceSet, ScopePolicy


def _subject() -> BridgeSubjectRef:
    return BridgeSubjectRef(
        subject_id="OBJ-1",
        subject_version="v1",
        reference_type="cognitive_object",
        source_ref="source:obj-1:v1",
        provenance_ref="prov:obj-1",
    )


def _target(*, allow_cross_case: bool) -> CaseScope:
    return CaseScope(
        case_id="CASE-B",
        owner="client:1",
        scope_policy=ScopePolicy(
            allowed_reference_types=frozenset({"cognitive_object"}),
            cross_case_allowed=allow_cross_case,
        ),
        reference_set=ReferenceSet(),
    )


def _active_bridge(**kwargs: object) -> CaseBridge:
    values = {
        "bridge_id": "BRIDGE-1",
        "source_case_id": "CASE-A",
        "target_case_id": "CASE-B",
        "subject_refs": (_subject(),),
        "disclosure_level": DisclosureLevel.SOURCE_VERSION,
        "purpose": "compare one bounded source",
        "authorization_ref": "authority:1",
        "provenance_ref": "bridge-prov:1",
        "created_at": "2026-09-05T04:30:00Z",
        "status": BridgeStatus.ACTIVE,
    }
    values.update(kwargs)
    return CaseBridge(**values)  # type: ignore[arg-type]


def test_candidate_discovery_contains_only_minimal_metadata() -> None:
    candidate = BridgeCandidate(
        candidate_id="CAND-1",
        source_case_id="CASE-A",
        target_case_id="CASE-B",
        subject_ids=("OBJ-1",),
        purpose_hint="possible shared source",
    )

    assert not hasattr(candidate, "content")
    assert candidate.subject_ids == ("OBJ-1",)


def test_non_active_bridge_cannot_be_consumed() -> None:
    bridge = _active_bridge(status=BridgeStatus.PROPOSED, authorization_ref=None)

    with pytest.raises(ValueError, match="not ACTIVE"):
        bridge.import_into(_target(allow_cross_case=True), "OBJ-1")


def test_active_bridge_imports_only_through_target_reference_set() -> None:
    target = _target(allow_cross_case=True)
    updated = _active_bridge().import_into(target, "OBJ-1")

    assert len(target.reference_set.references) == 0
    assert len(updated.reference_set.references) == 1
    imported = updated.reference_set.references[0]
    assert imported.cross_case_source == "CASE-A"
    assert imported.source_ref == "source:obj-1:v1"


def test_target_scope_can_reject_cross_case_import() -> None:
    with pytest.raises(ValueError, match="cross-case reference rejected"):
        _active_bridge().import_into(_target(allow_cross_case=False), "OBJ-1")


def test_bridge_cannot_disclose_subject_outside_bounded_scope() -> None:
    with pytest.raises(ValueError, match="outside CaseBridge disclosure scope"):
        _active_bridge().import_into(_target(allow_cross_case=True), "OBJ-2")


def test_same_client_does_not_create_implicit_cross_case_access() -> None:
    source = CaseScope(
        case_id="CASE-A",
        owner="client:1",
        scope_policy=ScopePolicy(cross_case_allowed=True),
        reference_set=ReferenceSet(),
    )
    target = _target(allow_cross_case=True)

    assert source.owner == target.owner
    assert target.reference_set.references == ()


def test_human_review_required_bridge_cannot_self_activate() -> None:
    with pytest.raises(ValueError, match="human approval"):
        _active_bridge(human_review_required=True, human_approval_ref=None)


def test_revoked_bridge_preserves_propagation_signal() -> None:
    bridge = _active_bridge(
        status=BridgeStatus.REVOKED,
        authorization_ref="authority:1",
        audit_lineage=("ACTIVE:v1", "REVOKED:v2"),
    )

    assert bridge.revocation_requires_propagation(relied_upon=True)
    assert bridge.audit_lineage[-1] == "REVOKED:v2"
