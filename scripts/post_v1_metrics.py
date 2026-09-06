"""Measure Post-v1 cognitive-path performance without turning timing into truth."""

from __future__ import annotations

import json
import resource
import time

from knowledge.epistemic import KnowledgeStatus
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact
from renderer.reasoning import JsonReasoningRenderer
from validation.post_v1_certification import build_replay_identity


def timed(call):
    started = time.perf_counter()
    value = call()
    return value, (time.perf_counter() - started) * 1000.0


def main() -> None:
    fact = ReasoningArtifact(
        artifact_id="PERF-F1",
        statement="Synthetic performance fixture.",
        status=KnowledgeStatus.FACT,
        evidence_refs=("PERF-E1",),
    )
    conclusion = ReasoningArtifact(
        artifact_id="PERF-C1",
        statement="Synthetic performance conclusion.",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=("PERF-F1",),
    )
    engine = ReasoningEngine((fact, conclusion))
    result, reasoning_ms = timed(lambda: engine.evaluate("PERF-C1"))
    rendered, renderer_ms = timed(lambda: JsonReasoningRenderer().render(result))
    replay, replay_ms = timed(
        lambda: build_replay_identity(
            result.canonical_dict(),
            code_sha="runtime-provided-by-ci",
            config_version="1.1.0",
            schema_version=result.schema,
            component_versions=("reasoning-v1", "reasoning-json-v1"),
        )
    )
    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    metrics = {
        "schema": "lukart.performance.v1",
        "reasoning_runtime_ms": reasoning_ms,
        "renderer_runtime_ms": renderer_ms,
        "replay_runtime_ms": replay_ms,
        "end_to_end_latency_ms": reasoning_ms + renderer_ms + replay_ms,
        "full_case_runtime_ms": reasoning_ms + renderer_ms + replay_ms,
        "peak_memory_kb": peak_kb,
        "graph_nodes": len(result.artifacts),
        "reasoning_digest": result.digest(),
        "rendered_source_digest": rendered.source_digest,
        "replay_digest": replay.digest(),
        "policy": "measurement-only; shared-runner timings are not analytical certification",
    }
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
