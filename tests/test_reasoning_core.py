from knowledge.epistemic import EpistemicTransitionError, KnowledgeStatus
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact, ReasoningOutcome
from reasoning.transitions import transition_artifact
from reasoning.validation import validate_reasoning_graph


def _fact(artifact_id: str = "F1") -> ReasoningArtifact:
    return ReasoningArtifact(
        artifact_id=artifact_id,
        statement="Observed source fact",
        status=KnowledgeStatus.FACT,
        evidence_refs=("DOC-1#p1",),
    )


def test_reasoning_artifact_digest_is_order_independent_for_refs() -> None:
    left = ReasoningArtifact(
        artifact_id="F1",
        statement="Observed source fact",
        status=KnowledgeStatus.FACT,
        evidence_refs=("DOC-2", "DOC-1"),
    )
    right = ReasoningArtifact(
        artifact_id="F1",
        statement="Observed source fact",
        status=KnowledgeStatus.FACT,
        evidence_refs=("DOC-1", "DOC-2"),
    )

    assert left.digest() == right.digest()


def test_fact_without_evidence_fails_validation() -> None:
    fact = ReasoningArtifact(
        artifact_id="F1",
        statement="Unsupported fact",
        status=KnowledgeStatus.FACT,
    )

    result = validate_reasoning_graph((fact,))

    assert result.ok is False
    assert any(issue.code == "R004" for issue in result.issues)


def test_conclusion_requires_existing_evidence_backed_support() -> None:
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Conclusion",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=("MISSING",),
    )

    result = validate_reasoning_graph((conclusion,))

    assert result.ok is False
    assert any(issue.code == "R002" for issue in result.issues)


def test_support_cycle_fails_closed() -> None:
    first = ReasoningArtifact(
        artifact_id="H1",
        statement="Hypothesis one",
        status=KnowledgeStatus.HYPOTHESIS,
        support_ids=("H2",),
    )
    second = ReasoningArtifact(
        artifact_id="H2",
        statement="Hypothesis two",
        status=KnowledgeStatus.HYPOTHESIS,
        support_ids=("H1",),
    )

    result = validate_reasoning_graph((first, second))

    assert result.ok is False
    assert any(issue.code == "R003" for issue in result.issues)


def test_engine_concludes_only_with_valid_evidence_lineage() -> None:
    fact = _fact()
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Evidence-backed conclusion",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=(fact.artifact_id,),
    )

    result = ReasoningEngine((fact, conclusion)).evaluate("C1")

    assert result.decision.outcome is ReasoningOutcome.CONCLUDE
    assert result.decision.artifact_id == "C1"
    assert result.open_questions == ()


def test_engine_abstains_when_support_is_unresolved() -> None:
    unresolved = ReasoningArtifact(
        artifact_id="U1",
        statement="Conflicting source value",
        status=KnowledgeStatus.UNRESOLVED,
        evidence_refs=("DOC-1", "DOC-2"),
    )
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Premature conclusion",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=(unresolved.artifact_id,),
    )

    result = ReasoningEngine((unresolved, conclusion)).evaluate("C1")

    assert result.decision.outcome is ReasoningOutcome.ABSTAIN
    assert result.decision.artifact_id is None
    assert result.open_questions
    assert result.decision.open_question_ids


def test_engine_abstains_when_conclusion_is_missing() -> None:
    result = ReasoningEngine((_fact(),)).evaluate("C404")

    assert result.decision.outcome is ReasoningOutcome.ABSTAIN
    assert result.open_questions


def test_reasoning_result_digest_is_stable_across_artifact_order() -> None:
    fact = _fact()
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Evidence-backed conclusion",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=(fact.artifact_id,),
    )

    left = ReasoningEngine((fact, conclusion)).evaluate("C1")
    right = ReasoningEngine((conclusion, fact)).evaluate("C1")

    assert left.digest() == right.digest()


def test_claim_cannot_be_promoted_to_fact_without_new_evidence() -> None:
    claim = ReasoningArtifact(
        artifact_id="CL1",
        statement="Party assertion",
        status=KnowledgeStatus.CLAIM,
    )

    try:
        transition_artifact(claim, KnowledgeStatus.FACT)
    except EpistemicTransitionError as exc:
        assert "requires new evidence" in str(exc)
    else:
        raise AssertionError("CLAIM -> FACT without new evidence must fail")


def test_claim_can_be_promoted_to_fact_with_new_evidence() -> None:
    claim = ReasoningArtifact(
        artifact_id="CL1",
        statement="Party assertion",
        status=KnowledgeStatus.CLAIM,
    )

    promoted = transition_artifact(
        claim,
        KnowledgeStatus.FACT,
        new_evidence_refs=("DOC-9#p4",),
    )

    assert promoted.status is KnowledgeStatus.FACT
    assert promoted.evidence_refs == ("DOC-9#p4",)
