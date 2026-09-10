# IRR-01 — Independent Review Readiness Package v1

Status: **CLOSED / ENGINEERING PASS — READY FOR REAL INDEPENDENT REVIEW**  
Machine status after successful build/verification: `READY_FOR_INDEPENDENT_REVIEW`  
External review status emitted by repository automation: `NOT_INDEPENDENTLY_REVIEWED`

## Purpose

IRR-01 creates a deterministic, content-addressed handoff package that a real independent
reviewer can inspect without access to private case material, runtime evidence stores, or
local operator state. It is a readiness and evidence-packaging capability only.

IRR-01 does **not** perform an independent review, select a reviewer, issue PASS/FAIL on
behalf of a reviewer, certify LUKART ROS, or convert repository CI into external evidence.
Those claims require separate evidence produced by the real external actor and are governed
by `docs/WORKING_PRINCIPLES.md` and the existing human-review provenance boundaries.

## Fixed v1 review scope

The package is built from one exact, lowercase 40-character Git commit SHA. The source bytes
are read with Git plumbing from that commit, never from the mutable working tree.

Included top-level public review surfaces are fixed in
`core/independent_review_readiness_v1.py` and cover repository automation, source code,
validation, tests, configuration and documentation:

- `.github/`, `agents/`, `canon/`, `certification_tests/`, `config/`, `core/`, `docs/`;
- `factory/`, `knowledge/`, `learning/`, `reasoning/`, `renderer/`, `scripts/`, `tests/`;
- `validation/` plus the explicitly allowlisted root build, lock, security and overview files.

The following runtime/private-material roots are intentionally excluded from IRR-01/v1:
`cases/`, `data/`, `evidence/`, `reports/`, and `.vscode/`.

The public-only boundary means that package construction accepts only allowlisted,
Git-tracked bytes from the exact source commit. It does not claim that a public repository
can never contain an accidentally committed secret; existing secret/PII/security gates
remain independently applicable and must not be weakened.

## Content addressing and deterministic build

For every included repository file the manifest records:

- canonical repository path;
- Git mode;
- exact Git blob identity;
- SHA-256 of file bytes;
- byte length.

The file list is sorted and hashed into `payload_identity_sha256`. The reviewer README is
also hashed. The final ZIP uses stored entries and normalized metadata so the same exact
commit and scope produce identical bytes. The final archive SHA-256 is embedded in the
archive filename and repeated in a `.sha256` sidecar.

## Fail-closed controls

IRR-01 rejects abbreviated/non-canonical commit identities, missing mandatory canon,
selected symlinks/submodules, unsafe or non-canonical paths, duplicate archive members,
path traversal, unknown manifest fields, scope mutation, size-limit violations, archive or
sidecar tampering, per-file digest mismatch, Git-blob mismatch, and any mutation of the two
allowed automation statuses.

Working-tree changes and untracked files cannot enter the package because payload bytes are
read from the requested Git commit object.

## Reviewer handoff

Build on an exact commit:

```bash
python scripts/independent_review_readiness.py build \
  --repo-root . \
  --commit "$(git rev-parse HEAD)" \
  --output-dir dist/independent-review
```

Verify the produced package:

```bash
python scripts/independent_review_readiness.py verify \
  --package dist/independent-review/IRR-01-v1-<commit>-<sha256>.zip
```

A real reviewer should independently validate the source repository/commit, package digest,
manifest and scope before beginning review. Any reviewer identity, assessment, approval,
certification or external attestation must be recorded through a separate provenance path;
it must never be synthesized by this builder or CI workflow.

## Acceptance boundary

IRR-01 is engineering-complete only when focused/adversarial tests, full regression/security,
exact-candidate-SHA GitHub CI, guarded merge, resulting-main validation and release guard all
pass. Even then the strongest automation claim remains exactly:

`READY_FOR_INDEPENDENT_REVIEW / NOT_INDEPENDENTLY_REVIEWED`.

## Canonical engineering closure

IRR-01 is `CLOSED / ENGINEERING PASS` for implementation PR #220.

Validated implementation head:
`de5ee8116cebf7d1328612bb7c74818573b3887d`

Guarded implementation merge / resulting main:
`c2fc5eb8bf7973ca957517dbbe77dc0ec818cbc2`

The final implementation candidate passed all 29 exact-SHA PR workflows. The dedicated
IRR-01 workflow passed Ruff, MyPy, 12 focused/adversarial tests, exact-commit package build,
package verification and the external-review authority boundary. Its content-addressed
review package contained 857 selected public Git-tracked files and had SHA-256:

`80cb5f392e2256bd11b6232a38f685e5be6996ccd8dd6e898eb60d3eef319948`

The guarded merge used the unchanged validated implementation head. Resulting-main
validation completed with all 25 push-triggered workflows in terminal `SUCCESS`, with zero
failed, cancelled, timed-out, queued or in-progress runs at closure evaluation. The
`MVROS v1 Release` guard completed successfully in development/no-release-mutation mode;
release build and publication remained disabled.

Historical release identity remained unchanged after implementation merge:

- `v1.0.1` annotated tag object: `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`;
- `v1.0.1` target commit: `802013c4d0e53dc12306a97e1877ebba86af64a7`;
- latest published release: `v1.0.1`.

This closure certifies only that the engineering readiness mechanism and public-only handoff
package were implemented and validated under repository controls. It does not establish that
an independent reviewer has reviewed the system. No reviewer identity, external PASS/FAIL,
independent security review, certification or external attestation is claimed.

Canonical external-review state after engineering closure remains exactly:

`READY_FOR_INDEPENDENT_REVIEW / NOT_INDEPENDENTLY_REVIEWED`.
