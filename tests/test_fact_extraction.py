from knowledge.generic_fact_extractor import GenericRegexFactExtractor
from knowledge.provenance import EntityType


def test_extraction_has_complete_provenance_and_source_spans() -> None:
    text = "Sygn. akt ABC-12/34. Data 01.09.2026. Kwota 1 250,00 zł."
    facts = list(GenericRegexFactExtractor()("DOC-1", "example", text))

    assert facts
    assert {fact.entity_type for fact in facts} == {
        EntityType.CASE_NUMBER,
        EntityType.DATE,
        EntityType.AMOUNT,
    }
    assert all(fact.source_document_id == "DOC-1" for fact in facts)
    assert all(fact.source_document_sha256 for fact in facts)
    assert all(fact.extraction_method == "deterministic_regex" for fact in facts)
    assert all(text[fact.char_start : fact.char_end] == fact.value for fact in facts)


def test_extraction_order_is_deterministic() -> None:
    text = "01.09.2026 Sygn. akt ABC-1/2 100,00 PLN 02.09.2026"
    first = list(GenericRegexFactExtractor()("DOC-1", "example", text))
    second = list(GenericRegexFactExtractor()("DOC-1", "example", text))

    assert first == second
