from __future__ import annotations

from copy import deepcopy

import pytest

from core.case_ledger.contracts import ContentAddress
from core.long_range_replay_v1 import (
    REQUIRED_MANIFEST_ARTIFACT_ROLES,
    LongRangeReplayError,
    LongRangeReplayManifestV1,
    ReplayArtifactBindingV1,
    ReplayArtifactRole,
    ReplayAssuranceEvidenceV1,
    ReplayAssuranceLevel,
    ReplayCapsuleV1,
    ReplayPreservationStatus,
    semantic_identity_equal,
)

COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40


def _address(label: str) -> ContentAddress:
    return ContentAddress.for_value({"label": label})


def _artifacts(
    *,
    preservation: ReplayPreservationStatus = ReplayPreservationStatus.PRESERVED,
    semantic_label: str = "semantic-v1",
    renderer_status: ReplayPreservationStatus | None = None,
) -> tuple[ReplayArtifactBindingV1, ...]:
    result: list[ReplayArtifactBindingV1] = []
    for role in ReplayArtifactRole:
        status = preservation
        if role is ReplayArtifactRole.RENDERER and renderer_status is not None:
            status = renderer_status
        label = semantic_label if role is ReplayArtifactRole.SEMANTIC_RESULT else role.value
        result.append(
            ReplayArtifactBindingV1(
                role=role,
                identity=_address(label),
                preservation=status,
            )
        )
    return tuple(result)


def _manifest(
    *,
    semantic_label: str = "semantic-v1",
    presentation_label: str | None = "presentation-v1",
    artifacts: tuple[ReplayArtifactBindingV1, ...] | None = None,
    case_id: str = "CASE-LRD-0001",
) -> LongRangeReplayManifestV1:
    inventory = artifacts or _artifacts(semantic_label=semantic_label)
    semantic_identity = next(
        item.identity
        for item in inventory
        if item.role is ReplayArtifactRole.SEMANTIC_RESULT
    )
    return LongRangeReplayManifestV1.build(
        case_id=case_id,
        case_replay_manifest_identity=_address("case-replay-v2"),
        coverage_matrix_identity=_address("lrd-01a-coverage"),
        code_commit_sha=COMMIT_SHA,
        code_tree_sha=TREE_SHA,
        artifacts=tuple(reversed(inventory)),
        semantic_result_identity=semantic_identity,
        presentation_identity=(
            _address(presentation_label) if presentation_label is not None else None
        ),
    )


def test_manifest_binds_complete_fixed_artifact_inventory_deterministically() -> None:
    manifest = _manifest()

    assert tuple(item.role.value for item in manifest.artifacts) == (
        REQUIRED_MANIFEST_ARTIFACT_ROLES
    )
    assert manifest.all_material_preserved
    assert manifest.manifest_identity == LongRangeReplayManifestV1.from_dict(
        manifest.canonical_dict()
    ).manifest_identity


def test_missing_required_artifact_role_fails_closed() -> None:
    artifacts = tuple(
        item for item in _artifacts() if item.role is not ReplayArtifactRole.RUNTIME
    )

    with pytest.raises(LongRangeReplayError, match="inventory is incomplete"):
        _manifest(artifacts=artifacts)


def test_duplicate_artifact_role_fails_closed() -> None:
    artifacts = _artifacts()
    duplicate = artifacts + (artifacts[0],)

    with pytest.raises(LongRangeReplayError, match="unique and sorted"):
        _manifest(artifacts=duplicate)


def test_unknown_manifest_field_fails_closed() -> None:
    raw = _manifest().canonical_dict()
    raw["implicit_fallback"] = True

    with pytest.raises(LongRangeReplayError, match="unknown=implicit_fallback"):
        LongRangeReplayManifestV1.from_dict(raw)


def test_unknown_preservation_status_fails_closed() -> None:
    raw = _manifest().canonical_dict()
    artifacts = raw["artifacts"]
    assert isinstance(artifacts, list)
    first = artifacts[0]
    assert isinstance(first, dict)
    first["preservation"] = "BEST_EFFORT"

    with pytest.raises(LongRangeReplayError, match="unknown replay artifact enum value"):
        LongRangeReplayManifestV1.from_dict(raw)


def test_one_byte_equivalent_identity_mutation_is_detected() -> None:
    raw = deepcopy(_manifest().canonical_dict())
    artifacts = raw["artifacts"]
    assert isinstance(artifacts, list)
    first = artifacts[0]
    assert isinstance(first, dict)
    identity = first["identity"]
    assert isinstance(identity, dict)
    digest = identity["digest"]
    assert isinstance(digest, str)
    replacement = "0" if digest[-1] != "0" else "1"
    identity["digest"] = digest[:-1] + replacement

    with pytest.raises(LongRangeReplayError, match="manifest identity mismatch"):
        LongRangeReplayManifestV1.from_dict(raw)


def test_semantic_identity_is_independent_from_presentation_identity() -> None:
    historical = _manifest(presentation_label="presentation-old")
    current = _manifest(presentation_label="presentation-new")

    assert historical.manifest_identity != current.manifest_identity
    assert historical.presentation_identity != current.presentation_identity
    assert semantic_identity_equal(historical, current)


def test_true_semantic_change_is_detected_even_when_presentation_matches() -> None:
    historical = _manifest(semantic_label="semantic-old", presentation_label="same-render")
    current = _manifest(semantic_label="semantic-new", presentation_label="same-render")

    assert not semantic_identity_equal(historical, current)


def test_cross_case_semantic_comparison_fails_closed() -> None:
    historical = _manifest(case_id="CASE-A")
    current = _manifest(case_id="CASE-B")

    with pytest.raises(LongRangeReplayError, match="across cases"):
        semantic_identity_equal(historical, current)


def test_assurance_exact_requires_complete_material_and_no_external_execution() -> None:
    evidence = ReplayAssuranceEvidenceV1(
        exact_identity_complete=True,
        deterministic_stages_reconstructed=True,
        required_material_complete=True,
        external_execution_present=False,
        external_outputs_verified=False,
        semantic_identity_verified=True,
    )

    assert evidence.level is ReplayAssuranceLevel.EXACT


def test_external_provider_history_never_promotes_to_exact() -> None:
    evidence = ReplayAssuranceEvidenceV1(
        exact_identity_complete=True,
        deterministic_stages_reconstructed=True,
        required_material_complete=True,
        external_execution_present=True,
        external_outputs_verified=True,
        semantic_identity_verified=True,
    )

    assert evidence.level is ReplayAssuranceLevel.VERIFIED_EXTERNAL


def test_incomplete_identity_is_unverifiable_not_guessed() -> None:
    evidence = ReplayAssuranceEvidenceV1(
        exact_identity_complete=False,
        deterministic_stages_reconstructed=True,
        required_material_complete=True,
        external_execution_present=False,
        external_outputs_verified=False,
        semantic_identity_verified=True,
    )

    assert evidence.level is ReplayAssuranceLevel.UNVERIFIABLE


def test_semantic_and_abstain_are_derived_from_available_evidence() -> None:
    semantic = ReplayAssuranceEvidenceV1(
        exact_identity_complete=True,
        deterministic_stages_reconstructed=False,
        required_material_complete=True,
        external_execution_present=False,
        external_outputs_verified=False,
        semantic_identity_verified=True,
    )
    abstain = ReplayAssuranceEvidenceV1(
        exact_identity_complete=True,
        deterministic_stages_reconstructed=False,
        required_material_complete=True,
        external_execution_present=False,
        external_outputs_verified=False,
        semantic_identity_verified=False,
    )

    assert semantic.level is ReplayAssuranceLevel.SEMANTIC
    assert abstain.level is ReplayAssuranceLevel.ABSTAIN


def test_capsule_is_content_addressed_and_correction_only_supersedes() -> None:
    original = ReplayCapsuleV1.build(manifest=_manifest(semantic_label="v1"))
    correction = ReplayCapsuleV1.build(
        manifest=_manifest(semantic_label="v2"),
        supersedes_digest=original.capsule_identity,
    )

    assert correction.capsule_identity != original.capsule_identity
    assert correction.supersedes_digest == original.capsule_identity
    assert ReplayCapsuleV1.from_dict(original.canonical_dict()).capsule_identity == (
        original.capsule_identity
    )
    assert ReplayCapsuleV1.from_dict(correction.canonical_dict()).supersedes_digest == (
        original.capsule_identity
    )


def test_capsule_tampering_is_detected() -> None:
    raw = deepcopy(ReplayCapsuleV1.build(manifest=_manifest()).canonical_dict())
    raw["supersedes_digest"] = _address("forged-parent").canonical_dict()

    with pytest.raises(LongRangeReplayError, match="capsule identity mismatch"):
        ReplayCapsuleV1.from_dict(raw)


def test_presentation_identity_requires_non_unavailable_renderer() -> None:
    artifacts = _artifacts(renderer_status=ReplayPreservationStatus.UNAVAILABLE)

    with pytest.raises(LongRangeReplayError, match="renderer material is unavailable"):
        _manifest(artifacts=artifacts, presentation_label="presentation")
