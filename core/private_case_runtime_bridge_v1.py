"""Verified non-cloud bridge from encrypted private evidence into local runtime/CCL.

CASE-OPS-02 treats the plaintext compatibility inventory as untrusted. The runtime
projection is reconstructed only from an encrypted DERIVED inventory and verified
CASE-OPS-01 evidence objects. CCL registration remains an explicit digest-only write
through the existing CanonicalCaseLedger.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from core.case_ledger.contracts import CaseId, ContentAddress, LedgerEvent
from core.case_ledger.ledger import CanonicalCaseLedger
from core.enterprise.contracts import AuthorizationContext, EnterpriseContractError, Permission
from core.p3.contracts import RuntimeIdentity
from core.private_evidence_v1 import (
    SCHEMA_MANIFEST,
    EvidenceKind,
    ImportedEvidence,
    PrivateEvidenceError,
    PrivateEvidenceStore,
    canonical_json,
    digest_hex,
    digest_object,
    opaque_digest,
)

SCHEMA_RUNTIME_INVENTORY = "lukart.private-case-runtime-inventory.v1"
SCHEMA_RUNTIME_PROJECTION = "lukart.private-case-runtime-projection.v1"
EVENT_PRIVATE_EVIDENCE_REGISTERED = "private.evidence.projection.registered.v1"
RUNTIME_INVENTORY_SOURCE_REF = "case-ops-runtime-inventory:v1"
_DOCUMENT_ID = re.compile(r"DOC-(\d{3})\Z")
_EXPECTED_INVENTORY_KEYS = frozenset(
    {
        "document_id",
        "evidence_id",
        "manifest_digest",
        "receipt_digest",
        "extracted_evidence_id",
        "extracted_receipt_digest",
        "source_name_digest",
        "sha256",
        "document_type",
        "extraction_method",
        "local_only",
    }
)
_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "evidence_id",
        "plaintext_sha256",
        "size_bytes",
        "media_type",
        "evidence_kind",
        "case_scope_digest",
        "source_ref_digest",
        "envelope_digest",
        "algorithm",
        "key_id",
        "key_version",
    }
)
_RECEIPT_KEYS = frozenset(
    {
        "schema",
        "evidence_id",
        "manifest_digest",
        "case_scope_digest",
        "source_ref_digest",
        "imported_at",
        "operation",
    }
)
_IMPORT_RECEIPT_SCHEMA = "lukart.evidence-import-receipt.v1"
_SOURCE_INDEX_SCHEMA = "lukart.private-evidence-source-index.v1"


class PrivateCaseRuntimeBridgeError(RuntimeError):
    """Fail-closed error at the CASE-OPS-02 runtime/CCL trust boundary."""


@dataclass(frozen=True, slots=True)
class VerifiedLocalDocumentV1:
    document_id: str
    evidence_id: str
    manifest_digest: str
    receipt_digest: str
    derived_evidence_id: str
    derived_manifest_digest: str
    derived_receipt_digest: str
    case_scope_digest: str
    primary_media_type: str
    derived_media_type: str

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
        """Return only digest-bound evidence references; never plaintext or source names."""
        return {
            "schema": self.schema,
            "projection_id": self.projection_id,
            "case_scope_digest": self.case_scope_digest,
            "documents": [
                {
                    "document_id": item.document_id,
                    "evidence_id": item.evidence_id,
                    "manifest_digest": item.manifest_digest,
                    "receipt_digest": item.receipt_digest,
                    "derived_evidence_id": item.derived_evidence_id,
                    "derived_manifest_digest": item.derived_manifest_digest,
                    "derived_receipt_digest": item.derived_receipt_digest,
                }
                for item in self.documents
            ],
        }


def runtime_inventory_payload(documents: Sequence[Mapping[str, object]]) -> bytes:
    return canonical_json(
        {
            "schema": SCHEMA_RUNTIME_INVENTORY,
            "documents": [dict(item) for item in documents],
        }
    )


def _object_path(root: Path, category: str, digest: str) -> Path:
    value = digest_hex(digest)
    base = root / category
    target = base / value[:2] / f"{value}.json"
    if base.is_symlink() or target.parent.is_symlink():
        raise PrivateCaseRuntimeBridgeError("private evidence object path contains a symlink")
    return target


def _load_mapping(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PrivateCaseRuntimeBridgeError("required private evidence object is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateCaseRuntimeBridgeError("invalid private evidence JSON object") from exc
    if not isinstance(value, dict):
        raise PrivateCaseRuntimeBridgeError("private evidence JSON object must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise PrivateCaseRuntimeBridgeError("private evidence JSON keys must be strings")
    return value


def _content_id(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise PrivateCaseRuntimeBridgeError(f"{field} must be a sha256 content identifier")
    try:
        digest_hex(value)
    except PrivateEvidenceError as exc:
        raise PrivateCaseRuntimeBridgeError(f"{field} is invalid") from exc
    return value


def _strict_manifest(imported: ImportedEvidence) -> dict[str, object]:
    manifest = _load_mapping(imported.manifest_path)
    if set(manifest) != _MANIFEST_KEYS or manifest.get("schema") != SCHEMA_MANIFEST:
        raise PrivateCaseRuntimeBridgeError("unsupported private evidence manifest schema")
    if digest_object(manifest) != imported.manifest_digest:
        raise PrivateCaseRuntimeBridgeError("private evidence manifest digest mismatch")
    if manifest.get("evidence_id") != imported.evidence_id:
        raise PrivateCaseRuntimeBridgeError("private evidence manifest identity mismatch")
    return manifest


def _resolve_imported(
    store: PrivateEvidenceStore,
    *,
    evidence_id: str,
    manifest_digest: str,
    receipt_digest: str,
) -> ImportedEvidence:
    evidence_id = _content_id(evidence_id, field="evidence_id")
    manifest_digest = _content_id(manifest_digest, field="manifest_digest")
    receipt_digest = _content_id(receipt_digest, field="receipt_digest")
    receipt_path = _object_path(store.root, "receipts", receipt_digest)
    receipt = _load_mapping(receipt_path)
    if set(receipt) != _RECEIPT_KEYS or receipt.get("schema") != _IMPORT_RECEIPT_SCHEMA:
        raise PrivateCaseRuntimeBridgeError("unsupported evidence receipt schema")
    if digest_object(receipt) != receipt_digest:
        raise PrivateCaseRuntimeBridgeError("evidence receipt digest mismatch")
    if receipt.get("evidence_id") != evidence_id:
        raise PrivateCaseRuntimeBridgeError("evidence receipt identity mismatch")
    if receipt.get("manifest_digest") != manifest_digest:
        raise PrivateCaseRuntimeBridgeError("evidence receipt manifest mismatch")
    if receipt.get("case_scope_digest") != store.case_scope_digest:
        raise PrivateCaseRuntimeBridgeError("evidence receipt belongs to a different case scope")

    manifest_path = _object_path(store.root, "manifests", manifest_digest)
    raw_manifest = _load_mapping(manifest_path)
    envelope_digest = _content_id(raw_manifest.get("envelope_digest"), field="envelope_digest")
    imported = ImportedEvidence(
        evidence_id=evidence_id,
        manifest_digest=manifest_digest,
        receipt_digest=receipt_digest,
        manifest_path=manifest_path,
        receipt_path=receipt_path,
        envelope_path=_object_path(store.root, "objects", envelope_digest),
    )
    try:
        store.verify(imported)
    except PrivateEvidenceError as exc:
        raise PrivateCaseRuntimeBridgeError("private evidence verification failed") from exc
    manifest = _strict_manifest(imported)
    if manifest.get("case_scope_digest") != store.case_scope_digest:
        raise PrivateCaseRuntimeBridgeError("private evidence manifest has wrong case scope")
    return imported


def _resolve_from_receipt(
    store: PrivateEvidenceStore,
    *,
    evidence_id: str,
    receipt_digest: str,
) -> ImportedEvidence:
    receipt_digest = _content_id(receipt_digest, field="derived_receipt_digest")
    receipt = _load_mapping(_object_path(store.root, "receipts", receipt_digest))
    manifest_digest = _content_id(
        receipt.get("manifest_digest"), field="derived_manifest_digest"
    )
    return _resolve_imported(
        store,
        evidence_id=evidence_id,
        manifest_digest=manifest_digest,
        receipt_digest=receipt_digest,
    )


def _verify_inventory_entry(
    store: PrivateEvidenceStore,
    item: Mapping[str, object],
) -> VerifiedLocalDocumentV1:
    if set(item) != _EXPECTED_INVENTORY_KEYS:
        raise PrivateCaseRuntimeBridgeError("runtime inventory fields do not match v1 contract")
    if item.get("local_only") is not True:
        raise PrivateCaseRuntimeBridgeError("runtime inventory must remain local-only")
    document_id = item.get("document_id")
    if not isinstance(document_id, str):
        raise PrivateCaseRuntimeBridgeError("document_id is invalid")
    match = _DOCUMENT_ID.fullmatch(document_id)
    if match is None or int(match.group(1)) < 1:
        raise PrivateCaseRuntimeBridgeError("document_id is not a canonical document slot")
    slot = int(match.group(1))

    evidence_id = _content_id(item.get("evidence_id"), field="evidence_id")
    manifest_digest = _content_id(item.get("manifest_digest"), field="manifest_digest")
    receipt_digest = _content_id(item.get("receipt_digest"), field="receipt_digest")
    primary = _resolve_imported(
        store,
        evidence_id=evidence_id,
        manifest_digest=manifest_digest,
        receipt_digest=receipt_digest,
    )
    primary_manifest = _strict_manifest(primary)
    if primary_manifest.get("evidence_kind") != EvidenceKind.PRIMARY.value:
        raise PrivateCaseRuntimeBridgeError("runtime primary reference is not PRIMARY evidence")
    if primary_manifest.get("source_ref_digest") != opaque_digest(f"document-slot:{slot}"):
        raise PrivateCaseRuntimeBridgeError("document slot is not bound to primary evidence")
    if item.get("sha256") != digest_hex(evidence_id):
        raise PrivateCaseRuntimeBridgeError("runtime inventory plaintext digest mismatch")
    _content_id(item.get("source_name_digest"), field="source_name_digest")
    if item.get("document_type") != "real_case":
        raise PrivateCaseRuntimeBridgeError("runtime inventory requires real_case document type")
    extraction_method = item.get("extraction_method")
    if not isinstance(extraction_method, str) or not extraction_method.strip():
        raise PrivateCaseRuntimeBridgeError("runtime inventory extraction method is invalid")

    derived_evidence_id = _content_id(
        item.get("extracted_evidence_id"), field="derived_evidence_id"
    )
    derived_receipt_digest = _content_id(
        item.get("extracted_receipt_digest"), field="derived_receipt_digest"
    )
    derived = _resolve_from_receipt(
        store,
        evidence_id=derived_evidence_id,
        receipt_digest=derived_receipt_digest,
    )
    derived_manifest = _strict_manifest(derived)
    if derived_manifest.get("evidence_kind") != EvidenceKind.DERIVED.value:
        raise PrivateCaseRuntimeBridgeError("runtime derived reference is not DERIVED evidence")
    if derived_manifest.get("source_ref_digest") != opaque_digest(f"derived-text:{evidence_id}"):
        raise PrivateCaseRuntimeBridgeError("derived text is not bound to primary evidence")
    if derived_manifest.get("media_type") != "text/plain":
        raise PrivateCaseRuntimeBridgeError("derived runtime evidence must be text/plain")

    return VerifiedLocalDocumentV1(
        document_id=document_id,
        evidence_id=evidence_id,
        manifest_digest=manifest_digest,
        receipt_digest=receipt_digest,
        derived_evidence_id=derived_evidence_id,
        derived_manifest_digest=derived.manifest_digest,
        derived_receipt_digest=derived_receipt_digest,
        case_scope_digest=store.case_scope_digest,
        primary_media_type=str(primary_manifest.get("media_type")),
        derived_media_type=str(derived_manifest.get("media_type")),
    )


def _projection_from_documents(
    store: PrivateEvidenceStore,
    documents: Sequence[Mapping[str, object]],
) -> VerifiedLocalEvidenceProjectionV1:
    verified = tuple(_verify_inventory_entry(store, item) for item in documents)
    expected_ids = tuple(f"DOC-{index:03d}" for index in range(1, len(verified) + 1))
    if tuple(item.document_id for item in verified) != expected_ids:
        raise PrivateCaseRuntimeBridgeError("runtime document slots must be contiguous and ordered")
    if len({item.evidence_id for item in verified}) != len(verified):
        raise PrivateCaseRuntimeBridgeError("duplicate primary evidence in runtime inventory")
    return VerifiedLocalEvidenceProjectionV1(
        schema=SCHEMA_RUNTIME_PROJECTION,
        case_id=store.case_id,
        case_scope_digest=store.case_scope_digest,
        documents=verified,
    )


def load_verified_projection(store: PrivateEvidenceStore) -> VerifiedLocalEvidenceProjectionV1:
    """Load the encrypted runtime inventory and verify every referenced evidence object."""
    source_ref_digest = opaque_digest(RUNTIME_INVENTORY_SOURCE_REF)
    index = _load_mapping(_object_path(store.root, "source-index", source_ref_digest))
    if set(index) != {"schema", "evidence_id", "manifest_digest", "receipt_digest"}:
        raise PrivateCaseRuntimeBridgeError("runtime inventory source index fields are invalid")
    if index.get("schema") != _SOURCE_INDEX_SCHEMA:
        raise PrivateCaseRuntimeBridgeError("unsupported runtime inventory source index schema")
    inventory = _resolve_imported(
        store,
        evidence_id=_content_id(index.get("evidence_id"), field="inventory_evidence_id"),
        manifest_digest=_content_id(
            index.get("manifest_digest"), field="inventory_manifest_digest"
        ),
        receipt_digest=_content_id(
            index.get("receipt_digest"), field="inventory_receipt_digest"
        ),
    )
    manifest = _strict_manifest(inventory)
    if manifest.get("evidence_kind") != EvidenceKind.DERIVED.value:
        raise PrivateCaseRuntimeBridgeError("runtime inventory object must be DERIVED evidence")
    if manifest.get("media_type") != "application/json":
        raise PrivateCaseRuntimeBridgeError("runtime inventory object must be application/json")
    if manifest.get("source_ref_digest") != source_ref_digest:
        raise PrivateCaseRuntimeBridgeError("runtime inventory source identity mismatch")
    try:
        decoded = json.loads(store.read(inventory).decode("utf-8"))
    except (PrivateEvidenceError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateCaseRuntimeBridgeError("encrypted runtime inventory cannot be decoded") from exc
    if not isinstance(decoded, dict) or set(decoded) != {"schema", "documents"}:
        raise PrivateCaseRuntimeBridgeError("runtime inventory payload fields are invalid")
    if decoded.get("schema") != SCHEMA_RUNTIME_INVENTORY:
        raise PrivateCaseRuntimeBridgeError("unsupported encrypted runtime inventory schema")
    documents = decoded.get("documents")
    if not isinstance(documents, list) or any(not isinstance(item, dict) for item in documents):
        raise PrivateCaseRuntimeBridgeError("runtime inventory documents are invalid")
    return _projection_from_documents(store, documents)


def migrate_legacy_inventory(
    store: PrivateEvidenceStore,
    inventory_path: Path,
) -> VerifiedLocalEvidenceProjectionV1:
    """Verify and encrypt one CASE-OPS-01 compatibility inventory; reruns are idempotent."""
    if inventory_path.is_symlink() or not inventory_path.is_file():
        raise PrivateCaseRuntimeBridgeError("legacy inventory must be a regular non-symlink file")
    try:
        decoded = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateCaseRuntimeBridgeError("legacy inventory is invalid JSON") from exc
    if not isinstance(decoded, list) or any(not isinstance(item, dict) for item in decoded):
        raise PrivateCaseRuntimeBridgeError("legacy inventory must be a list of mappings")
    projection = _projection_from_documents(store, decoded)
    try:
        store.import_bytes(
            runtime_inventory_payload(decoded),
            source_ref=RUNTIME_INVENTORY_SOURCE_REF,
            kind=EvidenceKind.DERIVED,
            media_type="application/json",
        )
    except PrivateEvidenceError as exc:
        raise PrivateCaseRuntimeBridgeError("legacy runtime inventory migration failed") from exc
    rebuilt = load_verified_projection(store)
    if rebuilt != projection:
        raise PrivateCaseRuntimeBridgeError("runtime inventory migration verification mismatch")
    return rebuilt


def register_projection_in_ccl(
    *,
    ledger: CanonicalCaseLedger,
    projection: VerifiedLocalEvidenceProjectionV1,
    runtime_identity: RuntimeIdentity,
    authorization: AuthorizationContext,
    expected_head: ContentAddress | None,
) -> LedgerEvent:
    """Append one verified digest-only projection event to the sole canonical case ledger."""
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
