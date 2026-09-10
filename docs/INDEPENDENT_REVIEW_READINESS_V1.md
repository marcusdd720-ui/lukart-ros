# IRR-01 — Independent Review Readiness Package v1

Status: **ENGINEERING READINESS SCOPE — NOT AN INDEPENDENT REVIEW**  
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
