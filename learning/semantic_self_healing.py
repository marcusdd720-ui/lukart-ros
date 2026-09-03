"""Fail-closed semantic self-healing and change-propagation contracts.

This module belongs to the Product/learning layer.  It deliberately does not import or mutate
Factory state.  Its job is to turn measured failures into traceable diagnoses, compute a
bounded revalidation impact, create an ordinary P4 LearningCandidate, and record fresh-SHA
replay/KQM evidence before the existing promotion path may continue.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum

from knowledge.case_replay import CaseReplayRecord, compare_replay
from learning.candidates import candidate_from_failure
from learning.experiment import ExperimentContract
from learning.models import ChangeKind, LearningCandidate, LearningSource, MeasuredFailure
from learning.promotion import PromotionDecision, PromotionStatus

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _required_text(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be blank")
    return normalized


def _require_sha256(name: str, value: str) -> str:
    normalized = _required_text(name, value).lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{name} must be a 64-character SHA-256 digest")
    return normalized


def _require_git_sha(name: str, value: str) -> str:
    normalized = _required_text(name, value).lower()
    if not _GIT_SHA_RE.fullmatch(normalized):
        raise ValueError(f"{name} must be a 40-64 character hexadecimal commit SHA")
    return normalized


def _digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DiagnosisStatus(StrEnum):
    DIAGNOSED = "diagnosed"
    INCONCLUSIVE = "inconclusive"


class RootCauseCategory(StrEnum):
    EVIDENCE = "evidence"
    EXTRACTION = "extraction"
    REASONING = "reasoning"
    RENDERING = "rendering"
    AGENT = "agent"
    RETRIEVAL = "retrieval"
    RULE = "rule"
    MODEL = "model"
    UNKNOWN = "unknown"


class RevalidationMode(StrEnum):
    SELECTIVE = "selective"
    BROAD_REVALIDATION_REQUIRED = "broad_revalidation_required"


class RepairReadinessStatus(StrEnum):
    READY_FOR_EXISTING_PROMOTION = "ready_for_existing_promotion"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True, order=True)
class DiagnosisRule:
    """Curated deterministic mapping from an exact measured failure code to a component."""

    rule_id: str
    source: LearningSource
    failure_code: str
    root_cause: RootCauseCategory
    target_component: str
    rationale: str

    def __post_init__(self) -> None:
        for field_name in ("rule_id", "failure_code", "target_component", "rationale"):
            object.__setattr__(
                self,
                field_name,
                _required_text(field_name, str(getattr(self, field_name))),
            )
        if self.root_cause is RootCauseCategory.UNKNOWN:
            raise ValueError("diagnosis rule cannot assert UNKNOWN as a root cause")


@dataclass(frozen=True, slots=True)
class SemanticFailureDiagnosis:
    """Evidence-bound semantic diagnosis; an inconclusive result never guesses a component."""

    diagnosis_id: str
    failure_digest: str
    status: DiagnosisStatus
    root_cause: RootCauseCategory
    target_component: str | None
    rule_id: str | None
    rationale: str
    evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnosis_id", _required_text("diagnosis_id", self.diagnosis_id))
        object.__setattr__(
            self,
            "failure_digest",
            _require_sha256("failure_digest", self.failure_digest),
        )
        object.__setattr__(self, "rationale", _required_text("rationale", self.rationale))
        evidence = tuple(_require_sha256("evidence_digest", item) for item in self.evidence_digests)
        if not evidence:
            raise ValueError("semantic diagnosis requires evidence digests")
        if len(evidence) != len(set(evidence)):
            raise ValueError("semantic diagnosis evidence digests must be unique")
        object.__setattr__(self, "evidence_digests", evidence)

        if self.status is DiagnosisStatus.DIAGNOSED:
            if self.root_cause is RootCauseCategory.UNKNOWN:
                raise ValueError("diagnosed failure requires a concrete root-cause category")
            if self.target_component is None or not self.target_component.strip():
                raise ValueError("diagnosed failure requires a target component")
            if self.rule_id is None or not self.rule_id.strip():
                raise ValueError("diagnosed failure requires a diagnosis rule id")
            object.__setattr__(self, "target_component", self.target_component.strip())
            object.__setattr__(self, "rule_id", self.rule_id.strip())
        else:
            if self.root_cause is not RootCauseCategory.UNKNOWN:
                raise ValueError("inconclusive diagnosis must preserve UNKNOWN root cause")
            if self.target_component is not None or self.rule_id is not None:
                raise ValueError("inconclusive diagnosis cannot guess a component or rule")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "evidence_digests": list(self.evidence_digests),
            "failure_digest": self.failure_digest,
            "rationale": self.rationale,
            "root_cause": self.root_cause.value,
            "rule_id": self.rule_id,
            "status": self.status.value,
            "target_component": self.target_component,
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())


class SemanticFailureDiagnoser:
    """Exact-rule diagnoser that abstains when no unique semantic mapping exists."""

    def __init__(self, rules: tuple[DiagnosisRule, ...]) -> None:
        rule_ids = [rule.rule_id for rule in rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("diagnosis rule ids must be unique")
        keys = [(rule.source, rule.failure_code) for rule in rules]
        if len(keys) != len(set(keys)):
            raise ValueError("diagnosis rules must be unique by source and failure code")
        self._rules = rules

    def diagnose(
        self,
        failure: MeasuredFailure,
        *,
        additional_evidence_digests: tuple[str, ...] = (),
    ) -> SemanticFailureDiagnosis:
        evidence = tuple(
            sorted(
                {
                    failure.result_digest,
                    failure.report_digest,
                    *(
                        _require_sha256("additional_evidence_digest", item)
                        for item in additional_evidence_digests
                    ),
                }
            )
        )
        matched = tuple(
            rule
            for rule in self._rules
            if rule.source is failure.source and rule.failure_code == failure.code
        )
        failure_digest = failure.digest()

        if not matched:
            seed = f"{failure_digest}:inconclusive".encode()
            return SemanticFailureDiagnosis(
                diagnosis_id=f"DX-{hashlib.sha256(seed).hexdigest()[:16]}",
                failure_digest=failure_digest,
                status=DiagnosisStatus.INCONCLUSIVE,
                root_cause=RootCauseCategory.UNKNOWN,
                target_component=None,
                rule_id=None,
                rationale="no curated semantic diagnosis rule matches this measured failure",
                evidence_digests=evidence,
            )

        rule = matched[0]
        seed = f"{failure_digest}:{rule.rule_id}:{rule.target_component}".encode()
        return SemanticFailureDiagnosis(
            diagnosis_id=f"DX-{hashlib.sha256(seed).hexdigest()[:16]}",
            failure_digest=failure_digest,
            status=DiagnosisStatus.DIAGNOSED,
            root_cause=rule.root_cause,
            target_component=rule.target_component,
            rule_id=rule.rule_id,
            rationale=rule.rationale,
            evidence_digests=evidence,
        )


@dataclass(frozen=True, slots=True, order=True)
class ComponentNode:
    component_id: str
    validators: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_id", _required_text("component_id", self.component_id))
        validators = tuple(item.strip() for item in self.validators)
        if not validators or not all(validators):
            raise ValueError("component requires at least one validator")
        if len(validators) != len(set(validators)):
            raise ValueError("component validators must be unique")
        object.__setattr__(self, "validators", validators)


@dataclass(frozen=True, slots=True, order=True)
class ComponentDependency:
    upstream: str
    downstream: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "upstream", _required_text("upstream", self.upstream))
        object.__setattr__(self, "downstream", _required_text("downstream", self.downstream))
        if self.upstream == self.downstream:
            raise ValueError("component dependency cannot point to itself")


@dataclass(frozen=True, slots=True)
class ComponentDependencyGraph:
    """Explicit semantic dependency graph; selective propagation requires completeness evidence."""

    graph_version: str
    nodes: tuple[ComponentNode, ...]
    dependencies: tuple[ComponentDependency, ...]
    complete: bool
    completeness_evidence_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "graph_version",
            _required_text("graph_version", self.graph_version),
        )
        if not self.nodes:
            raise ValueError("dependency graph requires components")
        node_ids = [node.component_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("dependency graph component ids must be unique")

        edge_pairs = [(edge.upstream, edge.downstream) for edge in self.dependencies]
        if len(edge_pairs) != len(set(edge_pairs)):
            raise ValueError("dependency graph edges must be unique")
        known = set(node_ids)
        for edge in self.dependencies:
            if edge.upstream not in known or edge.downstream not in known:
                raise ValueError("dependency graph edge references an unknown component")
        self._assert_acyclic(known)

        if self.complete:
            if self.completeness_evidence_digest is None:
                raise ValueError("complete dependency graph requires completeness evidence")
            object.__setattr__(
                self,
                "completeness_evidence_digest",
                _require_sha256(
                    "completeness_evidence_digest",
                    self.completeness_evidence_digest,
                ),
            )
        elif self.completeness_evidence_digest is not None:
            object.__setattr__(
                self,
                "completeness_evidence_digest",
                _require_sha256(
                    "completeness_evidence_digest",
                    self.completeness_evidence_digest,
                ),
            )

    def _assert_acyclic(self, known: set[str]) -> None:
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in known}
        for edge in self.dependencies:
            adjacency[edge.upstream].append(edge.downstream)
        state: dict[str, int] = {node_id: 0 for node_id in known}

        def visit(node_id: str) -> None:
            if state[node_id] == 1:
                raise ValueError("dependency graph must be acyclic")
            if state[node_id] == 2:
                return
            state[node_id] = 1
            for downstream in adjacency[node_id]:
                visit(downstream)
            state[node_id] = 2

        for node_id in sorted(known):
            visit(node_id)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "complete": self.complete,
            "completeness_evidence_digest": self.completeness_evidence_digest,
            "dependencies": [asdict(item) for item in sorted(self.dependencies)],
            "graph_version": self.graph_version,
            "nodes": [
                {
                    "component_id": item.component_id,
                    "validators": list(item.validators),
                }
                for item in sorted(self.nodes)
            ],
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())

    def component_ids(self) -> tuple[str, ...]:
        return tuple(sorted(node.component_id for node in self.nodes))

    def validators_for(self, components: tuple[str, ...]) -> tuple[str, ...]:
        wanted = set(components)
        return tuple(
            sorted(
                {
                    validator
                    for node in self.nodes
                    if node.component_id in wanted
                    for validator in node.validators
                }
            )
        )

    def downstream_closure(self, component_id: str) -> tuple[str, ...]:
        if component_id not in set(self.component_ids()):
            raise KeyError(component_id)
        adjacency: dict[str, set[str]] = {
            node_id: set() for node_id in self.component_ids()
        }
        for edge in self.dependencies:
            adjacency[edge.upstream].add(edge.downstream)

        impacted = {component_id}
        pending = [component_id]
        while pending:
            current = pending.pop()
            for downstream in sorted(adjacency[current]):
                if downstream not in impacted:
                    impacted.add(downstream)
                    pending.append(downstream)
        return tuple(sorted(impacted))


@dataclass(frozen=True, slots=True)
class RevalidationPlan:
    diagnosis_digest: str
    dependency_graph_digest: str
    mode: RevalidationMode
    changed_component: str | None
    impacted_components: tuple[str, ...]
    validators: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnosis_digest",
            _require_sha256("diagnosis_digest", self.diagnosis_digest),
        )
        object.__setattr__(
            self,
            "dependency_graph_digest",
            _require_sha256("dependency_graph_digest", self.dependency_graph_digest),
        )
        object.__setattr__(self, "reason", _required_text("reason", self.reason))
        components = tuple(item.strip() for item in self.impacted_components)
        validators = tuple(item.strip() for item in self.validators)
        if not components or not all(components):
            raise ValueError("revalidation plan requires impacted components")
        if not validators or not all(validators):
            raise ValueError("revalidation plan requires validators")
        if len(components) != len(set(components)):
            raise ValueError("impacted components must be unique")
        if len(validators) != len(set(validators)):
            raise ValueError("revalidation validators must be unique")
        object.__setattr__(self, "impacted_components", components)
        object.__setattr__(self, "validators", validators)
        if self.mode is RevalidationMode.SELECTIVE:
            if self.changed_component is None or not self.changed_component.strip():
                raise ValueError("selective revalidation requires a changed component")
            if self.changed_component not in components:
                raise ValueError("changed component must be included in selective impact")
            object.__setattr__(self, "changed_component", self.changed_component.strip())
        elif self.changed_component is not None:
            object.__setattr__(
                self,
                "changed_component",
                _required_text("changed_component", self.changed_component),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "changed_component": self.changed_component,
            "dependency_graph_digest": self.dependency_graph_digest,
            "diagnosis_digest": self.diagnosis_digest,
            "impacted_components": list(self.impacted_components),
            "mode": self.mode.value,
            "reason": self.reason,
            "validators": list(self.validators),
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())


def plan_revalidation(
    diagnosis: SemanticFailureDiagnosis,
    graph: ComponentDependencyGraph,
) -> RevalidationPlan:
    """Choose selective propagation only when diagnosis and graph are both trustworthy."""

    all_components = graph.component_ids()
    all_validators = graph.validators_for(all_components)
    target = diagnosis.target_component

    if diagnosis.status is DiagnosisStatus.INCONCLUSIVE or target is None:
        return RevalidationPlan(
            diagnosis_digest=diagnosis.digest(),
            dependency_graph_digest=graph.digest(),
            mode=RevalidationMode.BROAD_REVALIDATION_REQUIRED,
            changed_component=None,
            impacted_components=all_components,
            validators=all_validators,
            reason="semantic diagnosis is inconclusive; selective propagation is unsafe",
        )

    if target not in set(all_components):
        return RevalidationPlan(
            diagnosis_digest=diagnosis.digest(),
            dependency_graph_digest=graph.digest(),
            mode=RevalidationMode.BROAD_REVALIDATION_REQUIRED,
            changed_component=target,
            impacted_components=all_components,
            validators=all_validators,
            reason="diagnosed component is absent from the dependency graph",
        )

    if not graph.complete:
        return RevalidationPlan(
            diagnosis_digest=diagnosis.digest(),
            dependency_graph_digest=graph.digest(),
            mode=RevalidationMode.BROAD_REVALIDATION_REQUIRED,
            changed_component=target,
            impacted_components=all_components,
            validators=all_validators,
            reason="dependency graph is not completeness-certified",
        )

    impacted = graph.downstream_closure(target)
    return RevalidationPlan(
        diagnosis_digest=diagnosis.digest(),
        dependency_graph_digest=graph.digest(),
        mode=RevalidationMode.SELECTIVE,
        changed_component=target,
        impacted_components=impacted,
        validators=graph.validators_for(impacted),
        reason="complete dependency graph supports selective downstream revalidation",
    )


def repair_candidate_from_diagnosis(
    failure: MeasuredFailure,
    diagnosis: SemanticFailureDiagnosis,
    *,
    change_kind: ChangeKind,
    hypothesis: str,
    success_criteria: tuple[str, ...],
) -> LearningCandidate:
    """Reuse the P4 candidate contract; P6 never invents a parallel repair authority."""

    if diagnosis.failure_digest != failure.digest():
        raise ValueError("semantic diagnosis is not bound to this measured failure")
    if diagnosis.status is not DiagnosisStatus.DIAGNOSED or diagnosis.target_component is None:
        raise ValueError("repair candidate requires a conclusive semantic diagnosis")
    return candidate_from_failure(
        failure,
        target_component=diagnosis.target_component,
        change_kind=change_kind,
        hypothesis=hypothesis,
        success_criteria=success_criteria,
    )


@dataclass(frozen=True, slots=True)
class FreshShaValidationEvidence:
    """Immutable evidence that a repair was replayed and revalidated on a fresh revision."""

    candidate_digest: str
    revalidation_plan_digest: str
    baseline_sha: str
    repair_sha: str
    baseline_replay_fingerprint: str
    repair_replay_fingerprint: str
    replay_drift_fields: tuple[str, ...]
    kqm_result_digest: str
    kqm_report_digest: str
    executed_validators: tuple[str, ...]
    passed_validators: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "candidate_digest",
            "revalidation_plan_digest",
            "baseline_replay_fingerprint",
            "repair_replay_fingerprint",
            "kqm_result_digest",
            "kqm_report_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_sha256(field_name, str(getattr(self, field_name))),
            )
        object.__setattr__(
            self,
            "baseline_sha",
            _require_git_sha("baseline_sha", self.baseline_sha),
        )
        object.__setattr__(
            self,
            "repair_sha",
            _require_git_sha("repair_sha", self.repair_sha),
        )
        if self.baseline_sha == self.repair_sha:
            raise ValueError("repair validation requires a fresh SHA")

        drift = tuple(item.strip() for item in self.replay_drift_fields)
        executed = tuple(item.strip() for item in self.executed_validators)
        passed = tuple(item.strip() for item in self.passed_validators)
        if not all(drift) and drift:
            raise ValueError("replay drift fields cannot be blank")
        if not executed or not all(executed):
            raise ValueError("repair validation requires executed validators")
        if len(drift) != len(set(drift)):
            raise ValueError("replay drift fields must be unique")
        if len(executed) != len(set(executed)):
            raise ValueError("executed validators must be unique")
        if len(passed) != len(set(passed)) or not all(passed):
            raise ValueError("passed validators must be unique and non-blank")
        if not set(passed).issubset(set(executed)):
            raise ValueError("passed validators must be a subset of executed validators")
        object.__setattr__(self, "replay_drift_fields", drift)
        object.__setattr__(self, "executed_validators", executed)
        object.__setattr__(self, "passed_validators", passed)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "baseline_replay_fingerprint": self.baseline_replay_fingerprint,
            "baseline_sha": self.baseline_sha,
            "candidate_digest": self.candidate_digest,
            "executed_validators": list(self.executed_validators),
            "kqm_report_digest": self.kqm_report_digest,
            "kqm_result_digest": self.kqm_result_digest,
            "passed_validators": list(self.passed_validators),
            "repair_replay_fingerprint": self.repair_replay_fingerprint,
            "repair_sha": self.repair_sha,
            "replay_drift_fields": list(self.replay_drift_fields),
            "revalidation_plan_digest": self.revalidation_plan_digest,
        }

    def digest(self) -> str:
        return _digest(self.canonical_dict())


def validation_evidence_from_replays(
    candidate: LearningCandidate,
    plan: RevalidationPlan,
    *,
    baseline_sha: str,
    repair_sha: str,
    baseline_replay: CaseReplayRecord,
    repair_replay: CaseReplayRecord,
    expected_replay_drift_fields: tuple[str, ...],
    kqm_result_digest: str,
    kqm_report_digest: str,
    executed_validators: tuple[str, ...],
    passed_validators: tuple[str, ...],
) -> FreshShaValidationEvidence:
    """Record replay evidence only when revision, impact, and expected drift bindings agree."""

    baseline_revision = _require_git_sha("baseline_sha", baseline_sha)
    repair_revision = _require_git_sha("repair_sha", repair_sha)
    if baseline_revision == repair_revision:
        raise ValueError("repair validation requires a fresh SHA")
    if plan.changed_component != candidate.target_component:
        raise ValueError("revalidation plan is not bound to the candidate target component")
    if baseline_replay.git_commit != baseline_revision:
        raise ValueError("baseline replay is not bound to the baseline SHA")
    if repair_replay.git_commit != repair_revision:
        raise ValueError("repair replay is not bound to the repair SHA")

    comparison = compare_replay(baseline_replay, repair_replay)
    expected = tuple(sorted(item.strip() for item in expected_replay_drift_fields))
    if not all(expected) and expected:
        raise ValueError("expected replay drift fields cannot be blank")
    if len(expected) != len(set(expected)):
        raise ValueError("expected replay drift fields must be unique")
    observed = tuple(sorted(comparison.drift_fields))
    if observed != expected:
        raise ValueError("observed replay drift does not match the declared repair drift")

    executed = tuple(sorted(item.strip() for item in executed_validators))
    if not set(plan.validators).issubset(set(executed)):
        raise ValueError("not all planned validators were executed")

    return FreshShaValidationEvidence(
        candidate_digest=candidate.digest(),
        revalidation_plan_digest=plan.digest(),
        baseline_sha=baseline_revision,
        repair_sha=repair_revision,
        baseline_replay_fingerprint=baseline_replay.fingerprint(),
        repair_replay_fingerprint=repair_replay.fingerprint(),
        replay_drift_fields=observed,
        kqm_result_digest=kqm_result_digest,
        kqm_report_digest=kqm_report_digest,
        executed_validators=executed,
        passed_validators=tuple(sorted(item.strip() for item in passed_validators)),
    )


@dataclass(frozen=True, slots=True)
class RepairReadinessDecision:
    """Readiness artifact only; it does not apply, merge, deploy, or promote a repair."""

    status: RepairReadinessStatus
    reason: str
    candidate_digest: str
    validation_evidence_digest: str
    revalidation_mode: RevalidationMode


class SemanticSelfHealingGate:
    """Final P6 gate that preserves P4 PromotionGate as the promotion authority."""

    def evaluate(
        self,
        candidate: LearningCandidate,
        experiment: ExperimentContract,
        promotion: PromotionDecision,
        plan: RevalidationPlan,
        evidence: FreshShaValidationEvidence,
    ) -> RepairReadinessDecision:
        candidate_digest = candidate.digest()
        evidence_digest = evidence.digest()

        def reject(reason: str) -> RepairReadinessDecision:
            return RepairReadinessDecision(
                status=RepairReadinessStatus.REJECTED,
                reason=reason,
                candidate_digest=candidate_digest,
                validation_evidence_digest=evidence_digest,
                revalidation_mode=plan.mode,
            )

        if experiment.candidate_digest != candidate_digest:
            return reject("experiment is not bound to this repair candidate")
        if experiment.target_component != candidate.target_component:
            return reject("experiment target does not match the repair candidate")
        if promotion.contract_digest != experiment.digest():
            return reject("promotion decision is not bound to this experiment")
        if promotion.status is not PromotionStatus.ELIGIBLE_FOR_PROMOTION:
            return reject("existing P4 PromotionGate did not make the repair eligible")
        if evidence.candidate_digest != candidate_digest:
            return reject("validation evidence is not bound to this repair candidate")
        if evidence.revalidation_plan_digest != plan.digest():
            return reject("validation evidence is not bound to this revalidation plan")
        if plan.changed_component != candidate.target_component:
            return reject("revalidation plan target does not match the repair candidate")
        if experiment.baseline_revision != evidence.baseline_sha:
            return reject("experiment baseline revision does not match fresh-SHA evidence")
        if experiment.candidate_revision != evidence.repair_sha:
            return reject("experiment candidate revision does not match fresh-SHA evidence")
        if not set(plan.validators).issubset(set(evidence.executed_validators)):
            return reject("planned validators were not fully executed")
        if not set(plan.validators).issubset(set(evidence.passed_validators)):
            return reject("one or more planned validators did not pass")

        return RepairReadinessDecision(
            status=RepairReadinessStatus.READY_FOR_EXISTING_PROMOTION,
            reason=(
                "fresh-SHA replay and planned revalidation passed; repair may continue only "
                "through the existing controlled promotion/release path"
            ),
            candidate_digest=candidate_digest,
            validation_evidence_digest=evidence_digest,
            revalidation_mode=plan.mode,
        )
