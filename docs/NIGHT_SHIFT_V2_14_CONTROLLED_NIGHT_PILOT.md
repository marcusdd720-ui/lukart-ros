# Night Shift V2-14 — Controlled Night Pilot

Status: IMPLEMENTATION CANDIDATE
Recorded: 2026-09-29

## Objective

V2-14 composes the previously validated Night Shift controls into one bounded,
single-dispatch night pilot.

Canonical sequence:

`fresh portfolio -> deterministic dispatch -> exact identity binding -> existing
authority/evidence gates -> isolated controlled mutation -> signed receipt -> verified
rollback -> morning closure evidence`

## Pilot boundary

The pilot is intentionally narrow:

- exactly one planned dispatch;
- R0 or R1 only;
- mutating project required;
- exact current project main SHA required;
- single-task, single-repository AutonomyEnvelope required;
- envelope risk must match the selected live task exactly;
- exact LiveStateSnapshot and TaskCapsule binding required;
- existing verification quorum required;
- cryptographic automation identity required;
- Shadow Twin / Autonomy Debt clearance required;
- current V2-13 failure-injection report required;
- existing controlled-canary scope limits remain authoritative;
- verified rollback is mandatory;
- external publication is forbidden.

The pilot does not create a new authority path. It composes existing controls and fails
closed when their identities disagree.

## Fail-closed conditions

Execution is rejected when:

- the portfolio snapshot is stale;
- zero or more than one dispatch is planned;
- the selected project is not uniquely represented in live state;
- the project is not mutating;
- the risk class is outside R0/R1;
- repository, task, state or project identities differ;
- the execution state is not bound to current project main;
- the TaskCapsule is not bound to the current state snapshot;
- the canary executes against a different input SHA;
- rollback is not verified;
- the canary reports external publication.

All V2-07 through V2-13 gates remain in force inside the controlled canary.

## Output

A successful pilot emits deterministic evidence binding:

- portfolio digest;
- dispatch plan digest;
- controlled-pilot policy digest;
- execution receipt digest;
- exact input/output SHA;
- rollback status;
- publication status;
- morning report pilot evidence.

Because the controlled mutation is obligatorily rolled back, a successful pilot does
not claim durable task closure. The dispatched task, together with any other ready
task, is surfaced as READY_FOR_HUMAN in the morning report. Closure requires a separate
durable execution path with independently verified persistent effect. The pilot does
not automatically promote broader autonomy.

## Authority boundary

V2-14 does not:

- enable unattended production publication;
- increase AutonomyEnvelope scope;
- increase allowed risk class;
- permit multi-dispatch mutation;
- bypass human-only tasks;
- bypass verification, cryptographic, shadow or failure-injection gates;
- treat successful local pilot evidence as production certification.

Planned != Implemented != Validated != Certified.
Evidence Before Conclusion.
