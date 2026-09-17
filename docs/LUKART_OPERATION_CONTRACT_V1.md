# LUKART Operation Contract v1

Status: H3 canonical operation-boundary contract.

## Decision and ownership

`lukart-ros` owns the canonical, transport-independent contract. ChatGPT, Work and future
clients are adapters; none may fork its semantics. The schema id is
`lukart.operation-contract.v1`, version `1.0`.

The envelope has exactly ten top-level sections:
`request / context / preconditions / constraints / idempotency / effects / output / evidence /
errors / privacy`.

`core/operations/contract_v1.py` is the semantic facade and
`schemas/lukart_operation_contract_v1.schema.json` is the machine-readable interchange schema.
Runtime validation enforces invariants that JSON Schema alone cannot safely express.

## Invariants

- Unknown schema id/version fails closed.
- Canonical JSON is key-sorted and whitespace-free; SHA-256 binds request/result receipts.
- Request and response envelopes are validated and bounded.
- Raw credential fields are rejected; adapters use opaque authority/lock references.
- `expected_head` is an exact lowercase 40-character SHA and stale CAS blocks before execution.
- Privacy scope must match exactly; v1 never allows cross-scope execution.
- Effects are declared before execution; undeclared effects can never produce `success`.
- Required evidence is explicit; a `commit` effect requires exact commit-SHA evidence.
- Timeout, missing evidence or errors can never survive as false `success`.
- Same idempotency key + same request digest replays exactly; a different digest is blocked.
- Concurrent identical invocations execute the handler once and replay the stored result.
- Status is one of `success`, `failure`, `partial`, `skipped`, `blocked`.
- Unexpected handler exceptions use deterministic diagnostics and do not expose exception text.

## Lifecycle and receipt

A request uses the full envelope with `output.status=null`, no actual effects/evidence/errors and
explicit declared constraints. A response reuses the same envelope with a final status, actual
effects, artifacts, evidence and normalized errors.

`OperationRuntime.execute()` returns the validated `envelope` and a
`lukart.operation-receipt.v1` containing request/result digests, status, artifact references and
evidence references. The receipt intentionally excludes raw request input.

## CAS, idempotency and concurrency

`preconditions.expected_head` is compared with the parent runtime's observed `current_head`.
Mismatch produces `blocked / STALE_HEAD` before handler invocation. Repository adapters remain
responsible for enforcing their native atomic write against that same head.

The reference runtime maintains a process-local condition-protected idempotency ledger. The first
request reserves the key. An identical concurrent request waits within its deadline and replays the
stored execution; a different request digest returns `blocked / IDEMPOTENCY_CONFLICT`. Production
adapters may persist the ledger but must preserve these semantics.

## Timeout and evidence

The Python reference uses a cooperative monotonic deadline: arbitrary callbacks cannot be killed
safely without risking post-timeout effects. Handlers receive the deadline and must honor it. The
runtime post-checks elapsed time and never reports `success` after expiry: reported effects yield
`partial`; otherwise the result is `failure`. A parent process may impose a stronger timeout.

Evidence records contain `kind`, `ref` and optional exact `sha` or SHA-256 `digest`. Missing
required evidence prohibits success. A reported `commit` additionally requires a full commit SHA;
branch names, PR numbers and mutable refs are not exact-SHA evidence.

## Privacy and client readiness

`privacy.scope` must equal both `constraints.privacy_scope` and the runtime scope;
`cross_scope_allowed=false`. Tokens, passwords, cookies, private keys and credentials remain in
the native secret store and only opaque references enter the contract.

A Work/client adapter builds the canonical request, supplies opaque authority/lock references and
exact observed head, invokes the parent-owned handler, returns the result/receipt unchanged, and
may persist idempotency or add stronger timeout/transaction guarantees without changing semantics.
Work is a client, not the owner of H3.

## Compatibility

H3 is additive: existing `core.enterprise`, `core.p3` and CASE contracts are unchanged. New
integrations opt into v1. Future incompatible semantics require a new schema/version identifier;
unknown versions fail closed.

See `docs/H3_OPERATION_CONTRACT_COVERAGE.md` for requirements coverage, Red Team and preflight.
