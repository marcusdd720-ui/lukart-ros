# OPR-01 — Operational Readiness Contract v1

Status: implementation contract for the Post-Hardcore `OPR-01` stage.
Canonical operational runbook remains `docs/POST_V1_OPERATIONS.md`; this document records the
versioned engineering contract and does not create a second operational authority.

## Problem and evidence baseline

Before OPR-01, LUKART ROS already had exact-SHA CI, FIV-02 bounded invariant probes, Case Replay
v2, DR-02 recovery conformance, incident basics, privacy/security gates and an operational
runbook. The missing layer was an executable readiness decision tying those controls to explicit
SLIs/SLOs, error budgets, telemetry semantics, incident coverage and deterministic evidence.

The design therefore aggregates and verifies existing controls instead of cloning replay,
recovery, authorization, Product state or incident authority.

## Operational readiness model

`Exact code SHA -> FIV-02 / replay / recovery / authorization -> deterministic observations`
`-> SLI/SLO + error-budget evaluation -> bounded telemetry -> readiness report`

`OperationalReadinessReportV1` is a verification projection only. It cannot write the Canonical
Case Ledger, change epistemic state, promote trust, mutate Gold, publish a release or claim
independent review.

## SLI / SLO and error budgets

The fixed v1 registry contains seven deterministic SLIs:

1. critical invariant pass ratio — 6/6 required;
2. replay/recovery drill pass ratio — 2/2 required;
3. degraded-mode containment ratio — 4/4 required;
4. incident-detection coverage ratio — 6/6 required;
5. runbook-contract coverage ratio — 8/8 required;
6. telemetry-contract validity ratio — 7/7 required;
7. security/trust-boundary pass ratio — 2/2 required.

All seven are trust-critical exact-SHA drill SLIs, so v1 has a zero deterministic failure budget.
One failed sample exhausts the budget and yields `FAIL`; the implementation never rounds or
averages a failure into PASS. Wall-clock latency/RTO/RPO observations remain useful telemetry but
are not deterministic correctness authority and are not silently converted into these SLIs.

## Observability and telemetry contract

Telemetry is derived observability, never Product truth. `TelemetryEventV1` has a closed bounded
surface: event, component, outcome, exact code SHA, evidence digest and schema. There is no free
payload/labels field, raw Case text, evidence body, user identity, secret or arbitrary metadata.
Unknown event/schema/outcome or malformed SHA/digest fails closed. OPR-01 emits exactly seven
deterministic events per readiness run; the report hard-bounds the count to prevent cardinality
expansion.

## Incident detection and response

The v1 incident registry maps six known signals deterministically:

- private/secret boundary breach -> `FATAL` -> Incident procedure;
- unauthorized trust promotion -> `FATAL` -> Security and privacy procedure;
- replay identity mismatch -> `HIGH` -> Replay procedure;
- recovery identity mismatch -> `HIGH` -> recovery/replay drill procedure;
- exhausted operational error budget -> `HIGH` -> SLI/SLO procedure;
- telemetry contract violation -> `MEDIUM` -> observability/telemetry procedure.

Unknown or ambiguous signals do not receive an invented response and fail closed. Detection does
not replace incident ownership or provider-side secret revocation procedures.

## Recovery, replay and degraded-mode drills

OPR-01 reuses FIV-02 rather than implementing another recovery/replay engine. PASS requires the
existing exact-SHA FIV-02 registry to succeed, including replay projection equivalence and
recovery atomicity. Degraded-mode containment is evidenced by four existing adversarial probes:
stale exact-head refusal, migration-path determinism, authorization isolation and injected
recovery failure with zero partial history plus exact retry.

DR-02 and Case Replay v2 focused suites remain regression gates in the dedicated OPR-01 workflow.

## Runbook validation

The executable readiness drill requires exactly one occurrence of eight canonical runbook
headings spanning replay, security/privacy, incident response, evidence retention, SLI/SLO and
error budgets, observability/telemetry, recovery/degraded drills and runbook validation. Missing
or duplicated required controls consume the zero error budget and produce `FAIL`.

## Determinism and provenance

The readiness report binds:

- exact 40/64-hex candidate code SHA;
- content-addressed OPR-01 policy identity;
- FIV-02 report identity;
- exact runbook text digest;
- seven content-addressed SLI results;
- seven payload-free telemetry records;
- six incident-rule identities;
- final outcome and `operational-verification-only` authority marker.

No timestamp, random identifier or runner timing contributes to report identity. Repeating the
same exact-SHA drill with the same runbook must reproduce the same report digest. A stale or
malformed SHA fails before the operational drill is accepted.

## Security and trust boundaries

- Canonical Case Ledger remains the only writable Product history SSOT.
- FIV-02, replay, recovery and authorization production contracts are reused, not duplicated.
- telemetry is non-authoritative and payload-free;
- no real/private Case material is needed by the drill;
- synthetic writable state is temporary and isolated;
- unknown schemas/signals/identities fail closed;
- no gate, SLO or error budget may be weakened to obtain PASS;
- engineering PASS does not imply independent external, regulatory, SRE or security certification.

## Validation contract

Focused/adversarial OPR-01 tests cover policy immutability, budget exhaustion, unknown incident
signals, telemetry schema boundaries, malformed/stale SHA, deterministic replay of the readiness
report, missing runbook control and mixed-SHA telemetry. Dedicated CI also reruns FIV-02,
DR-02 and Case Replay v2 regression suites plus repository PII/secret gates.

Closure still requires the repository-wide full regression/security/policy checks, terminal
exact-head CI, guarded merge, resulting-main validation and immutable-baseline/release checks.
