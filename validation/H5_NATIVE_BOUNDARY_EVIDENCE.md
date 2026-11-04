# H5 native boundary evidence — historical record only (2026-11-03)

> **HISTORICAL ONLY — NOT A PASS FOR THE CURRENT PR #381 CANDIDATE.** The successful native HTTP→WORK operator_host→PostgreSQL probe recorded below ran against ROS `e8e6092b36da52bcda4bd1ce8d2faa89f9828307` and WORK `7a924f37696cdf74666c08f924f1941edb4fc030`. It must not be carried forward to the current candidate.

## Current candidate status (2026-11-04)

- ROS candidate SHA: authoritative value is `IRR-01/manifest.json.source_commit_sha` in the review package containing this file (avoids a self-referential hardcoded SHA).
- WORK candidate SHA: `fb8850431d34c0a204d8e1c425914442af151325`.
- Current native `NATIVE_HTTP_ASSESS_ONLY` integration run: **NOT RUN**.
- Current positive execute/package admission: **NOT ADMITTED**.
- Full H5: **BLOCKED / NOT VERIFIED**.
- The current PR contains the adapter, guard tests and assess-only harness, but local unit/guard tests are not native HTTP→PostgreSQL integration evidence.
- The historical PASS below is not reusable for the current ROS/WORK candidate pair.

## Historical run — 2026-11-03 only

Scope: real ROS adapter → WORK operator_host HTTP → existing isolated PostgreSQL 18 on loopback port 65432. No paid model, real case or legal approval. This was **not** full H5 PASS.

### Confirmed defect and historical repair

The earlier PR380 assess mapper emitted a command-shaped envelope. Native WORK CoreQuery JSON parsing rejected four fields: required top-level `tenant_id` and `case_id` were missing; command metadata and rationale were forbidden. A cross-repository regression reproduced the rejection. The mapper was changed to emit the exact contract, `operation=GetCaseHead`, `tenant_id` and `case_id` from trusted scope. Caller-supplied assess payload was refused. The ROS request digest and idempotency key remained on the mapped request; the read-only WORK query did not accept command metadata.

### Historical evidence (bound only to the SHAs above)

- ROS: `e8e6092b36da52bcda4bd1ce8d2faa89f9828307` (PR380), isolated branch `h5/native-assess-recovery-20261103`.
- WORK: `7a924f37696cdf74666c08f924f1941edb4fc030`; not silently substituted with a later candidate.
- Strict native CoreQuery JSON regression: PASS.
- Updated adapter suite: 24/24 PASS, exit 0.
- Targeted Ruff: PASS.
- Native HTTP→actual WORK service→PostgreSQL: PASS.
- Controlled HTTP server shutdown/recreation and replay on the same durable synthetic CASE: PASS, unchanged case sequence.
- Unadmitted execute: denied before dispatch, unchanged case sequence.
- Historical receipt: `h5-native-after.json`; it reported `full_h5=BLOCKED` and `NATIVE_HTTP_ASSESS_ONLY`.

### Historical environment recovery

The historical run reused an existing isolated WORK PostgreSQL 18 data directory in a local project workspace, with the service on loopback port 65432. `pg_ctl` confirmed the cluster was stopped; startup reused its existing data/configuration and completed interrupted-cluster recovery. No role, password or HBA changes, database overwrite or cluster kill occurred. Existing API/Gateway services were not modified. An unrelated test cluster on port 55432 was not altered. Exact local filesystem paths and usernames are intentionally omitted from this public review evidence.

## Remaining exact boundary

The WORK `ROS_WORK_CAPABILITY_GAP_V1.md` contract-operations section forbids positive execute/package conformance fixtures while PB02/PB03 independent acceptance and supported-type admission remain open. A historical positive generator fixture cannot stand in for native ROS orchestration or independent/HUMAN acceptance.

The review input is `H5_ADMISSION_REQUEST.json`. Current-candidate native HTTP assess-only execution has not been performed. Full CASE→DOCX/PDF→HUMAN→FINAL→FINISH with native adapter and full pipeline process-crash/recovery remains **NOT VERIFIED**, not simulated as PASS. Protected main merge and production go-live remain outside this branch authorization.
