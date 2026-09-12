from __future__ import annotations

from dataclasses import replace

import pytest

from core.cirp.engine import canonical_rule_pack_set_digest
from tests.test_cirp_canonical_runtime import calendar, deadline_rule, remedy_rule, rule_pack
from tests.test_cirp_private_intake import NOW as PRIVATE_NOW
from tests.test_cirp_private_intake import _bind, _draft_request


def test_private_intake_preserves_p03_rule_pack_identity_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_deadline_rule = deadline_rule(calendar())
    selected_remedy_rule = remedy_rule()
    selected_pack = rule_pack(selected_deadline_rule, selected_remedy_rule)
    draft = replace(_draft_request(), rule_packs=(selected_pack,))

    bound = _bind(monkeypatch, draft)

    assert bound.rule_packs == (selected_pack,)
    assert bound.run_identity.rule_pack_ids == (selected_pack.pack_id,)
    assert bound.run_identity.rule_pack_digest == canonical_rule_pack_set_digest((selected_pack,))
    assert bound.run_identity.evaluation_time == PRIVATE_NOW
