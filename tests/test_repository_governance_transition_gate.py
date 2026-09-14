from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.repository_governance_transition_gate import (
    validate_check_dependency_graph,
    validate_profile_truthfulness,
    validate_state_contract,
    validate_state_machine,
    validate_transition,
)


def _check(
    context: str,
    workflow: str,
    job_id: str,
    *,
    integration_id: int = 15368,
) -> dict[str, object]:
    return {
        "context": context,
        "integration_id": integration_id,
        "workflow": workflow,
        "job_id": job_id,
    }


def _h2(state: str = "INDEPENDENT_LOCKED") -> dict[str, object]:
    gate = _check("gate", ".github/workflows/stage-gate.yml", "gate")
    codeql = _check("codeql", ".github/workflows/codeql-enterprise.yml", "codeql")
    solo = _check(
        "solo-governance",
        ".github/workflows/solo-maintainer-governance.yml",
        "solo-governance",
    )
    technical = [gate, codeql]
    final = [*technical, solo]
    effective = technical if state == "INDEPENDENT_LOCKED" else final
    independent_rule = {
        "minimum_approving_review_count": 2,
        "dismiss_stale_reviews_on_push": True,
        "require_code_owner_review": True,
        "require_last_push_approval": True,
        "required_review_thread_resolution": True,
        "require_extra_approval_for_unattributed_changes": True,
        "allowed_merge_methods": ["merge"],
    }
    solo_rule = {
        "minimum_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": True,
        "require_code_owner_review": False,
        "require_last_push_approval": False,
        "required_review_thread_resolution": True,
        "require_extra_approval_for_unattributed_changes": False,
        "allowed_merge_methods": ["merge"],
    }
    review: dict[str, object] = {
        "ordinary_minimum_independent_approvals": 2,
        "critical_minimum_independent_approvals": 2,
        "approvals_must_bind_current_head": True,
        "critical_paths": ["config/**"],
    }
    pull_rule = independent_rule
    if state == "SOLO_ACTIVE":
        pull_rule = solo_rule
        review.update(
            {
                "ordinary_minimum_independent_approvals": 0,
                "critical_minimum_independent_approvals": 0,
                "independent_external_review": "NOT_PERFORMED",
                "reviewer_independent": False,
                "maintainer_attestation_must_bind_current_head": True,
            }
        )
    return {
        "governance_state": state,
        "governance_state_machine": {
            "INDEPENDENT_LOCKED": ["INDEPENDENT_LOCKED", "SOLO_ARMED"],
            "SOLO_ARMED": ["SOLO_ARMED", "SOLO_ACTIVE"],
            "SOLO_ACTIVE": ["SOLO_ACTIVE"],
        },
        "allowed_bypass_actors": [],
        "pull_request_rule": deepcopy(pull_rule),
        "review_integrity": review,
        "technical_required_checks": deepcopy(technical),
        "final_required_checks": deepcopy(final),
        "required_checks": deepcopy(effective),
        "check_dependencies": {
            "gate": [],
            "codeql": [],
            "solo-governance": ["gate", "codeql"],
        },
        "solo_maintainer_profile": {
            "maintainer_id": "owner",
            "default_branch": "main",
            "independent_external_review": "NOT_PERFORMED",
            "reviewer_independent": False,
            "attestation": {
                "marker": "LUKART-SOLO-MAINTAINER-ATTESTATION-V1",
                "decision": "ACCEPT",
                "revocation_decision": "REVOKE",
                "must_bind_current_head": True,
                "must_follow_terminal_technical_success": True,
                "author_association": "OWNER",
            },
            "cooldown_seconds": {"ordinary": 0, "critical": 7200, "governance": 86400},
            "target_pull_request_rule": deepcopy(solo_rule),
            "required_solo_check": deepcopy(solo),
        },
    }


def test_state_machine_accepts_only_locked_armed_active_topology() -> None:
    evidence = validate_state_machine(_h2())
    assert evidence["state"] == "INDEPENDENT_LOCKED"


def test_state_machine_rejects_skip_edge() -> None:
    h2 = _h2()
    h2["governance_state_machine"]["INDEPENDENT_LOCKED"].append("SOLO_ACTIVE")  # type: ignore[index]
    with pytest.raises(RuntimeError, match="LOCKED -> ARMED -> ACTIVE"):
        validate_state_machine(h2)


def test_transition_rejects_direct_locked_to_active() -> None:
    previous = {"governance_state": "INDEPENDENT_LOCKED"}
    current = {"governance_state": "SOLO_ACTIVE"}
    with pytest.raises(RuntimeError, match="forbidden governance transition"):
        validate_transition(previous, current)


def test_transition_treats_legacy_base_as_independent_locked() -> None:
    evidence = validate_transition({}, {"governance_state": "INDEPENDENT_LOCKED"})
    assert evidence == {
        "previous_state": "INDEPENDENT_LOCKED",
        "current_state": "INDEPENDENT_LOCKED",
    }


def test_state_contract_keeps_native_independent_controls_in_armed() -> None:
    evidence = validate_state_contract(_h2("SOLO_ARMED"))
    assert evidence == {
        "state": "SOLO_ARMED",
        "review_mode": "INDEPENDENT_NATIVE",
        "approvals": 2,
    }


def test_state_contract_rejects_early_approval_reduction_in_armed() -> None:
    h2 = _h2("SOLO_ARMED")
    h2["pull_request_rule"]["minimum_approving_review_count"] = 0  # type: ignore[index]
    with pytest.raises(RuntimeError, match="at least two approvals"):
        validate_state_contract(h2)


def test_state_contract_accepts_active_compensating_shape() -> None:
    evidence = validate_state_contract(_h2("SOLO_ACTIVE"))
    assert evidence["review_mode"] == "SOLO_COMPENSATING_CONTROLS"
    assert evidence["approvals"] == 0


def test_check_graph_accepts_technical_plus_solo_final_shape() -> None:
    evidence = validate_check_dependency_graph(_h2("SOLO_ARMED"))
    assert evidence["technical_required_checks"] == ["gate", "codeql"]
    assert evidence["final_required_checks"] == ["gate", "codeql", "solo-governance"]


def test_check_graph_rejects_solo_self_dependency() -> None:
    h2 = _h2("SOLO_ARMED")
    dependencies = h2["check_dependencies"]
    assert isinstance(dependencies, dict)
    solo_dependencies = dependencies["solo-governance"]
    assert isinstance(solo_dependencies, list)
    solo_dependencies.append("solo-governance")
    with pytest.raises(RuntimeError, match="self dependency"):
        validate_check_dependency_graph(h2)


def test_check_graph_rejects_cycle() -> None:
    h2 = _h2("SOLO_ARMED")
    h2["check_dependencies"]["gate"] = ["codeql"]  # type: ignore[index]
    h2["check_dependencies"]["codeql"] = ["gate"]  # type: ignore[index]
    with pytest.raises(RuntimeError, match="technical check|cycle"):
        validate_check_dependency_graph(h2)


def test_check_graph_rejects_duplicate_context() -> None:
    h2 = _h2()
    h2["technical_required_checks"].append(  # type: ignore[index]
        _check("gate", ".github/workflows/other.yml", "other")
    )
    with pytest.raises(RuntimeError, match="duplicate context"):
        validate_check_dependency_graph(h2)


def test_check_graph_rejects_wrong_solo_workflow_or_job_binding() -> None:
    h2 = _h2("SOLO_ARMED")
    h2["solo_maintainer_profile"]["required_solo_check"]["workflow"] = (  # type: ignore[index]
        ".github/workflows/spoof.yml"
    )
    with pytest.raises(RuntimeError, match="FINAL_REQUIRED_CHECKS"):
        validate_check_dependency_graph(h2)


def test_check_graph_rejects_wrong_solo_integration_binding() -> None:
    h2 = _h2("SOLO_ARMED")
    h2["solo_maintainer_profile"]["required_solo_check"]["integration_id"] = 999  # type: ignore[index]
    with pytest.raises(RuntimeError, match="FINAL_REQUIRED_CHECKS"):
        validate_check_dependency_graph(h2)


def test_check_graph_rejects_effective_checks_for_wrong_state() -> None:
    h2 = _h2("INDEPENDENT_LOCKED")
    h2["required_checks"] = deepcopy(h2["final_required_checks"])
    with pytest.raises(RuntimeError, match="effective required_checks"):
        validate_check_dependency_graph(h2)


def test_profile_truthfully_denies_independent_review() -> None:
    evidence = validate_profile_truthfulness(_h2())
    assert evidence["independent_external_review"] == "NOT_PERFORMED"
    assert evidence["reviewer_independent"] is False


def test_profile_rejects_false_independent_reviewer_claim() -> None:
    h2 = _h2()
    h2["solo_maintainer_profile"]["reviewer_independent"] = True  # type: ignore[index]
    with pytest.raises(RuntimeError, match="reviewer_independent=false"):
        validate_profile_truthfulness(h2)
