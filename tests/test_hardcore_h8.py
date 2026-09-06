from __future__ import annotations

from core.p3.scale import (
    ScaleProfile,
    StructuralScaleBudget,
    certify_profile_structure,
    measure_scale_profile,
    repeated_measurement_digest,
)


def _budget() -> StructuralScaleBudget:
    return StructuralScaleBudget(
        max_evidence_count=4096,
        max_graph_nodes=4096,
        max_replay_count=128,
        max_concurrency=8,
        max_blast_radius_size=4097,
    )


def test_h8_small_profile_is_structurally_within_budget() -> None:
    profile = ScaleProfile("small", 64, 64, 8, 2)
    certification = certify_profile_structure(profile, _budget())
    assert certification.passed is True
    assert certification.failures == ()
    assert len(certification.profile_digest) == 64
    assert len(certification.budget_digest) == 64


def test_h8_concurrency_breach_fails_closed() -> None:
    profile = ScaleProfile("too-wide", 64, 64, 8, 9)
    certification = certify_profile_structure(profile, _budget())
    assert certification.passed is False
    assert "concurrency" in certification.failures


def test_h8_resource_count_breaches_are_explicit() -> None:
    profile = ScaleProfile("oversized", 4097, 4097, 129, 8)
    certification = certify_profile_structure(profile, _budget())
    assert certification.passed is False
    assert set(certification.failures) == {
        "evidence_count",
        "graph_nodes",
        "replay_count",
        "blast_radius_budget",
    }


def test_h8_blast_radius_identity_mismatch_is_rejected() -> None:
    profile = ScaleProfile("graph", 128, 128, 8, 4)
    certification = certify_profile_structure(
        profile,
        _budget(),
        blast_radius_size=127,
    )
    assert certification.passed is False
    assert certification.failures == ("blast_radius_identity",)


def test_h8_same_work_produces_same_digest_across_concurrency_levels() -> None:
    serial = ScaleProfile("identity", 128, 128, 32, 1)
    parallel = ScaleProfile("identity", 128, 128, 32, 8)
    serial_measurement = measure_scale_profile(serial)
    parallel_measurement = measure_scale_profile(parallel)
    assert serial_measurement.work_digest == parallel_measurement.work_digest
    assert serial_measurement.blast_radius_size == 129
    assert parallel_measurement.blast_radius_size == 129


def test_h8_repeated_measurement_work_identity_is_deterministic() -> None:
    profile = ScaleProfile("repeat", 96, 96, 16, 4)
    digests = repeated_measurement_digest(
        lambda: measure_scale_profile(profile),
        repetitions=3,
    )
    assert len(set(digests)) == 1
