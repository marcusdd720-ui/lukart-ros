"""Ground-truth evaluation primitives for extraction quality experiments."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from knowledge.provenance import EntityType, ExtractedFact


CRITICAL_TYPES_BY_DOCUMENT_TYPE: dict[str, frozenset[EntityType]] = {
    "wyrok_sadowy": frozenset({EntityType.CASE_NUMBER, EntityType.DECISION_OUTCOME, EntityType.LEGAL_BASIS, EntityType.DEADLINE, EntityType.AMOUNT}),
    "decyzja_zus": frozenset({EntityType.DECISION_NUMBER, EntityType.DECISION_OUTCOME, EntityType.BENEFIT_AMOUNT, EntityType.DEADLINE}),
    "umowa": frozenset({EntityType.PARTY, EntityType.DATE, EntityType.AMOUNT}),
    "pismo_procesowe": frozenset({EntityType.CASE_NUMBER, EntityType.PARTY, EntityType.LEGAL_BASIS, EntityType.DEADLINE}),
}


@dataclass(frozen=True, slots=True)
class GoldFact:
    document_id: str
    document_type: str
    value: str
    entity_type: EntityType
    critical: bool


@dataclass(frozen=True, slots=True)
class ExtractionMetrics:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    critical_true_positive: int
    critical_false_positive: int
    critical_false_negative: int
    critical_recall: float
    critical_precision: float
    critical_fact_loss: int
    case_number_false_positive_rate: float
    provenance_completeness: float

    @property
    def complete(self) -> bool:
        return self.provenance_completeness == 1.0


@dataclass(frozen=True, slots=True)
class CorpusSplit:
    name: str
    document_ids: tuple[str, ...]

    def contains(self, document_id: str) -> bool:
        return document_id in self.document_ids


def normalize_value(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return " ".join(normalized.split()).strip()


def fact_key(document_id: str, entity_type: EntityType, value: str) -> tuple[str, str, str]:
    return (document_id, entity_type.value, normalize_value(value))


def precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _gold_facts(records: Sequence[object]) -> list[GoldFact]:
    facts: list[GoldFact] = []
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            raise TypeError("gold document must be an object")
        document_id = str(raw_record["document_id"])
        document_type = str(raw_record["document_type"])
        raw_entities = raw_record.get("entities")
        if not isinstance(raw_entities, Sequence) or isinstance(raw_entities, (str, bytes)):
            raise TypeError("gold document entities must be a sequence")
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, Mapping):
                raise TypeError("gold entity must be an object")
            facts.append(GoldFact(document_id, document_type, str(raw_entity["value"]), EntityType(str(raw_entity["entity_type"])), bool(raw_entity["critical"])))
    return facts


def load_corpus_documents(payload: Mapping[str, object]) -> list[GoldFact]:
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("unsupported extraction corpus schema")
    documents = payload.get("documents")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise ValueError("corpus.documents must be a sequence")
    return _gold_facts(documents)


def build_split(payload: Mapping[str, object], name: str) -> CorpusSplit:
    splits = payload.get("splits")
    if not isinstance(splits, Mapping):
        raise ValueError("corpus.splits must be an object")
    raw_ids = splits.get(name)
    if not isinstance(raw_ids, Sequence) or isinstance(raw_ids, (str, bytes)):
        raise ValueError(f"corpus split {name!r} must be a sequence")
    return CorpusSplit(name, tuple(str(item) for item in raw_ids))


def evaluate(gold: Sequence[GoldFact], predictions: Iterable[ExtractedFact], *, split: CorpusSplit | None = None) -> ExtractionMetrics:
    filtered_gold = [item for item in gold if split is None or split.contains(item.document_id)]
    prediction_list = [item for item in predictions if split is None or split.contains(item.source_document_id)]
    gold_map = {fact_key(item.document_id, item.entity_type, item.value): item for item in filtered_gold}
    predicted_keys = {fact_key(item.source_document_id, item.entity_type, item.value) for item in prediction_list}
    document_types = {item.document_id: item.document_type for item in filtered_gold}

    gold_keys = set(gold_map)
    true_keys = gold_keys & predicted_keys
    false_positive_keys = predicted_keys - gold_keys
    false_negative_keys = gold_keys - predicted_keys
    tp, fp, fn = len(true_keys), len(false_positive_keys), len(false_negative_keys)
    precision, recall, f1 = precision_recall_f1(tp, fp, fn)

    critical_keys = {key for key, item in gold_map.items() if item.critical}
    critical_tp = len(true_keys & critical_keys)
    critical_fn = len(false_negative_keys & critical_keys)
    critical_fp = sum(1 for key in false_positive_keys if key[0] in document_types and EntityType(key[1]) in CRITICAL_TYPES_BY_DOCUMENT_TYPE.get(document_types[key[0]], frozenset()))
    critical_total = len(critical_keys)

    documents_with_case_number = {item.document_id for item in filtered_gold if item.entity_type is EntityType.CASE_NUMBER}
    documents_without_case_number = {item.document_id for item in filtered_gold} - documents_with_case_number
    case_fp_documents = {item.source_document_id for item in prediction_list if item.entity_type is EntityType.CASE_NUMBER and item.source_document_id in documents_without_case_number and fact_key(item.source_document_id, item.entity_type, item.value) not in gold_keys}
    denominator = len(documents_without_case_number)

    usable_predictions = len(prediction_list)
    provenance_complete = (sum(bool(item.source_document_id and item.page >= 1 and item.char_start >= 0 and item.char_end > item.char_start and item.extractor_version) for item in prediction_list) / usable_predictions if usable_predictions else 1.0)
    return ExtractionMetrics(tp, fp, fn, precision, recall, f1, critical_tp, critical_fp, critical_fn, critical_tp / critical_total if critical_total else 0.0, critical_tp / (critical_tp + critical_fp) if critical_tp + critical_fp else 0.0, critical_fn, len(case_fp_documents) / denominator if denominator else 0.0, provenance_complete)
