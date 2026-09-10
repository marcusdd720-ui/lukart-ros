from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

from cryptography.hazmat.primitives.asymmetric.mldsa import MLDSA65PrivateKey, MLDSA65PublicKey

from core.cross_algorithm_crypto_migration_v1 import (
    ML_DSA_CONTEXT,
    ML_DSA_PUBLIC_KEY_BYTES,
    NIST_ACVP_EXPECTED_BLOB_SHA,
    NIST_ACVP_PROMPT_BLOB_SHA,
    NIST_ACVP_VECTOR_CASE_ID,
    NIST_ACVP_VECTOR_GROUP_ID,
    require_mldsa65_runtime_support_v1,
)


class AcvpVectorError(ValueError):
    pass


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def _load(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AcvpVectorError(f"{path.name} must contain a JSON object")
    return cast(dict[str, object], value)


def _group(document: dict[str, object], tg_id: int) -> dict[str, object]:
    groups = document.get("testGroups")
    if not isinstance(groups, list):
        raise AcvpVectorError("ACVP testGroups missing")
    matches = [item for item in groups if isinstance(item, dict) and item.get("tgId") == tg_id]
    if len(matches) != 1:
        raise AcvpVectorError("ACVP test group identity is not unique")
    return cast(dict[str, object], matches[0])


def _test(group: dict[str, object], tc_id: int) -> dict[str, object]:
    tests = group.get("tests")
    if not isinstance(tests, list):
        raise AcvpVectorError("ACVP tests missing")
    matches = [item for item in tests if isinstance(item, dict) and item.get("tcId") == tc_id]
    if len(matches) != 1:
        raise AcvpVectorError("ACVP test case identity is not unique")
    return cast(dict[str, object], matches[0])


def verify_vector(root: Path) -> None:
    prompt_path = root / "prompt.json"
    expected_path = root / "expectedResults.json"
    if _git_blob_sha(prompt_path) != NIST_ACVP_PROMPT_BLOB_SHA:
        raise AcvpVectorError("pinned NIST ACVP prompt blob identity mismatch")
    if _git_blob_sha(expected_path) != NIST_ACVP_EXPECTED_BLOB_SHA:
        raise AcvpVectorError("pinned NIST ACVP expected-results blob identity mismatch")

    prompt = _load(prompt_path)
    expected = _load(expected_path)
    if prompt.get("algorithm") != "ML-DSA" or prompt.get("revision") != "FIPS204":
        raise AcvpVectorError("unexpected ACVP prompt algorithm/revision")
    if expected.get("algorithm") != "ML-DSA" or expected.get("revision") != "FIPS204":
        raise AcvpVectorError("unexpected ACVP expected algorithm/revision")

    prompt_group = _group(prompt, NIST_ACVP_VECTOR_GROUP_ID)
    expected_group = _group(expected, NIST_ACVP_VECTOR_GROUP_ID)
    if prompt_group.get("parameterSet") != "ML-DSA-65":
        raise AcvpVectorError("pinned ACVP group is not ML-DSA-65")
    prompt_case = _test(prompt_group, NIST_ACVP_VECTOR_CASE_ID)
    expected_case = _test(expected_group, NIST_ACVP_VECTOR_CASE_ID)

    seed_hex = prompt_case.get("seed")
    expected_pk_hex = expected_case.get("pk")
    if not isinstance(seed_hex, str) or not isinstance(expected_pk_hex, str):
        raise AcvpVectorError("pinned ACVP key-generation vector is incomplete")
    seed = bytes.fromhex(seed_hex)
    expected_pk = bytes.fromhex(expected_pk_hex)
    if len(seed) != 32 or len(expected_pk) != ML_DSA_PUBLIC_KEY_BYTES:
        raise AcvpVectorError("pinned ACVP key-generation vector has unexpected sizes")

    require_mldsa65_runtime_support_v1()
    private_key = MLDSA65PrivateKey.from_seed_bytes(seed)
    actual_pk = private_key.public_key().public_bytes_raw()
    if actual_pk != expected_pk:
        raise AcvpVectorError("ML-DSA-65 public key does not match pinned NIST ACVP vector")

    reloaded = MLDSA65PublicKey.from_public_bytes(actual_pk)
    message = b"LRD-01J-pinned-ACVP-interoperability-probe"
    signature = private_key.sign(message, ML_DSA_CONTEXT)
    reloaded.verify(signature, message, ML_DSA_CONTEXT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify pinned NIST ACVP ML-DSA-65 vector")
    parser.add_argument("vector_dir", type=Path)
    args = parser.parse_args()
    verify_vector(args.vector_dir)
    print("LRD-01J NIST ACVP ML-DSA-65 vector: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
