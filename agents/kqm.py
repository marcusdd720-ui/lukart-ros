"""KQM adapter and vertical-slice runner for controlled fact agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.certification import (
    AgentCertificationReport,
    AgentCertificationThresholds,
    AgentCertifier,
)
from agents.contract import AgentRequest
from agents.reference_fact import REFERENCE_FACT_AGENT_ID, ReferenceFactAgent
from agents.registry import AgentRegistry
from agents.runner import AgentRunner
from knowledge.provenance import ExtractedFact
from validation.extraction_quality import ExtractionMetrics, build_split
from validation.kqm_runner import KQMRunner


class AgentKQMExecutionError(RuntimeError):
    """Raised when an agent cannot produce an accepted KQM prediction artifact."""


class AgentFactExtractorAdapter:
    """Expose a controlled fact agent through the existing KQM extractor interface."""

    def __init__(self, runner: AgentRunner, *, agent_version: str) -> None:
        self.runner = runner
        self.agent_version = agent_version

    def __call__(
        self,
        document_id: str,
        document_type: str,
        text: str,
    ) -> tuple[ExtractedFact, ...]:
        result = self.runner.run(
            REFERENCE_FACT_AGENT_ID,
            self.agent_version,
            AgentRequest(
                schema="lukart.document_text.v1",
                payload={
                    "document_id": document_id,
                    "document_type": document_type,
                    "text": text,
                },
                evidence_types=frozenset({"document_text"}),
            ),
        )
        if not result.accepted or result.artifact is None:
            raise AgentKQMExecutionError("agent KQM execution failed: " + "; ".join(result.errors))

        payload = result.artifact.payload
        if not isinstance(payload, tuple) or not all(
            isinstance(item, ExtractedFact) for item in payload
        ):
            raise AgentKQMExecutionError("agent artifact payload is not ExtractedFact tuple")
        return payload


@dataclass(frozen=True, slots=True)
class AgentKQMVerticalSliceResult:
    corpus_id: str
    corpus_status: str
    review_status: str
    development: ExtractionMetrics
    validation: ExtractionMetrics
    certification: AgentCertificationReport
    locked_split_executed: bool = False


def run_reference_agent_kqm(
    corpus_path: Path,
    taxonomy_path: Path,
    thresholds: AgentCertificationThresholds,
) -> AgentKQMVerticalSliceResult:
    """Measure the reference agent on development/validation without touching locked data."""

    kqm = KQMRunner(corpus_path, taxonomy_path)
    _, corpus = kqm.load()
    development_split = build_split(corpus, "development")
    validation_split = build_split(corpus, "validation")

    registry = AgentRegistry()
    agent = ReferenceFactAgent()
    registry.register(agent)
    adapter = AgentFactExtractorAdapter(
        AgentRunner(registry), agent_version=agent.contract.version
    )

    development_metrics = kqm.run(adapter, development_split)
    validation_metrics = kqm.run(adapter, validation_split)
    corpus_id = str(corpus.get("corpus_id", "unknown"))

    certification = AgentCertifier(thresholds).evaluate(
        agent.contract,
        validation_metrics,
        corpus_version=corpus_id,
        split_name=validation_split.name,
    )

    return AgentKQMVerticalSliceResult(
        corpus_id=corpus_id,
        corpus_status=str(corpus.get("status", "unknown")),
        review_status=str(corpus.get("review_status", "unknown")),
        development=development_metrics,
        validation=validation_metrics,
        certification=certification,
    )
