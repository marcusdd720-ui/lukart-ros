# SSC-02 — Supply Chain Continuity v2

Status: CLOSED / ENGINEERING PASS

## Problem

The repository already had software-supply-chain controls for resolved dependencies,
CycloneDX SBOM generation, SLSA-style provenance and full-SHA GitHub Actions pinning. Those
controls describe and authenticate a build, but they are not sufficient to recover it after
a package registry, dependency resolver, build frontend or workflow implementation changes
or disappears.

SSC-02 therefore addresses a different long-horizon failure mode: preserving enough exact,
verifiable physical build material and identity information to validate and rebuild the
software without trusting the original registry or the current LUKART runtime.

## Decision

SSC-02 adds one verifier-first continuity bundle around the existing supply-chain authority.
It does not replace `pylock.toml`, `uv.lock`, the existing Enterprise supply-chain module,
or Git provenance.

The continuity bundle contains:

- exact `pyproject.toml`, standard PEP 751 `pylock.toml`, `uv.lock` and
  `lukart_build_backend.py` identity inputs;
- a physical wheelhouse for the exact current dependency/build environment;
- an exact Git source archive whose PAX header is bound to the full source commit SHA;
- a standalone copy of the SSC-02 verifier that runs using only the Python standard library;
- a canonical JSON manifest containing exact source/runtime/platform declarations plus an
  exhaustive file inventory with SHA-256 and byte-size bindings;
- exact package name/version identities for physical wheels.

The bundle digest is content-addressed over canonical JSON excluding only its own digest
field. A valid manifest does not make a damaged or substituted payload valid: every listed
artifact is independently re-read and verified.

## PEP 751 / dependency semantics

SSC-02 preserves lock semantics instead of flattening them into a false single-version
model.

- Registry-backed packages require an exact version.
- PEP 751 environment markers are preserved in exported constraints.
- Multiple marker-separated versions of one normalized package name are permitted when the
  lock declares them.
- The repository project itself may appear as `directory.path = "."` without a package
  version because its exact source tree is separately escrowed and its project version is
  bound by `pyproject.toml` plus the generated project wheel.
- Any other direct-source dependency (`directory`, VCS or archive source) fails closed until
  a separately implemented continuity adapter physically escrows and verifies that source.

This avoids replacing the standardized lock with a second dependency authority.

## Offline recovery contract

The validated recovery path is registry-independent after bundle creation:

1. verify the continuity manifest and every physical artifact using the standalone stdlib
   verifier;
2. create an empty recovery environment;
3. install the project and dependencies with `PIP_NO_INDEX=1` and local `--find-links` only;
4. import the recovered product package;
5. extract the exact bound Git source archive;
6. install the pinned build-system tool from the local wheelhouse;
7. rebuild the project wheel from the extracted exact source using no index/network-backed
   dependency resolution;
8. verify the rebuilt package can be installed from the same local material.

The CI tamper drill mutates a physical wheel and requires the standalone verifier to reject
the bundle.

## Trust and authority boundary

- SSC-02 is supply-chain recovery/verification evidence only.
- It creates no Product truth, Canonical Case Ledger write, Gold, epistemic promotion,
  authorization or release authority.
- The standalone verifier intentionally does not depend on current LUKART packages, `uv`,
  PyPI metadata APIs or a current package resolver.
- Unknown schema, unknown inventory fields, missing/extra files, path traversal, symlinks,
  digest/size mismatch, package-identity mismatch, source-SHA mismatch and undeclared direct
  sources fail closed.
- Wheel identity is read from exactly one top-level `<distribution>.dist-info/METADATA`;
  nested vendored `dist-info` metadata is not a competing wheel identity.
- Runtime/platform fields document the environment in which the physical wheelhouse was
  materialized. They do not claim universal cross-platform executability.

## Long-horizon storage boundary

SSC-02 proves a deterministic continuity format and a working offline recovery drill. It
does **not** claim that GitHub Actions artifacts provide ten-year archival durability, and
it does not claim that an external immutable escrow currently exists.

A production long-horizon escrow should store the content-addressed bundle in at least two
independent durable/immutable locations and periodically execute a restore drill. Selecting,
provisioning and operating those external storage providers is separate infrastructure and
business continuity work; it is not fabricated by repository CI.

## Exact closure evidence

- implementation PR: `#174`;
- implementation base before merge: `main @ 0b1751a720438d517bfbec5c1ba0181b8633eb98`;
- validated exact implementation PR head:
  `90fe300d8d81876e9d690410eef2c1dc564820e8`;
- exact-head PR CI: `12/12 SUCCESS`, including CI Foundation, Stage Gate, Enterprise Hardcore
  Gate, Enterprise CodeQL and the dedicated SSC-02 Supply Chain Continuity workflow;
- SSC-02 focused/adversarial contract suite: `12/12 PASS` on the validated exact head;
- dedicated integration gate proved marker-aware PEP 751 export, physical wheelhouse
  materialization, exact-source archive creation, standalone bundle verification, offline
  install/import, offline exact-source rebuild and fail-closed live tamper detection;
- guarded merge used the unchanged exact head with
  `expected_head_sha=90fe300d8d81876e9d690410eef2c1dc564820e8`;
- implementation merge: `main @ d6efdfaad63427b5ddb76af8da58b33baae0386b`;
- implementation merge post-merge validation: `10/10 SUCCESS`, with zero failed, cancelled,
  timed-out, queued or in-progress runs at closure evaluation;
- historical `v1.0.1` annotated tag object remained
  `9f7c0b28f766c8921e63b1d517fefcc96aa991d4`;
- historical `v1.0.1` target commit remained
  `802013c4d0e53dc12306a97e1877ebba86af64a7`;
- the release list still contains the historical `v1.0.1` / `v1.0.0` releases and no new
  SSC-02 release was published;
- no independent external/security/SLSA certification or ten-year external-storage
  durability certification is claimed.

## Closed controls

- physical dependency/build artifacts are bound to exact lock/build/project identities;
- exact source bytes are bound to a full Git SHA and included in the continuity material;
- a historical bundle can be verified without importing LUKART or using the original
  dependency resolver;
- PEP 751 marker-separated variants are preserved rather than collapsed;
- unescrowed direct-source dependencies fail closed;
- inventory equality rejects both missing and undeclared extra artifacts;
- path traversal and symlink substitution fail closed;
- nested vendored package metadata cannot substitute the top-level wheel identity;
- offline install and exact-source rebuild are exercised under no-index constraints;
- tamper detection is exercised against real physical bundle material;
- GitHub Actions artifact retention is not treated as long-horizon escrow;
- no second dependency authority, Product authority, release authority or certification
  authority is introduced.

Next approved stage: `FIV-02`.
