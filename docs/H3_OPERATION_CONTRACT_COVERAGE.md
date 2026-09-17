# H3 Operation Contract v1 — coverage and preflight

## Requirements → tests → evidence

- Happy path + receipt — `test_happy_path_and_receipt_are_evidence_bound`:
  success, SHA and digests.
- Invalid schema — `test_invalid_schema_fails_closed`: fail-closed exception.
- Unsupported version — `test_unsupported_version_fails_closed`: fail-closed exception.
- Missing authority — `test_missing_authority_is_rejected_before_execution`:
  pre-handler rejection.
- CAS stale head — `test_stale_head_blocks_without_calling_handler`:
  `STALE_HEAD`, zero handler calls.
- Exact retry — `test_identical_retry_replays_exact_execution_once`:
  identical result, one handler call.
- Retry after HEAD change — `test_identical_retry_replays_after_repository_head_changes`:
  exact stored execution, one handler call.
- Duplicate key — `test_duplicate_key_with_different_digest_is_blocked`:
  idempotency conflict.
- Timeout — `test_timeout_can_never_report_success`: `TIMEOUT`, no false success.
- Partial — `test_timeout_after_reported_effect_is_partial`: `partial` after effect.
- Missing evidence — `test_missing_required_evidence_prevents_success`:
  `EVIDENCE_MISSING`.
- Privacy mismatch — `test_privacy_mismatch_blocks_before_handler`: pre-handler block.
- Concurrent invocation — `test_concurrent_identical_invocation_executes_handler_once`:
  one handler call.
- Determinism — `test_replay_and_serialization_are_deterministic`: stable bytes/digests.
- Hidden effect — `test_undeclared_side_effect_can_never_be_success`: no success.
- Exact commit SHA — `test_commit_effect_requires_exact_sha_evidence`:
  exact-SHA requirement.
- Secret minimization — `test_raw_secret_fields_are_rejected`: fail-closed rejection.
- Schema alignment — `test_machine_readable_schema_matches_runtime_contract`:
  parsed schema.
- Direct false success —
  `test_direct_response_validation_rejects_false_success_without_evidence`: rejection.
- Canonical request — `test_request_rejects_prefilled_result_fields`:
  request-only result fields rejected.
- Canonical identifiers — `test_uppercase_sha_is_not_silently_canonicalized`:
  noncanonical SHA rejected.
- JSON finiteness — `test_non_finite_input_number_is_rejected`: NaN rejected.
- Secret suffix — `test_common_secret_suffix_is_rejected`: token field rejected.

## Red Team

Adversarial review must confirm:

- stale clients cannot reach the handler before CAS passes;
- retries cannot duplicate a side effect and concurrent duplicates execute once;
- one idempotency key cannot be rebound to a different canonical request;
- timeout cannot report success, including after a reported effect;
- mutable refs cannot masquerade as exact commit evidence;
- unexpected exception text is not reflected into public diagnostics;
- known raw credential fields are rejected;
- privacy scope cannot cross CASE boundaries;
- undeclared effects cannot result in success;
- unknown schema versions are never interpreted permissively.

Any CRITICAL/HIGH finding blocks `MERGE_READY` until repaired and retested.

## Hardcore Preflight

H3 is `MERGE_READY` only if all of the following are PASS on the exact PR head:

- H3 commits are GitHub verified/signed;
- diff is limited to Operation Contract v1 implementation, schema, tests and docs;
- secret/PII gates show no leakage;
- required CI checks are green on the exact head SHA;
- conformance/adversarial suite passes;
- CAS, idempotency, concurrency, privacy, timeout, evidence and status semantics pass;
- request/result serialization and diagnostics are deterministic;
- existing contracts remain backward compatible because H3 is additive;
- docs and schema describe the implemented contract;
- Red Team has no unresolved CRITICAL/HIGH findings.

`MERGE_READY` is not merge authorization. Merge remains a separate explicit action.
