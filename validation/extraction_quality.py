"""Ground-truth evaluation primitives for extraction quality experiments.

The evaluator is deliberately independent of any extraction implementation. This keeps
measurement stable while extractors and adapters evolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence
import unicodedata

from knowledge.provenance import EntityType, ExtractedFact


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
    """Normalize text only for equality; source spans remain untouched."""

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
            facts.append(
                GoldFact(
                    document_id=document_id,
                    document_type=document_type,
                    value=str(raw_entity["value"]),
                    entity_type=EntityType(str(raw_entity["entity_type"])),
                    critical=bool(raw_entity["critical"]),
                )
            )
    return facts


def load_corpus_documents(payload: Mapping[str, object]) -> list[GoldFact]:
    """Parse the versioned corpus into immutable benchmark facts."""

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
    return CorpusSplit(name=name, document_ids=tuple(str(item) for item in raw_ids))


def evaluate(
    gold: Sequence[GoldFact],
    predictions: Iterable[ExtractedFact],
    *,
    split: CorpusSplit | None = None,
) -> ExtractionMetrics:
    """Evaluate exact fact matches and provenance completeness.

    A prediction matches only when document, entity type and normalized value agree.
    This is intentionally stricter than fuzzy text matching because the benchmark is
    designed to detect legally material value corruption.
    """

    filtered_gold = [fact for fact in gold if split is None or split.contains(fact.document_id)]
    prediction_list = [
        fact for fact in predictions if split is None or split.contains(fact.source_document_id)
    ]

    gold_map = {fact_key(f.document_id, f.entity_type, f.value): f for f in filtered_gold}
    predicted_keys = {
        fact_key(f.source_document_id, f.entity_type, f.value) for f in prediction_list
    }

    gold_keys = set(gold_map)
    true_keys = gold_keys.intersection(predicted_keys)
    false_positive_keys = predicted_keys - gold_keys
    false_negative_keys = gold_keys - predicted_keys

    tp = len(true_keys)
    fp = len(false_positive_keys)
    fn = len(false_negative_keys)
    precision, recall, f1 = precision_recall_f1(tp, fp, fn)

    critical_keys = {key for key, fact in gold_map.items() if fact.critical}
    critical_tp = len(true_keys.intersection(critical_keys))
    critical_fn = len(false_negative_keys.intersection(critical_keys))
    critical_fp = sum(
        1
        for key in false_positive_keys
        if any(
            fact_key(pred.source_document_id, pred.entity_type, pred.value) == key
            and pred.entity_type in {EntityType.CASE_NUMBER, EntityType.DECISION_NUMBER}
            for pred in prediction_list
        )
    )
    critical_total = len(critical_keys)
    critical_recall = critical_tp / critical_total if critical_total else 0.0
    critical_precision = (
        critical_tp / (critical_tp + critical_fp) if critical_tp + critical_fp else 0.0
    )

    documents_with_case_number = {
        fact.document_id for fact in filtered_gold if fact.entity_type is EntityType.CASE_NUMBER
    }
    documents_without_case_number = (
        {fact.document_id for fact in filtered_gold} - documents_with_case_number
    )
    case_fp_documents = {
        prediction.source_document_id
        for prediction in prediction_list
        if prediction.entity_type is EntityType.CASE_NUMBER
        and prediction.source_document_id in documents_without_case_number
        and fact_key(prediction.source_document_id, prediction.entity_type, prediction.value)
        not in gold_keys
    }
    denominator = len(documents_without_case_number)
    case_fpr = len(case_fp_documents) / denominator if denominator else 0.0

    usable_predictions = len(prediction_list)
    provenance_complete = (
        sum(
            bool(
                fact.source_document_id
                and fact.page >= 1
                and fact.char_start >= 0
                and fact.char_end > fact.char_start
                and fact.extractor_version
            )
            for fact in prediction_list
        )
        / usable_predictions
        if usable_predictions
        else 1.0
    )

    return ExtractionMetrics(
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        critical_true_positive=critical_tp,
        critical_false_negative=critical_fn,
        critical_recall=critical_recall,
        critical_precision=critical_precision,
        critical_fact_loss=critical_fn,
        case_number_false_positive_rate=case_fpr,
        provenance_completeness=provenance_complete,
    )
