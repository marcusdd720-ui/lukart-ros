from __future__ import annotations

import json
from pathlib import Path

from core.legal_authority import (
    LEGAL_SOURCE_PROFILE_SCHEMA_V1,
    AuthorityCapability,
    FallbackPolicy,
    LegalSourceProfile,
    PrivacyClass,
    SourceAccessMode,
    SourceClass,
    TemporalCoverage,
)

SCHEMA_PATH = Path("schemas/legal_source_profile_v1.schema.json")


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _profile() -> LegalSourceProfile:
    return LegalSourceProfile(
        source_id="TEST.OFFICIAL",
        jurisdiction="TEST",
        institution="Synthetic Official Institution",
        source_classes=(SourceClass.PRIMARY_PUBLICATION,),
        authority_capabilities=(
            AuthorityCapability.PUBLICATION_IDENTITY,
            AuthorityCapability.NORM_TEXT,
            AuthorityCapability.TEMPORAL_STATUS,
        ),
        privacy_class=PrivacyClass.PUBLIC,
        access_mode=SourceAccessMode.WEB_AND_API,
        canonical_base_uri="https://official.example.test/legal",
        allowed_hosts=("official.example.test",),
        temporal_coverage=TemporalCoverage.EXACT,
        fallback_policy=FallbackPolicy.NONE,
    )


def test_schema_declares_supported_dialect_and_contract_identity() -> None:
    schema = _schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert properties["schema"]["const"] == LEGAL_SOURCE_PROFILE_SCHEMA_V1


def test_python_canonical_shape_matches_required_schema_fields() -> None:
    schema = _schema()
    required = schema["required"]
    assert isinstance(required, list)

    assert set(_profile().canonical_dict()) == set(required)


def test_schema_enums_match_python_contract() -> None:
    properties = _schema()["properties"]
    assert isinstance(properties, dict)

    assert set(properties["source_classes"]["items"]["enum"]) == {
        item.value for item in SourceClass
    }
    assert set(properties["authority_capabilities"]["items"]["enum"]) == {
        item.value for item in AuthorityCapability
    }
    assert set(properties["privacy_class"]["enum"]) == {
        item.value for item in PrivacyClass
    }
    assert set(properties["access_mode"]["enum"]) == {
        item.value for item in SourceAccessMode
    }
    assert set(properties["temporal_coverage"]["enum"]) == {
        item.value for item in TemporalCoverage
    }
    assert set(properties["fallback_policy"]["enum"]) == {
        item.value for item in FallbackPolicy
    }


def test_schema_encodes_fail_closed_fallback_cardinality() -> None:
    schema = _schema()
    rules = schema["allOf"]
    assert isinstance(rules, list)
    rule = rules[0]

    assert rule["if"]["properties"]["fallback_policy"]["const"] == "NONE"
    assert rule["then"]["properties"]["fallback_source_ids"]["maxItems"] == 0
    assert rule["else"]["properties"]["fallback_source_ids"]["minItems"] == 1


def test_schema_rejects_mixed_derived_and_official_source_classes() -> None:
    rules = _schema()["allOf"]
    assert isinstance(rules, list)
    rule = rules[1]

    assert (
        rule["if"]["properties"]["source_classes"]["contains"]["const"]
        == "DERIVED_OPEN_SOURCE"
    )
    assert rule["then"]["properties"]["source_classes"]["maxItems"] == 1
