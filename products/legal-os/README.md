# LUKART LEGAL OS — ROS subsystem

Status: **READ-ONLY SHADOW CANDIDATE / NOT PRODUCT-ADMITTED**.

Canonical name LUKART LEGAL OS. This is the intended legal-product boundary under LUKART ROS. The existing LUKART WORK repository retains the authoritative draft, persistence, DOCX/PDF, package and native human-approval contracts until an independently validated cutover.

## First implemented integration seam

`core/operations/legal_os_readonly_v1.py` offers *only* `ros.work.generator.assess.v1` over the existing LUKART Operation Contract v1. It uses existing ROS privacy scope, expected HEAD / CAS, bounded input and idempotency semantics. A trusted host **must** resolve a scoped native WORK read capability and pass a separate native WORK snapshot reader; neither callback is implemented or invoked automatically outside a trusted host. If unavailable, the operation blocks. The returned receipt holds only provenance identity and a digest, not client source bytes.

The adapter deliberately rejects unknown document types, all caller-provided human/legal verdict fields, write effects and execute/read-package operations. It creates no new CASE ledger, legal engine, drafting engine, renderer, validation authority, signing or sending mechanism. A successful **read** is not proof that WORK content or its document type was legally or technically admitted.

## Existing assurance authority

ROS `docs/PRIVATE_CASE_OPERATING_STANDARD.md` v1.3.0 remains authoritative for G0-G8, Red Team, Hardcore Preflight, G7.5 FINISH, ZERO SILENT LOSS and real-case HUMAN approval. Native WORK HG-01..HG-09 gates must be mapped by pinned evidence and separate typed authorizations. `contracts/ros_work/v1/integration-contract.json` in WORK remains historical PLANNED_NOT_IMPLEMENTED; this branch does not claim execute/read-package conformance.

## Next release blockers

- Independent A2 technical review of the exact WORK PR #64 candidate.
- Genuine HUMAN legal/type review for each supported document category, issue #67.
- Host-side trusted WORK capability/read adapter; cross-repo and negative conformance evidence.
- Versioned G0-G8/HG gate mapping and exact-artifact G7.5 FINISH.
- Production model executor, privacy/security, controlled go-live, explicit merge/promotion authority and post-merge validation.

No real-case data in GitHub. No automatic external filing, legal conclusion, human approval, or paid model/provider fallback.
