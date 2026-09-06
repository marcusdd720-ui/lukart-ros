"""P3-01 semantic change graph and deterministic blast-radius planning."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.p2.semantic import SemanticDiff, semantic_diff
from knowledge.graph import KnowledgeGraph
from reasoning.models import ReasoningRunResult

from .contracts import P3ContractError, content_digest, require_unique_nonblank


@dataclass(frozen=True, slots=True)
class DependencyPath:
    changed_id: str
    affected_id: str
    path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RevalidationPlan:
    changed_ids: tuple[str, ...]
    affected_ids: tuple[str, ...]
    paths: tuple[DependencyPath, ...]
    graph_digest: str

    @property
    def replay_ids(self) -> tuple[str, ...]:
        return self.affected_ids


class SemanticChangeGraph:
    """Explicit dependency graph where an artifact depends on prerequisites.

    The graph intentionally does not infer edge meaning. Callers must project
    Product/Knowledge edges into the dependency contract explicitly.
    """

    def __init__(self, dependencies: Mapping[str, Sequence[str]]) -> None:
        normalized: dict[str, tuple[str, ...]] = {}
        known: set[str] = set()
        for artifact_id, prerequisites in dependencies.items():
            key = artifact_id.strip()
            if not key:
                raise P3ContractError("dependency artifact id cannot be blank")
            refs = require_unique_nonblank(prerequisites, field_name="prerequisites")
            if key in refs:
                raise P3ContractError(f"self dependency is forbidden: {key}")
            normalized[key] = tuple(sorted(refs))
            known.add(key)
            known.update(refs)
        for artifact_id in known:
            normalized.setdefault(artifact_id, ())
        self._dependencies = dict(sorted(normalized.items()))
        self._reverse = self._build_reverse()

    def _build_reverse(self) -> dict[str, tuple[str, ...]]:
        reverse: dict[str, set[str]] = {key: set() for key in self._dependencies}
        for dependent, prerequisites in self._dependencies.items():
            for prerequisite in prerequisites:
                reverse.setdefault(prerequisite, set()).add(dependent)
        return {key: tuple(sorted(values)) for key, values in sorted(reverse.items())}

    @property
    def dependencies(self) -> Mapping[str, tuple[str, ...]]:
        return dict(self._dependencies)

    def digest(self) -> str:
        return content_digest(self._dependencies)

    def validate_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                raise P3ContractError(f"dependency cycle detected at {node}")
            visiting.add(node)
            for prerequisite in self._dependencies[node]:
                visit(prerequisite)
            visiting.remove(node)
            visited.add(node)

        for artifact_id in sorted(self._dependencies):
            visit(artifact_id)

    def plan(self, changed_ids: Sequence[str]) -> RevalidationPlan:
        changed = tuple(
            sorted(set(require_unique_nonblank(changed_ids, field_name="changed_ids")))
        )
        unknown = tuple(item for item in changed if item not in self._dependencies)
        if unknown:
            raise P3ContractError(f"unknown changed artifacts: {', '.join(unknown)}")

        best_paths: dict[tuple[str, str], tuple[str, ...]] = {}
        affected: set[str] = set()
        for root in changed:
            queue: deque[tuple[str, tuple[str, ...]]] = deque([(root, (root,))])
            seen: set[str] = set()
            while queue:
                current, path = queue.popleft()
                if current in seen:
                    continue
                seen.add(current)
                affected.add(current)
                best_paths[(root, current)] = path
                for dependent in self._reverse.get(current, ()):
                    if dependent not in seen:
                        queue.append((dependent, (*path, dependent)))

        paths = tuple(
            DependencyPath(changed_id=root, affected_id=affected_id, path=path)
            for (root, affected_id), path in sorted(best_paths.items())
        )
        return RevalidationPlan(
            changed_ids=changed,
            affected_ids=tuple(sorted(affected)),
            paths=paths,
            graph_digest=self.digest(),
        )

    @classmethod
    def from_reasoning(cls, result: ReasoningRunResult) -> SemanticChangeGraph:
        artifact_ids = {artifact.artifact_id for artifact in result.artifacts}
        if len(artifact_ids) != len(result.artifacts):
            raise P3ContractError("duplicate reasoning artifact ids")

        dependencies: dict[str, tuple[str, ...]] = {}
        for artifact in result.artifacts:
            missing_support = sorted(set(artifact.support_ids) - artifact_ids)
            if missing_support:
                raise P3ContractError(
                    "dangling reasoning support references: " + ",".join(missing_support)
                )
            dependencies[artifact.artifact_id] = tuple(
                sorted(set((*artifact.support_ids, *artifact.evidence_refs)))
            )

        for evidence_ref in {
            ref for artifact in result.artifacts for ref in artifact.evidence_refs
        }:
            dependencies.setdefault(evidence_ref, ())

        if result.decision.artifact_id and result.decision.artifact_id not in artifact_ids:
            raise P3ContractError("decision references unknown reasoning artifact")

        questions_by_id = {question.question_id: question for question in result.open_questions}
        if len(questions_by_id) != len(result.open_questions):
            raise P3ContractError("duplicate open question ids")
        missing_questions = sorted(
            set(result.decision.open_question_ids) - set(questions_by_id)
        )
        if missing_questions:
            raise P3ContractError(
                "decision references unknown open questions: " + ",".join(missing_questions)
            )

        decision_dependencies: list[str] = []
        if result.decision.artifact_id:
            decision_dependencies.append(result.decision.artifact_id)
        decision_dependencies.extend(
            f"@question:{question_id}" for question_id in result.decision.open_question_ids
        )
        dependencies["@decision"] = tuple(sorted(set(decision_dependencies)))

        for question in result.open_questions:
            missing_related = sorted(set(question.related_artifact_ids) - artifact_ids)
            if missing_related:
                raise P3ContractError(
                    "open question references unknown artifacts: "
                    + ",".join(missing_related)
                )
            question_id = f"@question:{question.question_id}"
            dependencies[question_id] = tuple(sorted(question.related_artifact_ids))

        graph = cls(dependencies)
        graph.validate_acyclic()
        return graph

    @classmethod
    def from_knowledge_graph(
        cls,
        graph: KnowledgeGraph,
        *,
        source_depends_on_target: bool,
    ) -> SemanticChangeGraph:
        """Project a KnowledgeGraph only with an explicit edge-orientation contract."""

        dependencies: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
        for edge in graph.edges:
            dependent = edge.source if source_depends_on_target else edge.target
            prerequisite = edge.target if source_depends_on_target else edge.source
            dependencies.setdefault(dependent, []).append(prerequisite)
            dependencies.setdefault(prerequisite, [])
        projected = cls(dependencies)
        projected.validate_acyclic()
        return projected


def compare_semantic_artifacts(
    before: Mapping[str, object], after: Mapping[str, object]
) -> SemanticDiff:
    """Reuse the single P2 semantic-diff authority; P3 never forks its semantics."""

    return semantic_diff(before, after)
