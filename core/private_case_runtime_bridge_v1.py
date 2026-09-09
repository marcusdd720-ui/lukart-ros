"""Verified non-cloud bridge from CASE-OPS-02 derivations into local runtime/CCL.

The compatibility document inventory is never trusted by this module. Runtime evidence
is reconstructed from immutable derivation receipts and CASE-OPS private evidence only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from core.case_ledger.contracts import CaseId, ContentAddress, LedgerEvent
from core.case_ledger.ledger import CanonicalCaseLedger
from core.enterprise.contracts import AuthorizationContext, EnterpriseContractError, Permission
from core.p3.contracts import RuntimeIdentity
from core.private_evidence_derivation_v1 import DerivedEvidence, load_derivation
from core.private_evidence_v1 import (
    PrivateEvidenceError,
    PrivateEvidenceStore,
    digest_hex,
    digest_object,
    opaque_digest,
)

SCHEMA_RUNTIME_PROJECTION = "lukart.private-case-runtime-projection.v1"
EVENT_PRIVATE_EVIDENCE_REGISTERED = "private.evidence.projection.registered.v1"
MAX_RUNTIME_DOCUMENTS = 10_000


class PrivateCaseRuntimeBridgeError(RuntimeError):
    """Fail-closed error at the private evidence/runtime/CCL trust boundary."""


@dataclass(frozen=True, slots=True)
class VerifiedLocalDocumentV1:
    document_id: str
    evidence_id: str
    manifest_digest: str
    receipt_digest: str
    derived_evidence_id: str
    derived_manifest_digest: str
    derived_receipt_digest: str
    derivation_identity: str
    derivation_receipt_digest: str
    derivation_replay_class: str
    case_scope_digest: str

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class VerifiedLocalEvidenceProjectionV1:
    schema: str
    case_id: str
    case_scope_digest: str
    documents: tuple[VerifiedLocalDocumentV1, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "case_scope_digest": self.case_scope_digest,
            "documents": [item.canonical_dict() for item in self.documents],
        }

    @property
    def projection_id(self) -> str:
        return digest_object(self.canonical_dict())

    def ccl_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "projection_id": self.projection_id,
            "case_scope_digest": self.case_scope_digest,
            "documents": [item.canonical_dict() for item in self.documents],
        }


def _load_mapping(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PrivateCaseRuntimeBridgeError(f"{label} missing or symlinked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateCaseRuntimeBridgeError(f"invalid {label}") from exc
    if not isinstance(value, dict):
        raise PrivateCaseRuntimeBridgeError(f"{label} must be a mapping")
    return value


def _source_ref_digest(result: DerivedEvidence) -> str:
    manifest = _load_mapping(result.source.manifest_path, label="source manifest")
    if digest_object(manifest) != result.source.manifest_digest:
        raise PrivateCaseRuntimeBridgeError("source manifest digest mismatch")
    value = manifest.get("source_ref_digest")
    if not isinstance(value, str):
        raise PrivateCaseRuntimeBridgeError("source manifest source identity is invalid")
    try:
        digest_hex(value)
    except PrivateEvidenceError as exc:
        raise PrivateCaseRuntimeBridgeError("source manifest source identity is invalid") from exc
    return value


def _derivation_receipt_digests(store: PrivateEvidenceStore) -> tuple[str, ...]:
    root = store.root / "derivations"
    if not root.exists():
        raise PrivateCaseRuntimeBridgeError("CASE-OPS-02 derivation receipts are missing")
    if root.is_symlink() or not root.is_dir():
        raise PrivateCaseRuntimeBridgeError("derivation receipt root is invalid")
    paths = sorted(root.rglob("*.json"))
    if not paths:
        raise PrivateCaseRuntimeBridgeError("CASE-OPS-02 derivation receipts are missing")
    if len(paths) > MAX_RUNTIME_DOCUMENTS:
        raise PrivateCaseRuntimeBridgeError("verified runtime document budget exceeded")
    digests: list[str] = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise PrivateCaseRuntimeBridgeError("derivation receipt path is invalid")
        relative = path.relative_to(root)
        if len(relative.parts) != 2 or len(relative.parts[0]) != 2:
            raise PrivateCaseRuntimeBridgeError("derivation receipt layout is invalid")
        if path.suffix != ".json" or len(path.stem) != 64:
            raise PrivateCaseRuntimeBridgeError("derivation receipt filename is invalid")
        digest = f"sha256:{path.stem}"
        try:
            digest_hex(digest)
        except PrivateEvidenceError as exc:
            raise PrivateCaseRuntimeBridgeError("derivation receipt digest is invalid") from exc
        if not path.stem.startswith(relative.parts[0]):
            raise PrivateCaseRuntimeBridgeError("derivation receipt shard mismatch")
        digests.append(digest)
    if len(set(digests)) != len(digests):
        raise PrivateCaseRuntimeBridgeError("duplicate derivation receipt identity")
    return tuple(digests)


def load_verified_projection(
    store: PrivateEvidenceStore,
) -> VerifiedLocalEvidenceProjectionV1:
    """Rebuild one local runtime projection only from verified CASE-OPS-02 derivations."""
    digests = _derivation_receipt_digests(store)
    loaded: list[DerivedEvidence] = []
    try:
        for digest in digests:
            loaded.append(load_derivation(store, digest))
    except PrivateEvidenceError as exc:
        raise PrivateCaseRuntimeBridgeError("CASE-OPS-02 derivation verification failed") from exc

    expected_slot_digests = {
        opaque_digest(f"document-slot:{index}"): index
        for index in range(1, len(loaded) + 1)
    }
    by_slot: dict[int, DerivedEvidence] = {}
    for result in loaded:
        source_ref_digest = _source_ref_digest(result)
        slot = expected_slot_digests.get(source_ref_digest)
        if slot is None:
            raise PrivateCaseRuntimeBridgeError("derivation is not bound to a canonical document slot")
        if slot in by_slot:
            raise PrivateCaseRuntimeBridgeError("ambiguous derivations for one document slot")
        by_slot[slot] = result
    expected_slots = set(range(1, len(loaded) + 1))
    if set(by_slot) != expected_slots:
        raise PrivateCaseRuntimeBridgeError("document slots are not contiguous and complete")

    documents: list[VerifiedLocalDocumentV1] = []
    for slot in sorted(by_slot):
        result = by_slot[slot]
        documents.append(
            VerifiedLocalDocumentV1(
                document_id=f"DOC-{slot:03d}",
                evidence_id=result.source.evidence_id,
                manifest_digest=result.source.manifest_digest,
                receipt_digest=result.source.receipt_digest,
                derived_evidence_id=result.derived.evidence_id,
                derived_manifest_digest=result.derived.manifest_digest,
                derived_receipt_digest=result.derived.receipt_digest,
                derivation_identity=result.semantic_derivation_id,
                derivation_receipt_digest=result.derivation_receipt_digest,
                derivation_replay_class=result.replay_class.value,
                case_scope_digest=store.case_scope_digest,
            )
        )
    return VerifiedLocalEvidenceProjectionV1(
        schema=SCHEMA_RUNTIME_PROJECTION,
        case_id=store.case_id,
        case_scope_digest=store.case_scope_digest,
        documents=tuple(documents),
    )


def register_projection_in_ccl(
    *,
    ledger: CanonicalCaseLedger,
    projection: VerifiedLocalEvidenceProjectionV1,
    runtime_identity: RuntimeIdentity,
    authorization: AuthorizationContext,
    expected_head: ContentAddress | None,
) -> LedgerEvent:
    """Append one digest-only provenance event through the existing CCL authority."""
    try:
        authorization.require(
            Permission.CASE_WRITE,
            tenant_id=authorization.tenant_id,
            case_id=projection.case_id,
            strict_scope=True,
        )
    except EnterpriseContractError as exc:
        raise PrivateCaseRuntimeBridgeError("CCL registration authorization denied") from exc
    expected_scope = digest_object(
        {"tenant_id": authorization.tenant_id, "case_id": projection.case_id}
    )
    if projection.case_scope_digest != expected_scope:
        raise PrivateCaseRuntimeBridgeError("CCL registration case scope digest mismatch")
    if any(item.case_scope_digest != expected_scope for item in projection.documents):
        raise PrivateCaseRuntimeBridgeError("CCL registration document scope mismatch")

    projection_digest = digest_hex(projection.projection_id)
    if not runtime_identity.evidence_inventory_declared:
        raise PrivateCaseRuntimeBridgeError("runtime identity must declare evidence inventory")
    if projection_digest not in runtime_identity.evidence_digests:
        raise PrivateCaseRuntimeBridgeError("runtime identity does not bind projection evidence")
    return ledger.append_event(
        case_id=CaseId(projection.case_id),
        event_type=EVENT_PRIVATE_EVIDENCE_REGISTERED,
        runtime_identity=runtime_identity,
        payload=projection.ccl_payload(),
        expected_head=expected_head,
    )
