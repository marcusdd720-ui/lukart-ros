"""Frozen, non-authoritative ROS-to-WORK gate requirements for LEGAL OS.

This module maps *prerequisites*, not approvals. No caller-supplied status,
WORK receipt or ROS operation success can become HUMAN or FINISH admission.
The WORK domain and native authorization remain authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


GATE_MAP_VERSION: Final = "1.0.0"
ROS_SOURCE_SHA: Final = "7900bea704669c73e01c167b807a242f2e28d9cb"
WORK_CANDIDATE_SHA: Final = "efbb9006afbddfcbf7e181888845735aa912e44c"
RELATION: Final = "RELATED_PREREQUISITES_NOT_EQUIVALENCE"


@dataclass(frozen=True)
class GateRequirements:
    ros_gate: str
    work_prerequisites: tuple[str, ...]
    ros_only_requirements: tuple[str, ...]
    relation: str = RELATION
    admission: str = "NOT_ADMITTED"


# WORK HG-10 (independent product admission) is a separate release prerequisite,
# not an alternative to any ROS case gate or native WORK HG-01..HG-09.
_HG10 = "independent_exact_sha_product_admission"

_GATES: Final = MappingProxyType({
    "G0": GateRequirements(
        "G0", ("HG-01", "HG-04"),
        ("decision_need", "case_privacy_scope", "protective_outcome"),
    ),
    "G1": GateRequirements(
        "G1", ("HG-02",),
        ("source_inventory", "original_integrity", "evidence_provenance"),
    ),
    "G2": GateRequirements(
        "G2", ("HG-02",),
        ("evidence_ceiling", "fact_claim_separation", "unresolved_uncertainty"),
    ),
    "G3": GateRequirements(
        "G3", ("HG-02", "HG-03"),
        ("timeline", "receipt_service_evidence", "deadline_rule_and_uncertainty"),
    ),
    "G4": GateRequirements(
        "G4", ("HG-01", "HG-03"),
        ("standing", "representation", "competent_recipient_and_filing_route"),
    ),
    "G5": GateRequirements(
        "G5", ("HG-03",),
        ("current_law_sources", "effective_date", "adverse_authority"),
    ),
    "G6": GateRequirements(
        "G6", ("HG-03", "HG-04"),
        ("remedy_options", "strategy", "filing_topology", "human_position"),
    ),
    "G7": GateRequirements(
        "G7", ("HG-01", "HG-02", "HG-03", "HG-04",
               "HG-05", "HG-06", "HG-07", "HG-08"),
        ("draft_a", "red_team", "draft_b", "hardcore_preflight",
         "zero_silent_loss", "identity_address_completeness"),
    ),
    "G7.5": GateRequirements(
        "G7.5", ("HG-07", "HG-08", "HG-09"),
        ("fresh_final_artifact_review", "docx_pdf_exact_byte_hashes",
         "semantic_and_visual_parity", "zero_silent_loss",
         "finish_pass_exact_artifact", "invalidate_finish_on_any_byte_change"),
    ),
    "G8": GateRequirements(
        "G8", ("HG-09",),
        (_HG10, "finish_pass_exact_artifact", "native_work_release_receipt",
         "separate_human_send_or_filing_authority", "external_action_receipt",
         "no_automatic_send_or_signature"),
    ),
})


def map_ros_gate(gate: str) -> GateRequirements:
    """Return immutable prerequisite metadata; NEVER return a gate verdict.

    Raises on unknown gates rather than silently treating them as optional.
    """
    if not isinstance(gate, str) or gate not in _GATES:
        raise ValueError("LEGAL_OS_UNKNOWN_ROS_GATE")
    return _GATES[gate]


def all_ros_gates() -> tuple[str, ...]:
    """Canonical order includes the distinct post-render G7.5 FINISH gate."""
    return tuple(_GATES)


def can_promote_from_mapping_only() -> bool:
    """Mapping cannot authorize execution, release, SEND_READY or filing."""
    return False
