"""Reproducible runner for Knowledge Quality Model benchmark experiments."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

import yaml

from knowledge.provenance import ExtractedFact
from validation.extraction_quality import (
    CorpusSplit,
    ExtractionMetrics,
    GoldFact,
    evaluate,
    load_corpus_documents,
)
from validation.gold_corpus import validate_corpus


FactExtractor = Callable[[str, str, str], Iterable[ExtractedFact]]


class KQMRunner:
    """Load a versioned corpus, invoke an extractor, and return measured metrics."""

    def __init__(self, corpus_path: Path, taxonomy_path: Path) -> None:
        self.corpus_path = corpus_path
        self.taxonomy_path = taxonomy_path

    def load(self) -> tuple[list[GoldFact], Mapping[str, object]]:
        corpus = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        taxonomy = yaml.safe_load(self.taxonomy_path.read_text(encoding="utf-8"))
        validate_corpus(corpus, taxonomy)
        return load_corpus_documents(corpus), corpus

    def run(
        self,
        extractor: FactExtractor,
        split: CorpusSplit,
    ) -> ExtractionMetrics:
        gold, corpus = self.load()
        documents = corpus["documents"]
        if not isinstance(documents, list):
            raise ValueError("corpus.documents must be a list")

        predictions: list[ExtractedFact] = []
        for document in documents:
            if not isinstance(document, dict):
                raise ValueError("corpus document must be an object")
            document_id = str(document["document_id"])
            if not split.contains(document_id):
                continue
            document_type = str(document["document_type"])
            text = str(document["text"])
            predictions.extend(extractor(document_id, document_type, text))

        return evaluate(gold, predictions, split=split)
