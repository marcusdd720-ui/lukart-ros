"""PHX-02 immutable Gold Corpus and KQM evaluation contracts.

Evaluation is deliberately modeled as immutable input identity plus deterministic
projection.  This module has no persistence or Product-state mutation capability.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import cast

from core.case_ledger.contracts import (
    CANONICALIZATION_PROFILE_V1,
    CanonicalizationProfile,
    CaseId,
    ContentAddress,
    DigestAlgorithm,
)
from core.p3.contracts import P3ContractError, RuntimeIdentity, require_hex_digest

GOLD_CORPUS_IDENTITY_SCHEMA_V2 = "lukart.gold-corpus-identity.v2"
KQM_POLICY_SCHEMA_V2 = "lukart.kqm-policy.v2"
EVALUATOR_IDENTITY_SCHEMA_V1 = "lukart.evaluator-identity.v1"
EVALUATION_INPUT_IDENTITY_SCHEMA_V1 = "lukart.evaluation-input-identity.v1"
KQM_PROJECTION_SCHEMA_V2 = "lukart.kqm-projection.v2"

_SUPPORTED_GOLD_CORPUS_SCHEMA = "lukart.gold-corpus.v1"
_SUPPORTED_GOLD_MANIFEST_SCHEMA = "lukart.corpus-manifest.v1"
_PENDING_REVIEW = "candidate_pending_independent_freeze"
_CANDIDATE_STATUS = "candidate"
_LOCKED_POLICY = "certification_only_no_tuning"


class EvaluationContractError(P3ContractError):
    """Fail-closed violation of an evaluation identity or policy contract."""


class GoldSplit(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    LOCKED_EVALUATION = "locked_evaluation"


class EvaluationPurpose(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    CERTIFICATION = "certification"


class MetricDirection(StrEnum):
    MIN = "min"
    MAX = "max"


def _require_identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise EvaluationContractError(f"{field_name} must be nonblank and already canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise EvaluationContractError(f"{field_name} cannot contain control characters")
    return value


def _require_git_sha(value: str, *, field_name: str) -> str:
    normalized = _require_identifier(value, field_name=field_name)
    if len(normalized) != 40:
        raise EvaluationContractError(f"{field_name} must be a 40-character Git SHA")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise EvaluationContractError(f"{field_name} must be hexadecimal") from exc
    if normalized != normalized.lower():
        raise EvaluationContractError(f"{field_name} must use lowercase hexadecimal")
    return normalized


def _mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise EvaluationContractError(f"{field_name} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise EvaluationContractError(f"{field_name} keys must be strings")
    return cast(Mapping[str, object], value)


def _sequence(value: object, *, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise EvaluationContractError(f"{field_name} must be a sequence")
    return cast(Sequence[object], value)


def _finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise EvaluationContractError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise EvaluationContractError(f"{field_name} must be finite")
    return result


def _content_address_from_hex(value: str, *, field_name: str) -> ContentAddress:
    try:
        digest = require_hex_digest(value, field_name=field_name)
    except P3ContractError as exc:
        raise EvaluationContractError(str(exc)) from exc
    return ContentAddress(algorithm=DigestAlgorithm.SHA256, digest=digest)


def _address_from_mapping(value: object, *, field_name: str) -> ContentAddress:
    raw = _mapping(value, field_name=field_name)
    try:
        return ContentAddress.from_dict(raw)
    except P3ContractError as exc:
        raise EvaluationContractError(str(exc)) from exc


def _profile(value: str) -> CanonicalizationProfile:
    try:
        return CanonicalizationProfile(value)
    except ValueError as exc:
        raise EvaluationContractError(f"unsupported canonicalization profile: {value}") from exc


def _freeze_metrics(value: Mapping[str, MetricSpec]) -> Mapping[str, MetricSpec]:
    return MappingProxyType(dict(sorted(value.items())))


def _freeze_numbers(value: Mapping[str, float]) -> Mapping[str, float]:
    return MappingProxyType(dict(sorted(value.items())))


@dataclass(frozen=True, slots=True)
class GoldCorpusIdentity:
    corpus_id: str
    corpus_version: str
    source_digest: ContentAddress
    canonical_content_digest: ContentAddress
    manifest_digest: ContentAddress
    baseline_release: str
    baseline_sha: str
    privacy: str
    split_case_ids: Mapping[GoldSplit, tuple[str, ...]]
    locked_evaluation_policy: str
    review_status: str
    reviewer: str | None
    corpus_identity: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = GOLD_CORPUS_IDENTITY_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != GOLD_CORPUS_IDENTITY_SCHEMA_V2:
            raise EvaluationContractError(f"unsupported Gold identity schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise EvaluationContractError(
                f"unsupported canonicalization profile: {self.canonicalization_profile}"
            )
        object.__setattr__(
            self,
            "corpus_id",
            _require_identifier(self.corpus_id, field_name="corpus_id"),
        )
        object.__setattr__(
            self,
            "corpus_version",
            _require_identifier(self.corpus_version, field_name="corpus_version"),
        )
        object.__setattr__(
            self,
            "baseline_release",
            _require_identifier(self.baseline_release, field_name="baseline_release"),
        )
        object.__setattr__(
            self,
            "baseline_sha",
            _require_git_sha(self.baseline_sha, field_name="baseline_sha"),
        )
        object.__setattr__(
            self,
            "privacy",
            _require_identifier(self.privacy, field_name="privacy"),
        )
        object.__setattr__(
            self,
            "locked_evaluation_policy",
            _require_identifier(
                self.locked_evaluation_policy,
                field_name="locked_evaluation_policy",
            ),
        )
        if self.locked_evaluation_policy != _LOCKED_POLICY:
            raise EvaluationContractError("unsupported locked evaluation policy")
        if self.review_status != _PENDING_REVIEW or self.reviewer is not None:
            raise EvaluationContractError(
                "Gold v2 cannot claim independent freeze without externally verified evidence"
            )
        expected_splits = set(GoldSplit)
        if set(self.split_case_ids) != expected_splits:
            raise EvaluationContractError("Gold identity must contain all exact split memberships")
        normalized: dict[GoldSplit, tuple[str, ...]] = {}
        all_ids: set[str] = set()
        for split in GoldSplit:
            values = self.split_case_ids[split]
            if not values:
                raise EvaluationContractError(f"Gold split {split.value} cannot be empty")
            canonical_ids = tuple(
                _require_identifier(item, field_name=f"{split.value} case_id") for item in values
            )
            if tuple(sorted(canonical_ids)) != canonical_ids:
                raise EvaluationContractError("Gold split case ids must be sorted canonically")
            if len(set(canonical_ids)) != len(canonical_ids):
                raise EvaluationContractError("Gold split case ids cannot contain duplicates")
            if all_ids.intersection(canonical_ids):
                raise EvaluationContractError("Gold split memberships must be disjoint")
            all_ids.update(canonical_ids)
            normalized[split] = canonical_ids
        object.__setattr__(self, "split_case_ids", MappingProxyType(normalized))
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        corpus: Mapping[str, object],
        manifest: Mapping[str, object],
        source_digest: str,
    ) -> GoldCorpusIdentity:
        corpus_schema = corpus.get("schema")
        manifest_schema = manifest.get("schema")
        if corpus_schema != _SUPPORTED_GOLD_CORPUS_SCHEMA:
            raise EvaluationContractError(f"unsupported Gold corpus schema: {corpus_schema}")
        if manifest_schema != _SUPPORTED_GOLD_MANIFEST_SCHEMA:
            raise EvaluationContractError(f"unsupported Gold manifest schema: {manifest_schema}")
        if corpus.get("status") != _CANDIDATE_STATUS:
            raise EvaluationContractError("Gold corpus must remain a candidate")
        if manifest.get("review_status") != _PENDING_REVIEW or manifest.get("reviewer") is not None:
            raise EvaluationContractError(
                "Gold manifest cannot claim independent freeze without external evidence"
            )

        corpus_id = _require_identifier(str(corpus.get("corpus_id", "")), field_name="corpus_id")
        version = _require_identifier(str(corpus.get("version", "")), field_name="corpus_version")
        if manifest.get("corpus_id") != corpus_id or manifest.get("corpus_version") != version:
            raise EvaluationContractError("Gold manifest identity does not match corpus")

        baseline_release = _require_identifier(
            str(corpus.get("baseline_release", "")),
            field_name="baseline_release",
        )
        baseline_sha = _require_git_sha(str(corpus.get("baseline_sha", "")), field_name="baseline_sha")
        if (
            manifest.get("baseline_release") != baseline_release
            or manifest.get("baseline_sha") != baseline_sha
        ):
            raise EvaluationContractError("Gold manifest baseline does not match corpus")
        privacy = _require_identifier(str(corpus.get("privacy", "")), field_name="privacy")
        if manifest.get("privacy") != privacy:
            raise EvaluationContractError("Gold manifest privacy does not match corpus")

        declared_source = manifest.get("corpus_sha256")
        if not isinstance(declared_source, str):
            raise EvaluationContractError("Gold manifest corpus_sha256 is required")
        source_address = _content_address_from_hex(source_digest, field_name="source_digest")
        declared_address = _content_address_from_hex(
            declared_source,
            field_name="manifest corpus_sha256",
        )
        if source_address != declared_address:
            raise EvaluationContractError("Gold corpus raw-file digest mismatch")

        cases = _sequence(corpus.get("cases"), field_name="Gold cases")
        split_members: dict[GoldSplit, list[str]] = {split: [] for split in GoldSplit}
        seen: set[str] = set()
        for raw_case in cases:
            case = _mapping(raw_case, field_name="Gold case")
            case_id = _require_identifier(str(case.get("case_id", "")), field_name="case_id")
            if case_id in seen:
                raise EvaluationContractError(f"duplicate Gold case_id: {case_id}")
            seen.add(case_id)
            try:
                split = GoldSplit(str(case.get("split", "")))
            except ValueError as exc:
                raise EvaluationContractError(
                    f"unsupported Gold split: {case.get('split')}"
                ) from exc
            split_members[split].append(case_id)

        declared_counts = _mapping(manifest.get("splits"), field_name="manifest splits")
        normalized_splits: dict[GoldSplit, tuple[str, ...]] = {}
        for split in GoldSplit:
            declared_count = declared_counts.get(split.value)
            if not isinstance(declared_count, int) or isinstance(declared_count, bool):
                raise EvaluationContractError(f"manifest split count invalid: {split.value}")
            members = tuple(sorted(split_members[split]))
            if declared_count != len(members):
                raise EvaluationContractError(f"Gold split count mismatch: {split.value}")
            normalized_splits[split] = members

        manifest_case_ids = _sequence(manifest.get("case_ids"), field_name="manifest case_ids")
        declared_ids = tuple(str(item) for item in manifest_case_ids)
        if len(set(declared_ids)) != len(declared_ids):
            raise EvaluationContractError("manifest case_ids cannot contain duplicates")
        if set(declared_ids) != seen:
            raise EvaluationContractError("manifest case_ids do not exactly match Gold corpus")

        locked_policy = str(manifest.get("locked_evaluation_policy", ""))
        body = {
            "schema": GOLD_CORPUS_IDENTITY_SCHEMA_V2,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "corpus_id": corpus_id,
            "corpus_version": version,
            "source_digest": source_address.canonical_dict(),
            "canonical_content_digest": ContentAddress.for_value(corpus).canonical_dict(),
            "manifest_digest": ContentAddress.for_value(manifest).canonical_dict(),
            "baseline_release": baseline_release,
            "baseline_sha": baseline_sha,
            "privacy": privacy,
            "split_case_ids": {
                split.value: list(normalized_splits[split]) for split in GoldSplit
            },
            "locked_evaluation_policy": locked_policy,
            "review_status": str(manifest.get("review_status", "")),
            "reviewer": None,
        }
        return cls(
            corpus_id=corpus_id,
            corpus_version=version,
            source_digest=source_address,
            canonical_content_digest=ContentAddress.for_value(corpus),
            manifest_digest=ContentAddress.for_value(manifest),
            baseline_release=baseline_release,
            baseline_sha=baseline_sha,
            privacy=privacy,
            split_case_ids=normalized_splits,
            locked_evaluation_policy=locked_policy,
            review_status=str(manifest.get("review_status", "")),
            reviewer=None,
            corpus_identity=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> GoldCorpusIdentity:
        schema = value.get("schema")
        profile = value.get("canonicalization_profile")
        split_value = _mapping(value.get("split_case_ids"), field_name="split_case_ids")
        if not isinstance(schema, str) or not isinstance(profile, str):
            raise EvaluationContractError("Gold identity schema/profile are required")
        splits: dict[GoldSplit, tuple[str, ...]] = {}
        for raw_name, raw_ids in split_value.items():
            try:
                split = GoldSplit(raw_name)
            except ValueError as exc:
                raise EvaluationContractError(f"unsupported Gold split: {raw_name}") from exc
            splits[split] = tuple(
                str(item) for item in _sequence(raw_ids, field_name=f"{raw_name} case ids")
            )
        reviewer = value.get("reviewer")
        if reviewer is not None and not isinstance(reviewer, str):
            raise EvaluationContractError("reviewer must be a string or null")
        return cls(
            corpus_id=str(value.get("corpus_id", "")),
            corpus_version=str(value.get("corpus_version", "")),
            source_digest=_address_from_mapping(value.get("source_digest"), field_name="source_digest"),
            canonical_content_digest=_address_from_mapping(
                value.get("canonical_content_digest"),
                field_name="canonical_content_digest",
            ),
            manifest_digest=_address_from_mapping(
                value.get("manifest_digest"), field_name="manifest_digest"
            ),
            baseline_release=str(value.get("baseline_release", "")),
            baseline_sha=str(value.get("baseline_sha", "")),
            privacy=str(value.get("privacy", "")),
            split_case_ids=splits,
            locked_evaluation_policy=str(value.get("locked_evaluation_policy", "")),
            review_status=str(value.get("review_status", "")),
            reviewer=reviewer,
            corpus_identity=_address_from_mapping(
                value.get("corpus_identity"), field_name="corpus_identity"
            ),
            canonicalization_profile=_profile(profile),
            schema=schema,
        )

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(case_id for values in self.split_case_ids.values() for case_id in values)
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "canonicalization_profile": self.canonicalization_profile.value,
            "corpus_id": self.corpus_id,
            "corpus_version": self.corpus_version,
            "source_digest": self.source_digest.canonical_dict(),
            "canonical_content_digest": self.canonical_content_digest.canonical_dict(),
            "manifest_digest": self.manifest_digest.canonical_dict(),
            "baseline_release": self.baseline_release,
            "baseline_sha": self.baseline_sha,
            "privacy": self.privacy,
            "split_case_ids": {
                split.value: list(self.split_case_ids[split]) for split in GoldSplit
            },
            "locked_evaluation_policy": self.locked_evaluation_policy,
            "review_status": self.review_status,
            "reviewer": self.reviewer,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "corpus_identity": self.corpus_identity.canonical_dict()}

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.corpus_identity != expected:
            raise EvaluationContractError("Gold corpus identity content-address mismatch")


@dataclass(frozen=True, slots=True)
class MetricSpec:
    direction: MetricDirection
    warning_threshold: float
    release_threshold: float

    def __post_init__(self) -> None:
        warning = _finite_float(self.warning_threshold, field_name="warning_threshold")
        release = _finite_float(self.release_threshold, field_name="release_threshold")
        object.__setattr__(self, "warning_threshold", warning)
        object.__setattr__(self, "release_threshold", release)
        if self.direction is MetricDirection.MIN and warning < release:
            raise EvaluationContractError("MIN warning threshold cannot be below release threshold")
        if self.direction is MetricDirection.MAX and warning > release:
            raise EvaluationContractError("MAX warning threshold cannot exceed release threshold")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> MetricSpec:
        raw_direction = value.get("direction")
        if not isinstance(raw_direction, str):
            raise EvaluationContractError("metric direction is required")
        try:
            direction = MetricDirection(raw_direction)
        except ValueError as exc:
            raise EvaluationContractError(f"unsupported metric direction: {raw_direction}") from exc
        return cls(
            direction=direction,
            warning_threshold=_finite_float(
                value.get("warning_threshold"), field_name="warning_threshold"
            ),
            release_threshold=_finite_float(
                value.get("release_threshold"), field_name="release_threshold"
            ),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "direction": self.direction.value,
            "warning_threshold": self.warning_threshold,
            "release_threshold": self.release_threshold,
        }


@dataclass(frozen=True, slots=True)
class KQMPolicy:
    version: str
    baseline: str
    metrics: Mapping[str, MetricSpec]
    missing_metric: str
    threshold_relaxation_requires_versioned_policy_change: bool
    evaluator_may_mutate_product_state: bool
    policy_identity: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = KQM_POLICY_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != KQM_POLICY_SCHEMA_V2:
            raise EvaluationContractError(f"unsupported KQM policy schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise EvaluationContractError(
                f"unsupported canonicalization profile: {self.canonicalization_profile}"
            )
        object.__setattr__(self, "version", _require_identifier(self.version, field_name="version"))
        object.__setattr__(
            self,
            "baseline",
            _require_identifier(self.baseline, field_name="baseline"),
        )
        if not self.metrics:
            raise EvaluationContractError("KQM policy must contain at least one metric")
        normalized: dict[str, MetricSpec] = {}
        for name, spec in self.metrics.items():
            canonical_name = _require_identifier(name, field_name="metric name")
            if canonical_name in normalized:
                raise EvaluationContractError(f"duplicate KQM metric: {canonical_name}")
            normalized[canonical_name] = spec
        object.__setattr__(self, "metrics", _freeze_metrics(normalized))
        if self.missing_metric != "FAIL":
            raise EvaluationContractError("KQM missing_metric policy must be FAIL")
        if not self.threshold_relaxation_requires_versioned_policy_change:
            raise EvaluationContractError("KQM threshold relaxation must require versioned policy change")
        if self.evaluator_may_mutate_product_state:
            raise EvaluationContractError("KQM evaluator cannot mutate Product state")
        self.verify()

    @classmethod
    def build(cls, value: Mapping[str, object]) -> KQMPolicy:
        if value.get("schema") != KQM_POLICY_SCHEMA_V2:
            raise EvaluationContractError(f"unsupported KQM policy schema: {value.get('schema')}")
        raw_metrics = _mapping(value.get("metrics"), field_name="KQM metrics")
        metrics: dict[str, MetricSpec] = {}
        for name, raw_spec in raw_metrics.items():
            metrics[name] = MetricSpec.from_mapping(
                _mapping(raw_spec, field_name=f"metric {name}")
            )
        policy = _mapping(value.get("policy"), field_name="KQM policy controls")
        body = cls._body(
            version=str(value.get("version", "")),
            baseline=str(value.get("baseline", "")),
            metrics=metrics,
            missing_metric=str(policy.get("missing_metric", "")),
            threshold_relaxation_requires_versioned_policy_change=bool(
                policy.get("threshold_relaxation_requires_versioned_policy_change", False)
            ),
            evaluator_may_mutate_product_state=bool(
                policy.get("evaluator_may_mutate_product_state", True)
            ),
        )
        return cls(
            version=str(value.get("version", "")),
            baseline=str(value.get("baseline", "")),
            metrics=metrics,
            missing_metric=str(policy.get("missing_metric", "")),
            threshold_relaxation_requires_versioned_policy_change=bool(
                policy.get("threshold_relaxation_requires_versioned_policy_change", False)
            ),
            evaluator_may_mutate_product_state=bool(
                policy.get("evaluator_may_mutate_product_state", True)
            ),
            policy_identity=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> KQMPolicy:
        schema = value.get("schema")
        profile = value.get("canonicalization_profile")
        if not isinstance(schema, str) or not isinstance(profile, str):
            raise EvaluationContractError("KQM schema/profile are required")
        raw_metrics = _mapping(value.get("metrics"), field_name="KQM metrics")
        metrics = {
            name: MetricSpec.from_mapping(_mapping(raw, field_name=f"metric {name}"))
            for name, raw in raw_metrics.items()
        }
        return cls(
            version=str(value.get("version", "")),
            baseline=str(value.get("baseline", "")),
            metrics=metrics,
            missing_metric=str(value.get("missing_metric", "")),
            threshold_relaxation_requires_versioned_policy_change=bool(
                value.get("threshold_relaxation_requires_versioned_policy_change", False)
            ),
            evaluator_may_mutate_product_state=bool(
                value.get("evaluator_may_mutate_product_state", True)
            ),
            policy_identity=_address_from_mapping(
                value.get("policy_identity"), field_name="policy_identity"
            ),
            canonicalization_profile=_profile(profile),
            schema=schema,
        )

    @staticmethod
    def _body(
        *,
        version: str,
        baseline: str,
        metrics: Mapping[str, MetricSpec],
        missing_metric: str,
        threshold_relaxation_requires_versioned_policy_change: bool,
        evaluator_may_mutate_product_state: bool,
    ) -> dict[str, object]:
        return {
            "schema": KQM_POLICY_SCHEMA_V2,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "version": version,
            "baseline": baseline,
            "metrics": {
                name: metrics[name].canonical_dict() for name in sorted(metrics)
            },
            "missing_metric": missing_metric,
            "threshold_relaxation_requires_versioned_policy_change": (
                threshold_relaxation_requires_versioned_policy_change
            ),
            "evaluator_may_mutate_product_state": evaluator_may_mutate_product_state,
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            version=self.version,
            baseline=self.baseline,
            metrics=self.metrics,
            missing_metric=self.missing_metric,
            threshold_relaxation_requires_versioned_policy_change=(
                self.threshold_relaxation_requires_versioned_policy_change
            ),
            evaluator_may_mutate_product_state=self.evaluator_may_mutate_product_state,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "policy_identity": self.policy_identity.canonical_dict()}

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.policy_identity != expected:
            raise EvaluationContractError("KQM policy identity content-address mismatch")


@dataclass(frozen=True, slots=True)
class EvaluatorIdentity:
    evaluator_id: str
    evaluator_version: str
    code_sha: str
    runtime_identity_digest: ContentAddress
    evaluator_identity: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = EVALUATOR_IDENTITY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != EVALUATOR_IDENTITY_SCHEMA_V1:
            raise EvaluationContractError(f"unsupported evaluator identity schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise EvaluationContractError(
                f"unsupported canonicalization profile: {self.canonicalization_profile}"
            )
        object.__setattr__(
            self,
            "evaluator_id",
            _require_identifier(self.evaluator_id, field_name="evaluator_id"),
        )
        object.__setattr__(
            self,
            "evaluator_version",
            _require_identifier(self.evaluator_version, field_name="evaluator_version"),
        )
        object.__setattr__(
            self,
            "code_sha",
            _require_git_sha(self.code_sha, field_name="evaluator code_sha"),
        )
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        evaluator_id: str,
        evaluator_version: str,
        code_sha: str,
        runtime_identity: RuntimeIdentity,
    ) -> EvaluatorIdentity:
        runtime_address = _content_address_from_hex(
            runtime_identity.digest(),
            field_name="runtime_identity_digest",
        )
        body = cls._body(
            evaluator_id=evaluator_id,
            evaluator_version=evaluator_version,
            code_sha=code_sha,
            runtime_identity_digest=runtime_address,
        )
        return cls(
            evaluator_id=evaluator_id,
            evaluator_version=evaluator_version,
            code_sha=code_sha,
            runtime_identity_digest=runtime_address,
            evaluator_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        evaluator_id: str,
        evaluator_version: str,
        code_sha: str,
        runtime_identity_digest: ContentAddress,
    ) -> dict[str, object]:
        return {
            "schema": EVALUATOR_IDENTITY_SCHEMA_V1,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "evaluator_id": evaluator_id,
            "evaluator_version": evaluator_version,
            "code_sha": code_sha,
            "runtime_identity_digest": runtime_identity_digest.canonical_dict(),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            code_sha=self.code_sha,
            runtime_identity_digest=self.runtime_identity_digest,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "evaluator_identity": self.evaluator_identity.canonical_dict(),
        }

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.evaluator_identity != expected:
            raise EvaluationContractError("evaluator identity content-address mismatch")


@dataclass(frozen=True, slots=True)
class CaseLedgerHead:
    case_id: CaseId
    head_event_id: ContentAddress | None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id.value,
            "head_event_id": (
                self.head_event_id.canonical_dict() if self.head_event_id is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class EvaluationInputIdentity:
    corpus_identity: ContentAddress
    policy_identity: ContentAddress
    evaluator_identity: ContentAddress
    purpose: EvaluationPurpose
    splits: tuple[GoldSplit, ...]
    selected_case_ids: tuple[str, ...]
    ledger_heads: tuple[CaseLedgerHead, ...]
    input_identity: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = EVALUATION_INPUT_IDENTITY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != EVALUATION_INPUT_IDENTITY_SCHEMA_V1:
            raise EvaluationContractError(f"unsupported evaluation input schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise EvaluationContractError(
                f"unsupported canonicalization profile: {self.canonicalization_profile}"
            )
        if not self.splits or len(set(self.splits)) != len(self.splits):
            raise EvaluationContractError("evaluation splits must be nonempty and unique")
        if tuple(sorted(self.splits, key=lambda item: item.value)) != self.splits:
            raise EvaluationContractError("evaluation splits must be canonically sorted")
        if (
            GoldSplit.LOCKED_EVALUATION in self.splits
            and self.purpose is not EvaluationPurpose.CERTIFICATION
        ):
            raise EvaluationContractError(
                "locked evaluation may only be selected for certification"
            )
        canonical_cases = tuple(
            _require_identifier(item, field_name="selected case_id")
            for item in self.selected_case_ids
        )
        if not canonical_cases or tuple(sorted(canonical_cases)) != canonical_cases:
            raise EvaluationContractError("selected case ids must be nonempty and sorted")
        if len(set(canonical_cases)) != len(canonical_cases):
            raise EvaluationContractError("selected case ids cannot contain duplicates")
        ledger_ids = tuple(head.case_id.value for head in self.ledger_heads)
        if tuple(sorted(ledger_ids)) != ledger_ids:
            raise EvaluationContractError("ledger heads must be sorted by case_id")
        if len(set(ledger_ids)) != len(ledger_ids):
            raise EvaluationContractError("ledger heads cannot contain duplicate case ids")
        if ledger_ids != canonical_cases:
            raise EvaluationContractError("ledger heads must exactly cover selected case ids")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        corpus: GoldCorpusIdentity,
        policy: KQMPolicy,
        evaluator: EvaluatorIdentity,
        purpose: EvaluationPurpose,
        splits: Sequence[GoldSplit],
        ledger_heads: Sequence[CaseLedgerHead],
    ) -> EvaluationInputIdentity:
        normalized_splits = tuple(sorted(set(splits), key=lambda item: item.value))
        if not normalized_splits:
            raise EvaluationContractError("evaluation requires at least one split")
        if (
            GoldSplit.LOCKED_EVALUATION in normalized_splits
            and purpose is not EvaluationPurpose.CERTIFICATION
        ):
            raise EvaluationContractError(
                "locked evaluation may only be selected for certification"
            )
        selected = tuple(
            sorted(
                case_id
                for split in normalized_splits
                for case_id in corpus.split_case_ids[split]
            )
        )
        ordered_heads = tuple(sorted(ledger_heads, key=lambda item: item.case_id.value))
        body = cls._body(
            corpus_identity=corpus.corpus_identity,
            policy_identity=policy.policy_identity,
            evaluator_identity=evaluator.evaluator_identity,
            purpose=purpose,
            splits=normalized_splits,
            selected_case_ids=selected,
            ledger_heads=ordered_heads,
        )
        return cls(
            corpus_identity=corpus.corpus_identity,
            policy_identity=policy.policy_identity,
            evaluator_identity=evaluator.evaluator_identity,
            purpose=purpose,
            splits=normalized_splits,
            selected_case_ids=selected,
            ledger_heads=ordered_heads,
            input_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        corpus_identity: ContentAddress,
        policy_identity: ContentAddress,
        evaluator_identity: ContentAddress,
        purpose: EvaluationPurpose,
        splits: tuple[GoldSplit, ...],
        selected_case_ids: tuple[str, ...],
        ledger_heads: tuple[CaseLedgerHead, ...],
    ) -> dict[str, object]:
        return {
            "schema": EVALUATION_INPUT_IDENTITY_SCHEMA_V1,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "corpus_identity": corpus_identity.canonical_dict(),
            "policy_identity": policy_identity.canonical_dict(),
            "evaluator_identity": evaluator_identity.canonical_dict(),
            "purpose": purpose.value,
            "splits": [split.value for split in splits],
            "selected_case_ids": list(selected_case_ids),
            "ledger_heads": [head.canonical_dict() for head in ledger_heads],
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            corpus_identity=self.corpus_identity,
            policy_identity=self.policy_identity,
            evaluator_identity=self.evaluator_identity,
            purpose=self.purpose,
            splits=self.splits,
            selected_case_ids=self.selected_case_ids,
            ledger_heads=self.ledger_heads,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "input_identity": self.input_identity.canonical_dict()}

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.input_identity != expected:
            raise EvaluationContractError("evaluation input identity content-address mismatch")


@dataclass(frozen=True, slots=True)
class KQMProjection:
    input_identity: ContentAddress
    policy_identity: ContentAddress
    evaluator_identity: ContentAddress
    metrics: Mapping[str, float]
    passed: bool
    failures: tuple[str, ...]
    projection_identity: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = KQM_PROJECTION_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != KQM_PROJECTION_SCHEMA_V2:
            raise EvaluationContractError(f"unsupported KQM projection schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise EvaluationContractError(
                f"unsupported canonicalization profile: {self.canonicalization_profile}"
            )
        normalized: dict[str, float] = {}
        for name, value in self.metrics.items():
            metric_name = _require_identifier(name, field_name="measured metric name")
            normalized[metric_name] = _finite_float(value, field_name=f"metric {metric_name}")
        object.__setattr__(self, "metrics", _freeze_numbers(normalized))
        normalized_failures = tuple(
            _require_identifier(item, field_name="KQM failure") for item in self.failures
        )
        if tuple(sorted(normalized_failures)) != normalized_failures:
            raise EvaluationContractError("KQM failures must be canonically sorted")
        if len(set(normalized_failures)) != len(normalized_failures):
            raise EvaluationContractError("KQM failures cannot contain duplicates")
        if self.passed != (not normalized_failures):
            raise EvaluationContractError("KQM passed flag must match failure set")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        evaluation_input: EvaluationInputIdentity,
        policy: KQMPolicy,
        evaluator: EvaluatorIdentity,
        metrics: Mapping[str, float],
    ) -> KQMProjection:
        if evaluation_input.policy_identity != policy.policy_identity:
            raise EvaluationContractError("evaluation input policy identity mismatch")
        if evaluation_input.evaluator_identity != evaluator.evaluator_identity:
            raise EvaluationContractError("evaluation input evaluator identity mismatch")
        provided = set(metrics)
        expected = set(policy.metrics)
        unexpected = sorted(provided - expected)
        if unexpected:
            raise EvaluationContractError(
                f"unexpected KQM metrics: {', '.join(unexpected)}"
            )
        normalized = {
            name: _finite_float(value, field_name=f"metric {name}")
            for name, value in metrics.items()
        }
        failures: list[str] = []
        for name in sorted(policy.metrics):
            if name not in normalized:
                failures.append(f"missing metric: {name}")
                continue
            value = normalized[name]
            spec = policy.metrics[name]
            if spec.direction is MetricDirection.MIN and value < spec.release_threshold:
                failures.append(f"{name} below release threshold")
            elif spec.direction is MetricDirection.MAX and value > spec.release_threshold:
                failures.append(f"{name} above release threshold")
        ordered_failures = tuple(sorted(failures))
        body = cls._body(
            input_identity=evaluation_input.input_identity,
            policy_identity=policy.policy_identity,
            evaluator_identity=evaluator.evaluator_identity,
            metrics=normalized,
            passed=not ordered_failures,
            failures=ordered_failures,
        )
        return cls(
            input_identity=evaluation_input.input_identity,
            policy_identity=policy.policy_identity,
            evaluator_identity=evaluator.evaluator_identity,
            metrics=normalized,
            passed=not ordered_failures,
            failures=ordered_failures,
            projection_identity=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> KQMProjection:
        schema = value.get("schema")
        profile = value.get("canonicalization_profile")
        if not isinstance(schema, str) or not isinstance(profile, str):
            raise EvaluationContractError("KQM projection schema/profile are required")
        raw_metrics = _mapping(value.get("metrics"), field_name="projection metrics")
        metrics = {
            name: _finite_float(raw_value, field_name=f"metric {name}")
            for name, raw_value in raw_metrics.items()
        }
        failures = tuple(
            str(item)
            for item in _sequence(value.get("failures"), field_name="projection failures")
        )
        passed = value.get("passed")
        if not isinstance(passed, bool):
            raise EvaluationContractError("projection passed must be boolean")
        return cls(
            input_identity=_address_from_mapping(
                value.get("input_identity"), field_name="input_identity"
            ),
            policy_identity=_address_from_mapping(
                value.get("policy_identity"), field_name="policy_identity"
            ),
            evaluator_identity=_address_from_mapping(
                value.get("evaluator_identity"), field_name="evaluator_identity"
            ),
            metrics=metrics,
            passed=passed,
            failures=failures,
            projection_identity=_address_from_mapping(
                value.get("projection_identity"), field_name="projection_identity"
            ),
            canonicalization_profile=_profile(profile),
            schema=schema,
        )

    @staticmethod
    def _body(
        *,
        input_identity: ContentAddress,
        policy_identity: ContentAddress,
        evaluator_identity: ContentAddress,
        metrics: Mapping[str, float],
        passed: bool,
        failures: tuple[str, ...],
    ) -> dict[str, object]:
        return {
            "schema": KQM_PROJECTION_SCHEMA_V2,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "input_identity": input_identity.canonical_dict(),
            "policy_identity": policy_identity.canonical_dict(),
            "evaluator_identity": evaluator_identity.canonical_dict(),
            "metrics": dict(sorted(metrics.items())),
            "passed": passed,
            "failures": list(failures),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            input_identity=self.input_identity,
            policy_identity=self.policy_identity,
            evaluator_identity=self.evaluator_identity,
            metrics=self.metrics,
            passed=self.passed,
            failures=self.failures,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "projection_identity": self.projection_identity.canonical_dict(),
        }

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.projection_identity != expected:
            raise EvaluationContractError("KQM projection content-address mismatch")
