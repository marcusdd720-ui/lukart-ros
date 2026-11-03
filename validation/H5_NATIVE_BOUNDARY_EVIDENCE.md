# H5 native boundary repair — 2026-11-03

Scope: real ROS adapter → WORK operator_host HTTP → existing isolated PostgreSQL18 on loopback65432. No paid model, real case or legal approval. This is NOT full H5 PASS.

## Confirmed defect and repair

The PR380 assess mapper emitted a command-shaped envelope. Native WORK CoreQuery JSON parsing rejected four fields: required top-level tenant_id and case_id were missing; command meta and rationale were forbidden. A new cross-repository regression reproduced the rejection. The mapper now emits exactly contract, operation=GetCaseHead, tenant_id and case_id from trusted scope. Caller-supplied assess payload is refused. The ROS request digest and idempotency key remain on the mapped request; the read-only WORK query does not accept command metadata.

## Evidence

- ROS base e8e6092b36da52bcda4bd1ce8d2faa89f9828307 (PR380), isolated branch h5/native-assess-recovery-20261103.
- WORK checkout7a924f37696cdf74666c08f924f1941edb4fc030; not silently substituted with a later candidate.
- Strict native CoreQuery JSON regression: PASS.
- Updated adapter suite:24/24 PASS, exit0.
- Targeted ruff: PASS.
- Native HTTP→actual WORK service→PostgreSQL: PASS.
- Controlled HTTP server shutdown/recreation and replay on the same durable synthetic CASE: PASS, unchanged case sequence.
- Unadmitted execute: denied before dispatch, unchanged case sequence.
- Receipt: h5-native-after.json. It explicitly reports full_h5=BLOCKED and NATIVE_HTTP_ASSESS_ONLY.

## Environment recovery

Original WORK cluster found at C:/Users/LukaszA/Projects/lukart-work/.local-stage02/data with authoritative postmaster.opts selecting PostgreSQL18 and port65432. pg_ctl confirmed stopped; startup reused existing data/config. Interrupted-cluster fsync/recovery completed at09:59:10 CET. No role/password/HBA changes, no database overwrite, no cluster kill. Existing API8765/Gateway were not modified. The initially tried LUKART_LEGAL_OS/postgres18 cluster is unrelated (55432) and was not altered.

## Remaining exact boundary

WORK docs/ROS_WORK_CAPABILITY_GAP_V1.md contract-operations section forbids positive execute/package conformance fixtures while PB02/PB03 independent acceptance and supported-type admission remain open. The positive generator fixture already passed historically; it cannot stand in for native ROS orchestration or independent/HUMAN acceptance. No flags or authority records were flipped to bypass this gate.

Reviewable admission input is H5_ADMISSION_REQUEST.json. Full CASE→DOCX/PDF→FINISH with native adapter and full pipeline process-crash/recovery remains NOT VERIFIED, not simulated as PASS. Protected main merge and production go-live remain outside this branch authorization.
