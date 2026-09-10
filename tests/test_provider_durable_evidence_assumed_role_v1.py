from __future__ import annotations

import pytest

from core.provider_durable_evidence_bundle_v1 import (
    ProviderDurableEvidenceBundleV1Error,
)
from tests.test_provider_durable_evidence_bundle_v1 import _capture


def test_assumed_role_session_binds_to_backing_iam_role() -> None:
    capture = _capture(
        source_policy_arn="arn:aws:iam::account-alpha:role/security/escrow-a",
        source_principal_arn=(
            "arn:aws:sts::account-alpha:assumed-role/escrow-a/provider-drill-session"
        ),
    )

    assert capture.source_credential_scope.policy_source_arn == (
        "arn:aws:iam::account-alpha:role/security/escrow-a"
    )
    assert capture.source_evidence.principal_arn == (
        "arn:aws:sts::account-alpha:assumed-role/escrow-a/provider-drill-session"
    )


@pytest.mark.parametrize(
    "principal_arn",
    [
        "arn:aws:sts::account-beta:assumed-role/escrow-a/provider-drill-session",
        "arn:aws-us-gov:sts::account-alpha:assumed-role/escrow-a/provider-drill-session",
        "arn:aws:sts::account-alpha:assumed-role/different-role/provider-drill-session",
        "arn:aws:sts::account-alpha:assumed-role/escrow-a/provider/drill/session",
        "arn:aws:sts::account-alpha:federated-user/escrow-a",
    ],
)
def test_assumed_role_binding_rejects_identity_ambiguity(principal_arn: str) -> None:
    with pytest.raises(
        ProviderDurableEvidenceBundleV1Error,
        match="policy evidence principal does not match STS storage principal",
    ):
        _capture(
            source_policy_arn="arn:aws:iam::account-alpha:role/security/escrow-a",
            source_principal_arn=principal_arn,
        )
