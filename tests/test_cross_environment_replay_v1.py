from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import pytest

from core.cross_environment_replay_v1 import (
    CrossEnvironmentReplayClassification,
    CrossEnvironmentReplayError,
    ReplayExecutionStatus,
    build_environment_profile,
    build_observed_environment_receipt,
    build_replay_plan,
    build_replay_receipt,
    build_replay_report,
    capture_environment_snapshot,
    classify_from_lrd01d,
    digest_value,
    environment_compatible,
    verify_environment_profile,
    verify_observed_environment,
)
from core.cross_environment_replay_verifier_v1 import VerificationError, verify_file


def h(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


@lru_cache(maxsize=1)
def _cached_material() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    verifier = h("verifier")
    policy = h("policy")
    snapshot = capture_environment_snapshot()
    profile = build_environment_profile(
        name="current",
        observed=snapshot,
        dependency_lock_digest=h("lock"),
        physical_dependency_artifact_identities=[
            str(snapshot["installed_artifact_inventory_digest"])
        ],
        canonicalization_profile_digest=h("canon"),
        migration_registry_digest=h("migration"),
        crypto_profile_digest=h("crypto"),
        lrd01i_bundle_digest=h("bundle"),
        replay_verifier_digest=verifier,
        environment_policy_digest=policy,
    )
    observed = build_observed_environment_receipt(
        snapshot,
        declared_profile_digest=str(profile["profile_digest"]),
        verifier_digest=verifier,
        environment_policy_digest=policy,
    )
    other = dict(profile)
    other["name"] = "materially-other"
    other["profile_digest"] = digest_value(
        {k: v for k, v in other.items() if k != "profile_digest"}
    )
    plan = build_replay_plan(
        lrd01i_bundle_digest=h("bundle"),
        ssc02_manifest_digest=h("ssc"),
        environment_profile_digests=[str(profile["profile_digest"]), str(other["profile_digest"])],
        reference_profile_digest=str(profile["profile_digest"]),
        replay_policy_digest=h("replay-policy"),
        migration_registry_digest=h("migration"),
        canonicalization_profile_digest=h("canon"),
        crypto_profile_digest=h("crypto"),
        expected_matrix=[str(profile["profile_digest"]), str(other["profile_digest"])],
        hard_bounds={"network": "DENY"},
    )
    return observed, profile, other, plan


def material() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    return copy.deepcopy(_cached_material())


def test_observed_and_declared_are_separate_content_addressed_objects() -> None:
    observed, profile, _, _ = material()
    assert verify_observed_environment(observed) == observed["observed_environment_digest"]
    assert verify_environment_profile(profile) == profile["profile_digest"]
    assert observed["observed_environment_digest"] != profile["profile_digest"]
    assert profile["python_version"] == observed["python_version"]
    for key in (
        "os_release", "os_build", "openssl_identity", "sqlite_identity",
        "libc_runtime_identity", "locale", "timezone", "filesystem_semantics",
    ):
        assert profile[key] == observed[key]
    assert observed["declared_profile_digest"] == profile["profile_digest"]


def test_lrd01d_is_semantic_authority_mapping_only() -> None:
    _, profile, other, _ = material()
    exact = classify_from_lrd01d(
        lrd01d_classification="NO_DRIFT", compatible=True, evidence_complete=True,
        profile_digest=str(profile["profile_digest"]),
        reference_profile_digest=str(profile["profile_digest"]),
    )
    cross = classify_from_lrd01d(
        lrd01d_classification="NO_DRIFT", compatible=True, evidence_complete=True,
        profile_digest=str(other["profile_digest"]),
        reference_profile_digest=str(profile["profile_digest"]),
    )
    assert exact is CrossEnvironmentReplayClassification.EXACT_ENVIRONMENT_REPLAY
    assert cross is CrossEnvironmentReplayClassification.CROSS_ENV_SEMANTICALLY_EQUIVALENT
    assert classify_from_lrd01d(
        lrd01d_classification="PRESENTATION_ONLY", compatible=True, evidence_complete=True,
        profile_digest=str(other["profile_digest"]),
        reference_profile_digest=str(profile["profile_digest"]),
    ) is CrossEnvironmentReplayClassification.PRESENTATION_ONLY_DRIFT
    assert classify_from_lrd01d(
        lrd01d_classification="SEMANTIC_DRIFT", compatible=True, evidence_complete=True,
        profile_digest=str(other["profile_digest"]),
        reference_profile_digest=str(profile["profile_digest"]),
    ) is CrossEnvironmentReplayClassification.SEMANTIC_DRIFT
    with pytest.raises(CrossEnvironmentReplayError):
        classify_from_lrd01d(
            lrd01d_classification="IDENTICAL", compatible=True, evidence_complete=True,
            profile_digest=str(profile["profile_digest"]),
        reference_profile_digest=str(profile["profile_digest"]),
        )


def test_python_abi_and_os_mismatch_are_incompatible() -> None:
    observed, profile, _, _ = material()
    assert environment_compatible(profile, observed)
    for key in ("python_soabi", "python_cache_tag", "os_family", "cpu_architecture"):
        altered = copy.deepcopy(observed)
        altered[key] = f"different-{key}"
        altered["observed_environment_digest"] = digest_value(
            {k: v for k, v in altered.items() if k != "observed_environment_digest"}
        )
        assert not environment_compatible(profile, altered)


def test_dependency_inventory_substitution_fails_closed() -> None:
    observed, _, _, _ = material()
    altered = copy.deepcopy(observed)
    cast_inventory = altered["installed_artifacts"]
    assert isinstance(cast_inventory, list)
    cast_inventory.append(
        {
            "name": "evil",
            "version": "1",
            "physical_files_digest": h("evil"),
            "file_count": 1,
        }
    )
    altered["observed_environment_digest"] = digest_value(
        {k: v for k, v in altered.items() if k != "observed_environment_digest"}
    )
    with pytest.raises(CrossEnvironmentReplayError, match="inventory substitution"):
        verify_observed_environment(altered)


@pytest.mark.parametrize("field", [
    "lrd01i_bundle_digest",
    "migration_registry_digest",
    "canonicalization_profile_digest",
    "crypto_profile_digest",
])
def test_critical_profile_substitution_rejected(field: str) -> None:
    observed, profile, _, plan = material()
    changed = copy.deepcopy(profile)
    changed[field] = h(f"substitute-{field}")
    changed["profile_digest"] = digest_value(
        {k: v for k, v in changed.items() if k != "profile_digest"}
    )
    with pytest.raises(CrossEnvironmentReplayError, match="substitution"):
        build_replay_receipt(
            plan=plan, profile=changed, observed=observed, verifier_digest=h("verifier"),
            semantic_result_identity=h("semantic"), invariant_report_identity=h("invariants"),
            lrd01d_classification="NO_DRIFT", execution_status=ReplayExecutionStatus.VERIFIED,
        )


def test_observed_environment_cross_profile_swap_fails_closed() -> None:
    observed, _, other, plan = material()
    with pytest.raises(
        CrossEnvironmentReplayError,
        match="observed-environment/profile substitution",
    ):
        build_replay_receipt(
            plan=plan,
            profile=other,
            observed=observed,
            verifier_digest=h("verifier"),
            semantic_result_identity=h("semantic"),
            invariant_report_identity=h("invariants"),
            lrd01d_classification="NO_DRIFT",
            execution_status=ReplayExecutionStatus.VERIFIED,
        )


def test_unknown_schema_and_unknown_fields_fail() -> None:
    observed, profile, _, _ = material()
    bad_profile = dict(profile)
    bad_profile["unknown"] = True
    with pytest.raises(CrossEnvironmentReplayError, match="fields mismatch"):
        verify_environment_profile(bad_profile)
    bad_observed = dict(observed)
    bad_observed["schema"] = "lukart.observed-environment-receipt.v2"
    bad_observed["observed_environment_digest"] = digest_value(
        {k: v for k, v in bad_observed.items() if k != "observed_environment_digest"}
    )
    with pytest.raises(CrossEnvironmentReplayError, match="unsupported observed"):
        verify_observed_environment(bad_observed)


def test_complete_matrix_report_and_standalone_verifier(tmp_path: Path) -> None:
    observed, profile, other, plan = material()
    # Simulate another environment receipt while keeping its observed provenance
    # independently addressed.
    observed2 = copy.deepcopy(observed)
    observed2["os_build"] = str(observed2["os_build"]) + "-other-runner"
    observed2["declared_profile_digest"] = other["profile_digest"]
    observed2["observed_environment_digest"] = digest_value(
        {k: v for k, v in observed2.items() if k != "observed_environment_digest"}
    )
    # `other` differs only in a declared non-runtime name, so it is compatible
    # but not the reference profile.
    receipt1 = build_replay_receipt(
        plan=plan, profile=profile, observed=observed, verifier_digest=h("verifier"),
        semantic_result_identity=h("semantic"), invariant_report_identity=h("invariants"),
        lrd01d_classification="NO_DRIFT", execution_status=ReplayExecutionStatus.VERIFIED,
    )
    receipt2 = build_replay_receipt(
        plan=plan, profile=other, observed=observed2, verifier_digest=h("verifier"),
        semantic_result_identity=h("semantic"), invariant_report_identity=h("invariants"),
        lrd01d_classification="NO_DRIFT", execution_status=ReplayExecutionStatus.VERIFIED,
    )
    assert receipt1["classification"] == "EXACT_ENVIRONMENT_REPLAY"
    assert receipt2["classification"] == "CROSS_ENV_SEMANTICALLY_EQUIVALENT"
    report = build_replay_report(
        plan=plan,
        profiles=[profile, other],
        observed_environments=[observed, observed2],
        receipts=[receipt1, receipt2],
    )
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    assert verify_file(path, str(report["report_digest"])) == report["report_digest"]


def test_partial_matrix_and_cross_environment_swap_rejected() -> None:
    observed, profile, other, plan = material()
    receipt = build_replay_receipt(
        plan=plan, profile=profile, observed=observed, verifier_digest=h("verifier"),
        semantic_result_identity=h("semantic"), invariant_report_identity=h("invariants"),
        lrd01d_classification="NO_DRIFT", execution_status=ReplayExecutionStatus.VERIFIED,
    )
    with pytest.raises(CrossEnvironmentReplayError, match="partial"):
        build_replay_report(
            plan=plan,
            profiles=[profile, other],
            observed_environments=[observed],
            receipts=[receipt],
        )


def test_tampered_inner_digest_with_pinned_outer_digest_rejected(tmp_path: Path) -> None:
    observed, profile, other, plan = material()
    observed2 = copy.deepcopy(observed)
    observed2["os_build"] = str(observed2["os_build"]) + "-2"
    observed2["declared_profile_digest"] = other["profile_digest"]
    observed2["observed_environment_digest"] = digest_value(
        {k: v for k, v in observed2.items() if k != "observed_environment_digest"}
    )
    receipts = [
        build_replay_receipt(
            plan=plan,
            profile=p,
            observed=o,
            verifier_digest=h("verifier"),
            semantic_result_identity=h("semantic"),
            invariant_report_identity=h("invariants"),
            lrd01d_classification="NO_DRIFT",
            execution_status=ReplayExecutionStatus.VERIFIED,
        )
        for p, o in ((profile, observed), (other, observed2))
    ]
    report = build_replay_report(
        plan=plan,
        profiles=[profile, other],
        observed_environments=[observed, observed2],
        receipts=receipts,
    )
    pinned = str(report["report_digest"])
    raw_receipts = report["receipts"]
    assert isinstance(raw_receipts, list)
    first_receipt = raw_receipts[0]
    assert isinstance(first_receipt, dict)
    first_receipt["semantic_result_identity"] = h("tampered")
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(VerificationError):
        verify_file(path, pinned)


def _write_minimal_oci_layout(root: Path) -> str:
    blobs = root / "blobs" / "sha256"
    blobs.mkdir(parents=True)
    layer_payload = b"synthetic-layer"
    layer_digest = hashlib.sha256(layer_payload).hexdigest()
    (blobs / layer_digest).write_bytes(layer_payload)

    config_payload = json.dumps(
        {
            "architecture": "amd64",
            "os": "linux",
            "config": {"Entrypoint": ["python", "/capsule/verifier.py"]},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    config_digest = hashlib.sha256(config_payload).hexdigest()
    (blobs / config_digest).write_bytes(config_payload)

    manifest_payload = json.dumps(
        {
            "schemaVersion": 2,
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "digest": f"sha256:{config_digest}",
                "size": len(config_payload),
            },
            "layers": [
                {
                    "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                    "digest": f"sha256:{layer_digest}",
                    "size": len(layer_payload),
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    manifest_digest = hashlib.sha256(manifest_payload).hexdigest()
    (blobs / manifest_digest).write_bytes(manifest_payload)
    (root / "oci-layout").write_text(
        '{"imageLayoutVersion":"1.0.0"}', encoding="utf-8"
    )
    (root / "index.json").write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "manifests": [
                    {
                        "mediaType": "application/vnd.oci.image.manifest.v1+json",
                        "digest": f"sha256:{manifest_digest}",
                        "size": len(manifest_payload),
                        "platform": {"os": "linux", "architecture": "amd64"},
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return layer_digest


def test_oci_layout_is_content_addressed_and_tag_independent(tmp_path: Path) -> None:
    from core.cross_environment_replay_v1 import inspect_oci_layout

    root = tmp_path / "oci"
    layer_digest = _write_minimal_oci_layout(root)
    identity = inspect_oci_layout(
        root,
        source_bundle_digest=h("bundle"),
        dependency_identity_digest=h("ssc02"),
        verifier_digest=h("verifier"),
    )
    assert identity["mutable_tag_is_identity_authority"] is False
    assert identity["host_kernel_runtime_cpu_dependency_remains"] is True
    assert identity["platform"] == {"os": "linux", "architecture": "amd64"}
    assert identity["layer_digests"] == [layer_digest]
    assert identity["dependency_identity_digest"] == h("ssc02")
    assert identity["verifier_digest"] == h("verifier")
    assert identity["entrypoint"] == ["python", "/capsule/verifier.py"]


def test_oci_blob_substitution_rejected(tmp_path: Path) -> None:
    from core.cross_environment_replay_v1 import inspect_oci_layout

    root = tmp_path / "oci"
    layer_digest = _write_minimal_oci_layout(root)
    (root / "blobs" / "sha256" / layer_digest).write_bytes(b"different")
    with pytest.raises(CrossEnvironmentReplayError, match="OCI blob digest mismatch"):
        inspect_oci_layout(
            root,
            source_bundle_digest=h("bundle"),
            dependency_identity_digest=h("ssc02"),
            verifier_digest=h("verifier"),
        )


def test_missing_comparison_evidence_is_unverifiable() -> None:
    observed, profile, _, plan = material()
    receipt = build_replay_receipt(
        plan=plan,
        profile=profile,
        observed=observed,
        verifier_digest=h("verifier"),
        semantic_result_identity=None,
        invariant_report_identity=None,
        lrd01d_classification="NO_DRIFT",
        execution_status=ReplayExecutionStatus.VERIFIED,
    )
    assert receipt["classification"] == "UNVERIFIABLE"


def test_verified_incompatible_environment_is_rejected() -> None:
    observed, profile, _, plan = material()
    altered = copy.deepcopy(observed)
    altered["python_soabi"] = "different-abi"
    altered["observed_environment_digest"] = digest_value(
        {k: v for k, v in altered.items() if k != "observed_environment_digest"}
    )
    with pytest.raises(CrossEnvironmentReplayError, match="verified execution contradicts"):
        build_replay_receipt(
            plan=plan,
            profile=profile,
            observed=altered,
            verifier_digest=h("verifier"),
            semantic_result_identity=h("semantic"),
            invariant_report_identity=h("invariants"),
            lrd01d_classification="NO_DRIFT",
            execution_status=ReplayExecutionStatus.VERIFIED,
        )


def test_unknown_field_class_and_missing_coverage_fail_closed() -> None:
    _, profile, _, _ = material()
    bad_class = copy.deepcopy(profile)
    classes = bad_class["field_classes"]
    assert isinstance(classes, dict)
    classes["timezone"] = "MAGIC"
    bad_class["profile_digest"] = digest_value(
        {k: v for k, v in bad_class.items() if k != "profile_digest"}
    )
    with pytest.raises(CrossEnvironmentReplayError, match="unknown environment field class"):
        verify_environment_profile(bad_class)

    missing = copy.deepcopy(profile)
    missing_classes = missing["field_classes"]
    assert isinstance(missing_classes, dict)
    missing_classes.pop("timezone")
    missing["profile_digest"] = digest_value(
        {k: v for k, v in missing.items() if k != "profile_digest"}
    )
    with pytest.raises(CrossEnvironmentReplayError, match="coverage mismatch"):
        verify_environment_profile(missing)


def test_nonsemantic_locale_timezone_variation_does_not_change_semantic_classification() -> None:
    observed, profile, _, plan = material()
    varied = copy.deepcopy(observed)
    varied["locale"] = "C.synthetic"
    varied["timezone"] = "Etc/UTC.synthetic"
    varied["observed_environment_digest"] = digest_value(
        {k: v for k, v in varied.items() if k != "observed_environment_digest"}
    )
    receipt = build_replay_receipt(
        plan=plan,
        profile=profile,
        observed=varied,
        verifier_digest=h("verifier"),
        semantic_result_identity=h("semantic"),
        invariant_report_identity=h("invariants"),
        lrd01d_classification="NO_DRIFT",
        execution_status=ReplayExecutionStatus.VERIFIED,
    )
    assert receipt["classification"] == "EXACT_ENVIRONMENT_REPLAY"


def test_canonical_identity_is_hash_seed_and_mapping_order_independent() -> None:
    left = {"alpha": 1, "beta": 2, "gamma": [3, 4]}
    right = {"gamma": [3, 4], "beta": 2, "alpha": 1}
    assert digest_value(left) == digest_value(right)


def test_report_identity_is_input_enumeration_order_independent() -> None:
    observed, profile, other, plan = material()
    observed2 = copy.deepcopy(observed)
    observed2["declared_profile_digest"] = other["profile_digest"]
    observed2["os_build"] = str(observed2["os_build"]) + "-enumeration"
    observed2["observed_environment_digest"] = digest_value(
        {k: v for k, v in observed2.items() if k != "observed_environment_digest"}
    )
    receipt1 = build_replay_receipt(
        plan=plan,
        profile=profile,
        observed=observed,
        verifier_digest=h("verifier"),
        semantic_result_identity=h("semantic"),
        invariant_report_identity=h("invariants"),
        lrd01d_classification="NO_DRIFT",
        execution_status=ReplayExecutionStatus.VERIFIED,
    )
    receipt2 = build_replay_receipt(
        plan=plan,
        profile=other,
        observed=observed2,
        verifier_digest=h("verifier"),
        semantic_result_identity=h("semantic"),
        invariant_report_identity=h("invariants"),
        lrd01d_classification="NO_DRIFT",
        execution_status=ReplayExecutionStatus.VERIFIED,
    )
    first = build_replay_report(
        plan=plan,
        profiles=[profile, other],
        observed_environments=[observed, observed2],
        receipts=[receipt1, receipt2],
    )
    second = build_replay_report(
        plan=plan,
        profiles=[other, profile],
        observed_environments=[observed2, observed],
        receipts=[receipt2, receipt1],
    )
    assert first == second


def test_valid_enum_field_class_reassignment_is_rejected() -> None:
    _, profile, _, _ = material()
    changed = copy.deepcopy(profile)
    classes = changed["field_classes"]
    assert isinstance(classes, dict)
    classes["os_family"] = "OBSERVED_PROVENANCE"
    changed["profile_digest"] = digest_value(
        {key: value for key, value in changed.items() if key != "profile_digest"}
    )
    with pytest.raises(CrossEnvironmentReplayError, match="field class mapping mismatch"):
        verify_environment_profile(changed)


def test_recomputed_receipt_classification_forgery_is_rejected(tmp_path: Path) -> None:
    observed, profile, other, plan = material()
    observed2 = copy.deepcopy(observed)
    observed2["declared_profile_digest"] = other["profile_digest"]
    observed2["os_build"] = str(observed2["os_build"]) + "-classification-forgery"
    observed2["observed_environment_digest"] = digest_value(
        {key: value for key, value in observed2.items() if key != "observed_environment_digest"}
    )
    receipts = [
        build_replay_receipt(
            plan=plan,
            profile=current_profile,
            observed=current_observed,
            verifier_digest=h("verifier"),
            semantic_result_identity=h("semantic"),
            invariant_report_identity=h("invariants"),
            lrd01d_classification="NO_DRIFT",
            execution_status=ReplayExecutionStatus.VERIFIED,
        )
        for current_profile, current_observed in ((profile, observed), (other, observed2))
    ]
    report = build_replay_report(
        plan=plan,
        profiles=[profile, other],
        observed_environments=[observed, observed2],
        receipts=receipts,
    )
    report_receipts = report["receipts"]
    assert isinstance(report_receipts, list)
    forged = report_receipts[0]
    assert isinstance(forged, dict)
    forged["classification"] = "SEMANTIC_DRIFT"
    forged["receipt_digest"] = digest_value(
        {key: value for key, value in forged.items() if key != "receipt_digest"}
    )
    report["report_digest"] = digest_value(
        {key: value for key, value in report.items() if key != "report_digest"}
    )
    path = tmp_path / "forged.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(VerificationError, match="classification mismatch"):
        verify_file(path, str(report["report_digest"]))
