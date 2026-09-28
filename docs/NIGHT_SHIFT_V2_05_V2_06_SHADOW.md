# Night Shift V2-05 / V2-06 / Shadow

Status: VALIDATED SHADOW CANDIDATE
Validated: 2026-09-28

This stage adds:
- live Git-ref observer with non-interactive, fail-closed lookup;
- repository-owned read-only Shadow CLI and fresh portfolio snapshots;
- durable runtime capability matrix and evidence-driven selection;
- restart pilot over the provider-neutral DurableWorkflowEngine;
- strict configuration typing for runtime/project/executor profiles;
- static project registry separate from live portfolio state;
- provider-neutral executor capability registry;
- executor-locality and per-executor parallel-capacity controls;
- deterministic multi-project dispatch;
- read-only Shadow Night Shift planning;
- morning report and autonomy friction metrics;
- SQLite connection-lifecycle hardening for restart/cleanup reliability.

## Live portfolio evidence

Verified live inputs:
- LUKART ROS main: `3362bb35c6b5a54fcf51c58077d3bc4aeecbc0be`;
- PR #313 candidate: `a684ea0380a061c5062557db7b03704797396c7a`;
- PR #313 candidate base: `2f81977f64ad7ec550b5dc7a43540a144ac7bc70`;
- LATAM Career OS main: `b0680b77c9aa527d50da0a62b2b8c8c12160f9a6`;
- synthetic-test-data main: `cd157d48f580c9d613cee99ea0ac8acf32162faa`.

Observed shadow result:
- repository-owned live command: `python scripts/night_shift_shadow.py`;
- live refs are resolved with `GIT_TERMINAL_PROMPT=0` and a bounded timeout;
- LUKART PR #313 -> BLOCKED by stale candidate base;
- LATAM I11 -> PLANNED via `codex_adapter`;
- synthetic v0.7.1 -> PLANNED concurrently via `codex_adapter`;
- mutating actions executed -> 0;
- plan digest -> `04a66ddf21003a96063d2170090c1c1e3d627dd3f6b8ffd7a4ac12f0e14a2d4f`.

## Runtime pilot evidence

Requirements:
- crash resume required;
- idempotent steps required;
- deterministic replay not yet required for this pilot;
- durable timers not yet required;
- distributed workers not yet required.

Observed result:
- `LocalJournalWorkflowEngine` restart pilot -> PASS;
- state before restart -> RUNNING;
- state after restart -> RUNNING;
- final state -> VALIDATING;
- immediate temporary database cleanup -> PASS;
- selected runtime -> `local_journal`.

DBOS and Temporal remain DOCUMENTED-only candidates until a repository-owned adapter and validated observation exist. They cannot win runtime selection on documentation alone.

## Validation

Latest local validation:
- Night Shift test suite -> PASS;
- Ruff -> PASS;
- Mypy Linux target -> PASS across 845 source files;
- PII scan -> PASS;
- secret scan -> PASS;
- repository audit -> PASS.

Promotion to controlled unattended mutation remains out of scope until final exact-SHA CI, independent review and signed-candidate landing complete.

Planned != Implemented != Validated != Certified.
Evidence Before Conclusion.
