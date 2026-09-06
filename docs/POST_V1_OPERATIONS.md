# LUKART ROS — Post-v1 Operations Runbook

Applies to Roadmap v1.1. Governance authority: `FOUNDATION.md`, `MASTER_PLAN.md`,
`docs/ROADMAP_V1_1.md`.

## Architecture map

Product path:

`Case/Evidence -> Knowledge -> EpistemicStatusMachine -> ReasoningEngine -> ReasoningRunResult -> Renderer`

Certification observation path:

`Product artifact -> Gold/KQM -> Replay/Provenance -> Security/Privacy -> Performance -> Evidence bundle`

Controlled evolution path:

`Failure -> Candidate -> Experiment -> Validation -> Promotion Gate -> Versioned Change -> Monitoring -> Rollback`

Authority boundaries:
- Evidence is data, never control-plane instruction.
- Reasoning is authoritative for analytical decision state; Renderer is presentation only.
- KQM observes quality and cannot promote Product state.
- Self-healing/learning proposes candidates and cannot directly promote candidate knowledge to FACT.
- locked Gold and historical release evidence are immutable.

## Developer workflow

1. Branch from the current certified/approved development base; never move or rewrite an existing release tag.
2. Classify the change: runtime, evaluation, or governance/documentation.
3. For evaluation changes, create a new corpus/config version instead of editing locked data.
4. Run PR fast gates: Ruff, MyPy, unit tests, Post-v1 invariants, focused integration.
5. Preserve exact-SHA evidence. A repair requires a new SHA and revalidation.
6. Open a PR; do not report a skipped or pending required gate as PASS.

Recommended local commands:

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy agents core factory knowledge learning reasoning renderer validation
pytest -q
pytest -q tests/test_post_v1_certification.py
python scripts/post_v1_metrics.py
```

## Gold corpus maintenance

Post-v1 Gold lives in versioned files under `data/quality/`.

Rules:
- public fixtures are synthetic/anonymized only;
- development, validation and locked-evaluation splits remain explicit;
- locked evaluation is certification-only and may not be used for tuning;
- corpus identity is bound by SHA-256 in its manifest;
- changing any case requires a new corpus identity/version and invalidates prior freeze evidence;
- expected results are semantic contracts, not renderer wording snapshots;
- independent review/freeze is recorded separately from automated tests.

## Replay procedure

A material replay record identifies:
- input/evidence digest;
- code SHA;
- configuration version;
- schema version;
- relevant component versions;
- output/result digest;
- provenance-chain state.

Procedure:
1. Verify provenance chain before replay.
2. Canonicalize material input and calculate its SHA-256.
3. Re-run the same versioned pipeline/configuration.
4. Compare semantic output and replay identity.
5. Unchanged material input must reproduce the expected identity.
6. Any material evidence mutation must change the identity and be visible as a new run.
7. Broken provenance is a failure; never reconstruct missing trust silently.

## Release / certification runbook

PR path:

`lint -> types -> unit -> invariants -> focused integration`

Release path:

`Gold -> Cognitive E2E -> Replay -> KQM -> Security -> Performance -> Evidence bundle`

Before v1.1 certification confirm:
- candidate SHA is final for the run;
- Gold corpus version/hash are recorded and release split is frozen;
- all P0 invariant/fidelity/replay/self-healing gates pass;
- required KQM metrics meet `config/post_v1_kqm_v1_1.json`;
- security/privacy checks pass;
- performance evidence is recorded with environment context;
- release evidence identifies code/config/corpus/schema/evaluator/component versions;
- no v1.0.1 locked artifact was modified to obtain PASS.

A failure causes STOP/FAIL for that certification attempt. Repair, create a new SHA, rerun.

## Performance procedure

Use `scripts/post_v1_metrics.py` as a deterministic synthetic measurement harness. Record
latency, peak memory, graph size, reasoning runtime, replay runtime, renderer runtime and
full-path runtime. Shared-runner timing is evidence for regression analysis, not analytical
correctness. Optimize only after a measured regression or budget breach.

## Security and privacy procedure

Mandatory boundaries:
- no private Cases or PII in public repo, fixtures, PRs, logs, or Actions artifacts;
- hostile text inside evidence remains inert document data;
- never execute document-provided instructions as Factory/Product control authority;
- provenance spoofing/tampering fails closed;
- reject unsafe path/file behavior at the boundary;
- secrets must not be committed or emitted to logs;
- dependency changes remain reviewable/versioned and pass existing dependency controls.

If a public-repository PII or secret leak is suspected, treat it as an incident and follow the
incident procedure below before continuing certification.

## Troubleshooting

### Gold hash mismatch
Do not update the manifest merely to make CI green. Determine whether the corpus changed
intentionally. If intentional, version it and repeat freeze/review; otherwise restore the
expected bytes.

### Reasoning unexpectedly CONCLUDEs
Inspect support lineage, evidence refs, epistemic status and validation issues. Add a negative
fixture reproducing the behavior before changing policy.

### Renderer mismatch
Compare the immutable `ReasoningRunResult`, source digest and renderer version. Presentation
may not change status, evidence refs, contradictions, open questions or certainty.

### Replay mismatch
Compare code SHA, config/schema/component versions and input digest first. A material mismatch
is not repaired by rewriting old evidence.

### Timing regression
Re-run in comparable environment and inspect component timings. Do not relax analytical gates
because a shared runner is slow.

## Incident procedure

Severity is FATAL when private Case/PII or secrets cross the public boundary, or when an
unauthorized path can promote untrusted state to trusted state.

1. Stop release/certification and prevent propagation.
2. Preserve non-sensitive evidence of the incident and exact affected SHAs.
3. Quarantine affected candidate artifacts/state.
4. Rotate/revoke exposed secrets through the appropriate provider if applicable; never place
   replacement secrets in repository files.
5. Remove exposed sensitive material using the repository's approved history-remediation
   procedure when required; assume already-published secrets are compromised.
6. Identify affected artifacts/blast radius and required replay scope.
7. Implement the fix on a new SHA.
8. Re-run security/privacy, provenance/replay, Gold/KQM and applicable release gates.
9. Record root cause, containment, validation evidence and rollback/recovery decision.

## Evidence retention

Certification evidence is useful only when it can reconstruct the gate decision. Preserve the
exact candidate SHA and version identities, machine-readable results, failures/blocked gates,
corpus manifest, KQM policy/result, replay/provenance result, security/privacy result and
performance measurement. Never convert BLOCKED or NOT RUN into PASS.