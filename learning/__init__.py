"""Controlled, measurement-first learning foundation for LUKART ROS."""

from learning.candidates import candidate_from_failure
from learning.experiment import (
    ExperimentContract,
    ExperimentMeasurement,
    ExperimentResult,
    MetricDirection,
    MetricGuardrail,
    contract_for_candidate,
)
from learning.failure_corpus import (
    FailureCorpus,
    LockedLearningSourceError,
    failure_corpus_from_reasoning,
    reasoning_report_digest,
)
from learning.models import (
    ChangeKind,
    LearningCandidate,
    LearningSource,
    MeasuredFailure,
    MetricValue,
)
from learning.promotion import (
    MetricDelta,
    PromotionDecision,
    PromotionGate,
    PromotionStatus,
)
from learning.teaching import (
    AgentTeachingPackage,
    AgentTeachingReleaseGate,
    TeachingApproval,
    TeachingExample,
    TeachingExampleKind,
    TeachingReleaseDecision,
    TeachingReleaseStatus,
    distill_agent_teaching_package,
    failure_teaching_example,
    gold_teaching_example,
    promotion_decision_digest,
)

__all__ = [
    "AgentTeachingPackage",
    "AgentTeachingReleaseGate",
    "ChangeKind",
    "ExperimentContract",
    "ExperimentMeasurement",
    "ExperimentResult",
    "FailureCorpus",
    "LearningCandidate",
    "LearningSource",
    "LockedLearningSourceError",
    "MeasuredFailure",
    "MetricDelta",
    "MetricDirection",
    "MetricGuardrail",
    "MetricValue",
    "PromotionDecision",
    "PromotionGate",
    "PromotionStatus",
    "TeachingApproval",
    "TeachingExample",
    "TeachingExampleKind",
    "TeachingReleaseDecision",
    "TeachingReleaseStatus",
    "candidate_from_failure",
    "contract_for_candidate",
    "distill_agent_teaching_package",
    "failure_corpus_from_reasoning",
    "failure_teaching_example",
    "gold_teaching_example",
    "promotion_decision_digest",
    "reasoning_report_digest",
]
