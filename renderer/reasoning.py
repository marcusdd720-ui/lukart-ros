"""Deterministic presentation adapters for structured reasoning results."""

from __future__ import annotations

import json

from reasoning.models import ReasoningRunResult
from renderer.contract import RenderedResult, RendererKind


class JsonReasoningRenderer:
    kind = RendererKind.JSON
    version = "reasoning-json-v1"

    def render(self, result: ReasoningRunResult) -> RenderedResult:
        content = json.dumps(
            result.canonical_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        return RenderedResult(
            kind=self.kind,
            media_type="application/json",
            content=content,
            source_digest=result.digest(),
            renderer_version=self.version,
        )


class MarkdownReasoningRenderer:
    kind = RendererKind.MARKDOWN
    version = "reasoning-markdown-v1"

    def render(self, result: ReasoningRunResult) -> RenderedResult:
        lines = [
            "# LUKART Reasoning Result",
            "",
            f"- Schema: `{result.schema}`",
            f"- Source digest: `{result.digest()}`",
            f"- Outcome: **{result.decision.outcome.value}**",
            f"- Reason: {result.decision.reason}",
        ]
        if result.decision.artifact_id:
            lines.append(f"- Conclusion artifact: `{result.decision.artifact_id}`")

        lines.extend(["", "## Reasoning artifacts", ""])
        for artifact in sorted(result.artifacts, key=lambda item: item.artifact_id):
            evidence = ", ".join(artifact.evidence_refs) or "—"
            supports = ", ".join(artifact.support_ids) or "—"
            lines.extend(
                [
                    f"### {artifact.artifact_id} — {artifact.status.value}",
                    "",
                    artifact.statement,
                    "",
                    f"- Evidence: {evidence}",
                    f"- Supports: {supports}",
                ]
            )
            if artifact.rationale:
                lines.append(f"- Rationale: {artifact.rationale}")
            lines.append("")

        lines.extend(["## Open questions", ""])
        if not result.open_questions:
            lines.append("None.")
        else:
            for question in sorted(result.open_questions, key=lambda item: item.question_id):
                related = ", ".join(question.related_artifact_ids) or "—"
                lines.extend(
                    [
                        f"### {question.question_id}",
                        "",
                        question.question,
                        "",
                        f"- Reason: {question.reason}",
                        f"- Related artifacts: {related}",
                        "",
                    ]
                )

        content = "\n".join(lines).rstrip() + "\n"
        return RenderedResult(
            kind=self.kind,
            media_type="text/markdown; charset=utf-8",
            content=content,
            source_digest=result.digest(),
            renderer_version=self.version,
        )


class EvidenceListRenderer:
    kind = RendererKind.EVIDENCE_LIST
    version = "reasoning-evidence-list-v1"

    def render(self, result: ReasoningRunResult) -> RenderedResult:
        evidence_map: dict[str, dict[str, set[str]]] = {}
        for artifact in result.artifacts:
            for evidence_ref in artifact.evidence_refs:
                entry = evidence_map.setdefault(
                    evidence_ref,
                    {"artifact_ids": set(), "statuses": set()},
                )
                entry["artifact_ids"].add(artifact.artifact_id)
                entry["statuses"].add(artifact.status.value)

        evidence = [
            {
                "evidence_ref": evidence_ref,
                "artifact_ids": sorted(values["artifact_ids"]),
                "statuses": sorted(values["statuses"]),
            }
            for evidence_ref, values in sorted(evidence_map.items())
        ]
        payload = {
            "schema": "lukart.reasoning-evidence-list.v1",
            "source_digest": result.digest(),
            "evidence": evidence,
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        return RenderedResult(
            kind=self.kind,
            media_type="application/vnd.lukart.reasoning-evidence+json",
            content=content,
            source_digest=result.digest(),
            renderer_version=self.version,
        )
