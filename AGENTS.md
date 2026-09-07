# LUKART ROS / KOS — AGENTS.md

Status: Active repository-specific agent bootstrap
Scope: Repository-wide

## Authority

All contributors, coding agents, reviewers and automation MUST read and obey `docs/WORKING_PRINCIPLES.md`. It is the **single canonical living execution/trust standard**.

This file MUST remain a thin repository-specific bridge. It MUST NOT duplicate the full operating standard. If this file appears to conflict with `docs/WORKING_PRINCIPLES.md`, an Accepted ADR, or an explicit safety/privacy invariant, stop the conflicting action, preserve the safer state and resolve the contradiction in the canonical source rather than creating another rule list.

Memory, previous chats, summaries and previous agent output are non-authoritative for live repository state. Before substantive work, verify live `main`, current stage/PR, exact PR-head/candidate SHA and required CI. GitHub state wins when stale context differs.

## Repository invariants

- Historical release `v1.0.1` is immutable. Do not move/rewrite its tag, target commit, Gold/certification evidence or historical closure.
- Canonical Case Ledger is the sole authoritative writable SSOT for case history.
- Gold/evidence are immutable inputs; epistemic state, trust graphs, reasoning, KQM, renderer/search and propagation are projections/derived artifacts, not parallel truth authorities.
- Factory infrastructure may validate/protect Product semantics but may not create epistemic truth or independent certification.
- Real case data and sensitive identifiers are local-only. Public GitHub/Actions may contain only approved code, documentation and synthetic/anonymized fixtures. A privacy-boundary violation is FATAL: do not propagate it.
- Unknown trust-boundary state fails closed.

## Execution

For accepted work, execute the no-stop lifecycle in `docs/WORKING_PRINCIPLES.md` end-to-end. A branch, commit, PR, partial PASS, running CI or repairable FAIL is not a stopping point.

After any result-affecting change:
1. create/use the fresh candidate SHA;
2. invalidate older candidate evidence;
3. validate required checks on that exact SHA;
4. merge only the unchanged validated PR head;
5. validate exact resulting `main`;
6. close only after post-merge evidence satisfies Definition of Done.

Do not ask for confirmation between already-approved reversible technical steps. Stop only on a true `HARD BLOCKER` as defined by the canonical standard.

## Validation surfaces

Use repository-native tooling and current workflows rather than inventing parallel gates. Typical local/static sequence when applicable:

```bash
uv sync --frozen --extra dev
uv run --frozen --extra dev python -m ruff check .
uv run --frozen --extra dev python -m mypy .
uv run --frozen --extra dev python -m pytest
```

Also run focused/adversarial tests and repository security/policy/Stage/Enterprise gates affected by the change. CI/release evidence must belong to one exact candidate SHA.

Never weaken a valid test, threshold, expected result, security control or policy merely to make CI green.

## Architecture and change discipline

Before adding a new framework, authority, persistence layer, agent, service or abstraction, prove the failure mode or change cost it solves. Reuse/extend canonical components where safe. Material architecture/security/trust/provenance/replay/migration/recovery/scale decisions follow the bounded 2–4 alternative review from `docs/WORKING_PRINCIPLES.md`.

Provider/model/plugin changes do not inherit certification automatically. Persistent/cross-boundary artifacts require explicit identities/contracts, deterministic migration/replay behavior where applicable, and provenance.

## Reporting

Progress updates are informational only. Final stage reporting is allowed only at `CLOSED / ENGINEERING PASS` or a true `HARD BLOCKER`.

After closure use:
`STATUS → WYKONANO → FINAL STATE → WNIOSEK → NEXT`.

Do not manufacture human, independent, security, red-team or external review. When required independent evidence is absent, use `INDEPENDENT_REVIEW_REQUIRED`.
