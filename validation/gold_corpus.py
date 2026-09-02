"""Validation contracts for the synthetic extraction gold corpus."""

from __future__ import annotations  # noqa: I001

from collections.abc import Mapping, Sequence

from knowledge.provenance import EntityType


EXPECTED_DOCUMENT_TYPES = {
    "wyrok_sadowy",
    "decyzja_zus",
    "umowa",
    "pismo_procesowe",
}
EXPECTED_DOCUMENTS_PER_TYPE = 5
EXPECTED_DOCUMENT_COUNT = 20
EXPECTED_SPLIT_SIZES = {
    "development": 12,
    "validation": 4,
    "locked_evaluation": 4,
}


def _severity_map(document_schema: Mapping[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for severity in ("critical", "important", "ordinary"):
        raw_values = document_schema.get(severity)
        if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
            raise ValueError(f"taxonomy {severity!r} must be a sequence")
        for value in raw_values:
            entity_type = str(value)
            if entity_type in result:
                raise ValueError(f"entity type {entity_type!r} has multiple severities")
            result[entity_type] = severity
    return result


def validate_corpus(
    corpus: Mapping[str, object],
    taxonomy: Mapping[str, object],
) -> None:
    """Fail closed when corpus structure or criticality diverges from taxonomy."""

    if corpus.get("schema_version") != "1.0.0":
        raise ValueError("unsupported extraction corpus schema")
    if taxonomy.get("schema_version") != "1.0.0":
        raise ValueError("unsupported critical-facts schema")
    if corpus.get("status") != "candidate_pending_independent_review":
        raise ValueError("corpus must remain a review-pending candidate until frozen")
    if corpus.get("review_status") != "not_reviewed":
        raise ValueError("synthetic benchmark corpus cannot claim review without evidence")

    documents = corpus.get("documents")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise ValueError("corpus.documents must be a sequence")
    if len(documents) != EXPECTED_DOCUMENT_COUNT:
        raise ValueError("corpus must contain exactly 20 documents")

    taxonomy_document_types = taxonomy.get("document_types")
    if not isinstance(taxonomy_document_types, Mapping):
        raise ValueError("taxonomy.document_types must be an object")
    if set(taxonomy_document_types) != EXPECTED_DOCUMENT_TYPES:
        raise ValueError("taxonomy document types do not match the benchmark contract")

    document_ids: list[str] = []
    counts: dict[str, int] = {name: 0 for name in EXPECTED_DOCUMENT_TYPES}
    severity_by_type: dict[str, dict[str, str]] = {}

    for document_type, schema in taxonomy_document_types.items():
        if not isinstance(schema, Mapping):
            raise ValueError(f"taxonomy for {document_type!r} must be an object")
        severity_by_type[str(document_type)] = _severity_map(schema)

    known_entity_types = {item.value for item in EntityType}
    seen_fact_keys: set[tuple[str, str, str]] = set()

    for raw_document in documents:
        if not isinstance(raw_document, Mapping):
            raise ValueError("corpus document must be an object")

        document_id = str(raw_document.get("document_id", ""))
        document_type = str(raw_document.get("document_type", ""))
        if not document_id.startswith("SYN-"):
            raise ValueError(f"non-synthetic document id: {document_id!r}")
        if document_type not in EXPECTED_DOCUMENT_TYPES:
            raise ValueError(f"unsupported document type: {document_type!r}")

        document_ids.append(document_id)
        counts[document_type] += 1

        raw_entities = raw_document.get("entities")
        if not isinstance(raw_entities, Sequence) or isinstance(raw_entities, (str, bytes)):
            raise ValueError(f"entities missing for {document_id}")

        severity_map = severity_by_type[document_type]
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, Mapping):
                raise ValueError(f"entity must be an object in {document_id}")

            value = str(raw_entity.get("value", ""))
            entity_type = str(raw_entity.get("entity_type", ""))
            critical = raw_entity.get("critical")
            if not value:
                raise ValueError(f"empty entity value in {document_id}")
            if entity_type not in known_entity_types:
                raise ValueError(f"unknown entity type {entity_type!r}")
            if entity_type not in severity_map:
                raise ValueError(
                    f"entity type {entity_type!r} is not covered for {document_type}"
                )
            if not isinstance(critical, bool):
                raise ValueError(f"critical flag must be boolean in {document_id}")

            expected_critical = severity_map[entity_type] == "critical"
            if critical != expected_critical:
                raise ValueError(
                    f"criticality mismatch for {document_id}: "
                    f"{entity_type} expected {expected_critical}, got {critical}"
                )

            key = (document_id, entity_type, value)
            if key in seen_fact_keys:
                raise ValueError(f"duplicate gold fact: {key}")
            seen_fact_keys.add(key)

    if len(set(document_ids)) != EXPECTED_DOCUMENT_COUNT:
        raise ValueError("corpus document ids must be unique")
    if set(counts.values()) != {EXPECTED_DOCUMENTS_PER_TYPE}:
        raise ValueError("corpus must contain five documents of each normative type")

    splits = corpus.get("splits")
    if not isinstance(splits, Mapping):
        raise ValueError("corpus.splits must be an object")

    split_ids: set[str] = set()
    for split_name, expected_size in EXPECTED_SPLIT_SIZES.items():
        raw_ids = splits.get(split_name)
        if not isinstance(raw_ids, Sequence) or isinstance(raw_ids, (str, bytes)):
            raise ValueError(f"split {split_name!r} must be a sequence")
        ids = tuple(str(item) for item in raw_ids)
        if len(ids) != expected_size:
            raise ValueError(f"split {split_name!r} must contain {expected_size} documents")
        if len(set(ids)) != len(ids):
            raise ValueError(f"split {split_name!r} contains duplicate document ids")
        if split_ids.intersection(ids):
            raise ValueError("corpus splits must be disjoint")
        split_ids.update(ids)

    if split_ids != set(document_ids):
        raise ValueError("corpus splits must partition the document set")
