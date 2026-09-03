from __future__ import annotations

import pytest

from validation.security_privacy import (
    SecurityControl,
    SecurityControlEvidence,
    SecurityPrivacyEvidence,
    SecurityPrivacyGate,
)


def _control(control: SecurityControl, *, passed: bool = True) -> SecurityControlEvidence:
    return SecurityControlEvidence(
        control=control,
        passed=passed,
        report_sha256=control.value[0] * 64,
        evidence_id=f"evidence-{control.value}",
    )


def _all_controls() -> tuple[SecurityControlEvidence, ...]:
    return tuple(_control(control) for control in SecurityControl)


def test_all_independent_security_controls_are_required() -> None:
    evidence = SecurityPrivacyEvidence(
        validated_sha="a" * 40,
        controls=_all_controls(),
    )

    report = SecurityPrivacyGate().evaluate(evidence)

    assert report.passed is True
    assert report.missing_controls == ()
    assert report.failed_controls == ()
    assert len(report.digest()) == 64


def test_missing_auditability_review_cannot_be_inferred_from_other_gates() -> None:
    controls = tuple(
        _control(control)
        for control in SecurityControl
        if control is not SecurityControl.AUDITABILITY_REVIEW
    )
    evidence = SecurityPrivacyEvidence(
        validated_sha="a" * 40,
        controls=controls,
    )

    report = SecurityPrivacyGate().evaluate(evidence)

    assert report.passed is False
    assert report.missing_controls == (SecurityControl.AUDITABILITY_REVIEW,)


def test_any_failed_security_control_blocks_attestation() -> None:
    controls = tuple(
        _control(control, passed=control is not SecurityControl.LOCAL_DATA_BOUNDARY)
        for control in SecurityControl
    )
    evidence = SecurityPrivacyEvidence(
        validated_sha="a" * 40,
        controls=controls,
    )

    report = SecurityPrivacyGate().evaluate(evidence)

    assert report.passed is False
    assert report.failed_controls == (SecurityControl.LOCAL_DATA_BOUNDARY,)


def test_private_case_commit_or_locked_tuning_is_rejected_at_contract_boundary() -> None:
    with pytest.raises(ValueError, match="private Case data"):
        SecurityPrivacyEvidence(
            validated_sha="a" * 40,
            controls=_all_controls(),
            private_case_data_committed=True,
        )

    with pytest.raises(ValueError, match="locked evaluation"):
        SecurityPrivacyEvidence(
            validated_sha="a" * 40,
            controls=_all_controls(),
            locked_evaluation_used_for_tuning=True,
        )
