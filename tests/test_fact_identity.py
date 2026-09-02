from knowledge.fact_identity import (
    FactIdentity,
    FactIdentityConflict,
    deduplicate_facts,
    duplicate_count,
)
from knowledge.provenance import EntityType, ExtractedFact


_SHA = "a" * 64


def make_fact(
    *,
    value: str = "SYN-CASE-001/26",
    entity_type: EntityType = EntityType.CASE_NUMBER,
    document_id: str = "doc-1",
    page: int = 1,
    start: int = 0,
    end: int = 15,
    extractor_version: str = "regex-kqm-v1",
    sha: str = _SHA,
    method: str = "deterministic_regex",
) -> ExtractedFact:
    return ExtractedFact(
        value=value,
        entity_type=entity_type,
        source_document_id=document_id,
        page=page,
        char_start=start,
        char_end=end,
        extractor_version=extractor_version,
        source_document_sha256=sha,
        extraction_method=method,
    )


def test_identity_uses_source_span_and_entity_type():
    fact = make_fact()

    identity = FactIdentity.from_fact(fact)

    assert identity.as_key() == ("doc-1", "CASE_NUMBER", 1, 0, 15)


def test_same_source_span_is_deduplicated_across_extractor_versions():
    first = make_fact(extractor_version="regex-kqm-v1")
    second = make_fact(extractor_version="regex-kqm-v2")

    result = deduplicate_facts([second, first])

    assert result == [first]
    assert duplicate_count([second, first]) == 1


def test_same_value_at_different_spans_remains_distinct():
    first = make_fact(start=0, end=15)
    second = make_fact(start=20, end=35)

    result = deduplicate_facts([first, second])

    assert len(result) == 2
    assert duplicate_count([first, second]) == 0


def test_same_span_with_different_entity_type_remains_distinct():
    first = make_fact(entity_type=EntityType.CASE_NUMBER)
    second = make_fact(entity_type=EntityType.DECISION_NUMBER)

    result = deduplicate_facts([first, second])

    assert len(result) == 2


def test_conflicting_values_at_same_identity_fail_closed():
    first = make_fact(value="SYN-CASE-001/26")
    second = make_fact(value="SYN-CASE-002/26")

    try:
        deduplicate_facts([first, second])
    except FactIdentityConflict as exc:
        assert "conflicting facts share identity" in str(exc)
    else:
        raise AssertionError("expected FactIdentityConflict")


def test_conflicting_source_hash_at_same_identity_fails_closed():
    first = make_fact(sha="a" * 64)
    second = make_fact(sha="b" * 64)

    try:
        deduplicate_facts([first, second])
    except FactIdentityConflict:
        pass
    else:
        raise AssertionError("expected FactIdentityConflict")


def test_order_of_input_does_not_change_output():
    first = make_fact(start=20, end=35)
    second = make_fact(start=0, end=15)

    assert deduplicate_facts([first, second]) == deduplicate_facts([second, first])
