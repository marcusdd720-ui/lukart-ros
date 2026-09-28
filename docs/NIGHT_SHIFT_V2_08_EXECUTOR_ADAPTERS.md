# Night Shift V2-08 — Executor Adapters

Status: VALIDATED STAGING CANDIDATE  
Recorded: 2026-09-28

## Objective

Bind capability routing to real, evidence-bearing executor implementations.

V2-08 closes the gap between an `ExecutorProfile` declaration and executable authority.
A routed executor is not executable merely because it exists in the profile registry.

## Binding states

- `VALIDATED` — a repository-owned adapter implementation exists and must match its profile.
- `DOCUMENTED_ONLY` — capability is known but execution fails closed.
- `DISABLED` — execution fails closed.

Current bindings:

- `deterministic_local` -> `process_isolation` -> `VALIDATED`;
- `codex_adapter` -> `external_provider` -> `DOCUMENTED_ONLY`;
- `independent_reviewer` -> `external_review` -> `DOCUMENTED_ONLY`.

Therefore V2-08 does not grant autonomous Codex/Work execution authority.

## Validated local adapter

The reference adapter reuses the existing enterprise `ProcessIsolationExecutor` and requires:

- separate child process;
- hard timeout termination;
- environment sanitization;
- temporary workspace;
- Python audit-hook capability enforcement;
- network denied for the probe;
- explicit allow-listed entrypoint.

Execution returns content-addressed request, output and isolation-control evidence.

## Fail-closed rules

- route executor ID must equal request executor ID;
- binding must exist;
- binding status must be `VALIDATED`;
- implementation must exist;
- adapter kind must equal binding kind;
- adapter mutating capability must equal profile mutating capability;
- adapter capabilities must satisfy the executor profile;
- request capabilities may not exceed the routed profile;
- read-only adapter may not execute a mutating request;
- the validated process-isolation adapter must deny network access;
- the validated process-isolation adapter must deny child-process spawning;
- the validated process-isolation adapter must deny native FFI;
- writes must remain restricted to the temporary workspace;
- returned isolation-control evidence must prove those restrictions;
- a `DOCUMENTED_ONLY` adapter may not expose an implementation.

## Repository-owned probe

`python scripts/night_shift_executor_adapter_probe.py`

Expected result:

- executor: `deterministic_local`;
- adapter: `process_isolation`;
- output status: `PASS`;
- request/output/isolation digests present;
- no network authority;
- no external provider invocation.

## Autonomy boundary

`codex_adapter` remains fail-closed until a provider adapter has repository-owned validation
and explicit policy authority. `independent_reviewer` is treated the same way.

Planned != Implemented != Validated != Certified.  
Evidence Before Conclusion.

## Validation evidence

Local validation before staging freeze:

- focused V2-08 adapter/routing/isolation tests: PASS;
- full Night Shift test set: PASS across 31 test files;
- Ruff: PASS;
- Mypy Linux target: PASS across 857 source files;
- repository audit: PASS;
- PII/confidentiality gate: PASS;
- secret scanning: PASS;
- repository-owned executor adapter probe: PASS;
- validated executor: `deterministic_local`;
- validated adapter kind: `process_isolation`;
- external provider adapters remain `DOCUMENTED_ONLY` and fail closed.
