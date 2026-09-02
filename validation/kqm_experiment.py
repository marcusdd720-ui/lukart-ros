"""Executable fact-extraction experiment against the synthetic KQM corpus."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.fact_extractor import extract_facts
from validation.extraction_quality import CorpusSplit, ExtractionMetrics, build_split
from validation.kqm_runner import KQMRunner

CORPUS_PATH = Path("data/quality/extraction_gold_v1.json")
TAXONOMY_PATH = Path("docs/quality/critical_facts_schema.yaml")


def run_split(runner: KQMRunner, split: CorpusSplit) -> ExtractionMetrics:
    """Run the real extractor on exactly one benchmark split."""

    return runner.run(extract_facts, split)


def run_experiment() -> dict[str, ExtractionMetrics]:
    """Run development and validation without touching the locked evaluation split."""

    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    runner = KQMRunner(CORPUS_PATH, TAXONOMY_PATH)
    return {
        name: run_split(runner, build_split(payload, name))
        for name in ("development", "validation")
    }


def main() -> None:
    for name, metrics in run_experiment().items():
        print(f"[{name}]")
        print(f"  precision={metrics.precision:.6f}")
        print(f"  recall={metrics.recall:.6f}")
        print(f"  f1={metrics.f1:.6f}")
        print(f"  critical_recall={metrics.critical_recall:.6f}")
        print(f"  critical_precision={metrics.critical_precision:.6f}")
        print(f"  critical_fact_loss={metrics.critical_fact_loss}")
        print(
            "  case_number_false_positive_rate="
            f"{metrics.case_number_false_positive_rate:.6f}"
        )
        print(f"  provenance_completeness={metrics.provenance_completeness:.6f}")


if __name__ == "__main__":
    main()
