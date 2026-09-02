"""Ground-truth evaluation primitives for extraction quality experiments.

The evaluator is deliberately independent of any extraction implementation. This keeps
measurement stable while extractors and adapters evolve.
"""

from __future__ import annotations

from collections import Counter
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


def _gold_facts(records: Iterable[Mapping[str, object]]) -> list[GoldFact]:
    facts: list[GoldFact] = []
    for record in records:
        document_id = str(record["document_id"])
        document_type = str(record["document_type"])
        for entity in record["entities"]:
            data = entity  # type narrowed by runtime corpus validation below
            if not isinstance(data, Mapping):
                raise TypeError("gold entity must be an object")
            facts.append(
                GoldFact(
                    document_id=document_id,
                    document_type=document_type,
                    value=str(data["value"]),
                    entity_type=EntityType(str(data["entity_type"])),
                    critical=bool(data["critical"]),
                )
            )
    return facts


def load_corpus_documents(payload: Mapping[str, object]) -> list[GoldFact]:
    """Parse the versioned corpus without depending on a particular JSON library wrapper."""

    if payload.get("schema_version") != "1.0.0":
        raise ValueError("unsupported extraction corpus schema")
    documents = payload.get("documents")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise ValueError("corpus.documents must be a sequence")
    return _gold_facts(documents)  # type: ignore[arg-type]


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

    true_keys = set(gold_map).intersection(predicted_keys)
    false_positive_keys = predicted_keys - set(gold_map)
    false_negative_keys = set(gold_map) - predicted_keys

    tp = len(true_keys)
    fp = len(false_positive_keys)
    fn = len(false_negative_keys)
    precision, recall, f1 = precision_recall_f1(tp, fp, fn)

    critical_keys = {
        key for key, fact in gold_map.items() if fact.critical
    }
    critical_tp = len(true_keys.intersection(critical_keys))
    critical_fn = len(false_negative_keys.intersection(critical_keys))
    critical_fp = len(
        key for key in false_positive_keys if key[1] in {EntityType.CASE_NUMBER.value}
    )
    critical_total = len(critical_keys)
    critical_recall = critical_tp / critical_total if critical_total else 0.0
    critical_precision = critical_tp / (critical_tp + critical_fp) if critical_tp + critical_fp else 0.0

    documents_without_case_number = {
        fact.document_id
        for fact in filtered_gold
        if fact.entity_type is EntityType.CASE_NUMBER
    }
    denominator = 0
    case_fp_documents: set[str] = set()
    all_documents = {fact.document_id for fact in filtered_gold}
    for document_id in all_documents:
        if document_id not in documents_without_case_number:
            denominator += 1

    gold_case_keys = {
        key for key, fact in gold_map.items() if fact.entity_type is EntityType.CASE_NUMBER
    }
    for prediction in prediction_list:
        if prediction.entity_type is not EntityType.CASE_NUMBER:
            continue
        key = fact_key(prediction.source_document_id, prediction.entity_type, prediction.value)
        if key not in gold_case_keys and prediction.source_document_id not in documents_without_case_number:
            case_fp_documents.add(prediction.source_document_id)
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
