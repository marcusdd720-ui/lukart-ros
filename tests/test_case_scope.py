import pytest

from knowledge.models.case_scope import (
    CaseEpistemicState,
    CaseOperationalState,
    CaseReference,
    CaseScope,
    ReferenceAuthorization,
    ReferenceSet,
    ScopePolicy,
)


def _scope(*, cross_case_allowed: bool = False) -> CaseScope:
    return CaseScope(
        case_id="CASE-001",
        owner="client:001",
        scope_policy=ScopePolicy(
            allowed_reference_types=frozenset({"document", "authority"}),
            cross_case_allowed=cross_case_allowed,
        ),
        reference_set=ReferenceSet(),
        goals=("determine decision need",),
    )


def _authorized_reference(**overrides: object) -> CaseReference:
    values: dict[str, object] = {
        "reference_id": "REF-1",
        "reference_type": "document",
        "source_ref": "source://document/1",
        "reason": "directly relevant to the Case goal",
        "authorization": ReferenceAuthorization.AUTHORIZED,
    }
    values.update(overrides)
    return CaseReference(**values)  # type: ignore[arg-type]


def test_authorized_reference_enters_scope_immutably() -> None:
    scope = _scope()

    updated = scope.with_reference(_authorized_reference())

    assert scope.reference_set.references == ()
    assert updated.reference_set.get("REF-1") is not None
    assert updated.version == 2


def test_pending_reference_fails_closed_when_authorization_required() -> None:
    scope = _scope()
    reference = _authorized_reference(authorization=ReferenceAuthorization.PENDING)

    with pytest.raises(ValueError, match="explicit authorization"):
        scope.with_reference(reference)


def test_scope_policy_rejects_out_of_scope_reference_type() -> None:
    scope = _scope()
    reference = _authorized_reference(reference_type="private_other_case")

    with pytest.raises(ValueError, match="rejected by ScopePolicy"):
        scope.with_reference(reference)


def test_cross_case_reference_requires_explicit_policy() -> None:
    reference = _authorized_reference(cross_case_source="CASE-OTHER")

    with pytest.raises(ValueError, match="cross-case reference"):
        _scope().with_reference(reference)

    allowed = _scope(cross_case_allowed=True).with_reference(reference)
    assert allowed.reference_set.get("REF-1") == reference


def test_operational_and_epistemic_state_are_independent() -> None:
    scope = _scope()

    updated = scope.with_states(
        operational_state=CaseOperationalState.ANALYSIS,
        epistemic_state=CaseEpistemicState.MATERIAL_CONTRADICTION,
    )

    assert updated.operational_state is CaseOperationalState.ANALYSIS
    assert updated.epistemic_state is CaseEpistemicState.MATERIAL_CONTRADICTION
    assert updated.version == 2


def test_duplicate_reference_id_fails_closed() -> None:
    scope = _scope().with_reference(_authorized_reference())

    with pytest.raises(ValueError, match="duplicate CaseReference"):
        scope.with_reference(_authorized_reference())


def test_invalid_integrity_hash_is_rejected() -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        _authorized_reference(integrity_sha256="abc123")
