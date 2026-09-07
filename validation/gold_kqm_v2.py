"""Read-only PHX-02 loaders for immutable Gold and KQM policy inputs.

This Factory-side module validates source bytes and constructs content-addressed
contracts.  It intentionally contains no ledger write or Product mutation API.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from core.evaluation import EvaluationContractError, GoldCorpusIdentity, KQMPolicy


def _json_mapping(raw: bytes, *, field_name: str) -> Mapping[str, object]:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationContractError(f"{field_name} must be valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise EvaluationContractError(f"{field_name} must be a JSON object")
    if any(not isinstance(key, str) for key in decoded):
        raise EvaluationContractError(f"{field_name} keys must be strings")
    return cast(Mapping[str, object], decoded)


def load_gold_corpus_identity(
    corpus_path: str | Path,
    manifest_path: str | Path,
) -> GoldCorpusIdentity:
    """Verify exact source bytes and build immutable semantic Gold identity."""

    corpus_bytes = Path(corpus_path).read_bytes()
    manifest_bytes = Path(manifest_path).read_bytes()
    corpus = _json_mapping(corpus_bytes, field_name="Gold corpus")
    manifest = _json_mapping(manifest_bytes, field_name="Gold manifest")
    source_digest = hashlib.sha256(corpus_bytes).hexdigest()
    return GoldCorpusIdentity.build(
        corpus=corpus,
        manifest=manifest,
        source_digest=source_digest,
    )


def load_kqm_policy(path: str | Path) -> KQMPolicy:
    """Load a versioned immutable KQM policy without evaluating or mutating Product state."""

    policy = _json_mapping(Path(path).read_bytes(), field_name="KQM policy")
    return KQMPolicy.build(policy)
