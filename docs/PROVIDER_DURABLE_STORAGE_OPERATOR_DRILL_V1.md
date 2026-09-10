# LRD-01H — Provider Durable Storage Operator Drill v1

Status: `NON-AUTHORITATIVE OPERATIONAL RUNBOOK / REAL PROVIDER EVIDENCE REQUIRED`

Authority: this runbook is subordinate to `docs/WORKING_PRINCIPLES.md`, `MASTER_PLAN.md`,
`docs/POST_HARDCORE_ROADMAP.md` and `docs/PROVIDER_DURABLE_STORAGE_WORM_V1.md`. It does not
change the LRD-01H Definition of Done, approve AWS for real-case storage, or create Product, CCL,
Gold, trust, release, certification or independent-review authority.

## Purpose

The original LRD-01H implementation can verify live S3 Object Lock state in memory, but closure
requires preserved, re-verifiable provider receipts and a target-only restore after real source
unavailability. The operator surface is therefore split into two phases so the final phase does not
instantiate a source client.

Only the fixed synthetic case identity
`CASE-LRD-01H-SYNTHETIC-PROVIDER-DRILL` is accepted. Real case bytes, private evidence and case
identifiers are structurally outside this runner.

## External prerequisites

Before running, provision two independently configured S3 Object Lock locations outside this
repository. Each tested object version must receive active `COMPLIANCE` retention through the
provider configuration. Source and target must use distinct AWS regions, storage principals and
credential-domain IDs. The storage credentials must not have delete, retention-mutation or
`BypassGovernanceRetention` authority. Separate read-only IAM policy-simulation credentials may be
used for the bounded least-privilege check.

The repository intentionally does not depend on boto3. Install boto3 only in the external operator
environment and configure named AWS profiles outside the repository. Do not commit AWS credentials,
configuration files, provider receipts or source-unavailability evidence.

## Secret-free operator config

Create a JSON config outside the repository using schema
`lukart.provider-durable-operator-config.v1`. Both `source` and `target` contain exactly:

- `aws_profile` — local named profile used for S3 and STS;
- `auditor_aws_profile` — local named profile used for IAM policy simulation;
- `region`;
- `bucket`;
- `key_prefix`;
- `expected_bucket_owner`;
- `credential_domain_id`;
- `policy_source_arn`.

Unknown fields are rejected. Credential values, access keys, tokens and secrets are not valid config
fields. The source and target storage profiles, regions and credential-domain IDs must differ.

## Phase 1 — prepare

Run from an exact Git checkout:

```text
python scripts/provider_durable_storage_drill.py prepare \
  --config <external-config.json> \
  --code-sha <exact-40-character-sha> \
  --output <external-capture.json>
```

`prepare` verifies the local Git SHA, builds only deterministic synthetic LRD-01H artifacts,
publishes them to source, replicates them through the existing 01G path, rereads exact S3
`VersionId` objects, verifies Object Lock/retention/legal-hold/STS/IAM evidence for both locations,
and writes a content-addressed secret-free capture outside the repository.

Closure-grade capture additionally rejects two ambiguities that the original in-memory verifier did
not make terminal: IAM policy evidence must bind the same storage principal observed through STS,
and every exact-version Object Lock observation must contain all five provider request identifiers.
The capture authority string is fixed to
`captured-provider-evidence-not-closure-authority`.

## Source-unavailability boundary

After `prepare`, make the source genuinely unavailable using an externally controlled mechanism
appropriate to the approved provider setup. Do not try to prove source loss by deleting a protected
COMPLIANCE version. Preserve separate evidence of the unavailability event in a nonempty file
outside the repository.

The runner hashes that file but does not interpret or certify its semantics. A matching digest proves
only which external evidence bytes were bound into the drill record; it does not independently prove
physical, organizational or provider failure-domain separation.

## Phase 2 — finalize with target only

After source unavailability:

```text
python scripts/provider_durable_storage_drill.py finalize \
  --config <external-config.json> \
  --capture <external-capture.json> \
  --source-unavailability-evidence <external-evidence-file> \
  --output <external-drill.json>
```

The finalize path intentionally does not instantiate source AWS clients. It recreates only the target
backend from the exact preserved target `VersionId` inventory, re-verifies target Object Lock,
retention, principal and IAM evidence, performs the existing 01G target restore verification and
binds the SHA-256 of the external source-unavailability evidence.

The resulting status is structurally fixed to `CAPTURED_NOT_CLOSURE_AUTHORITY`. The tool cannot emit
`CLOSED`, `ENGINEERING PASS`, a ten-year durability claim or external certification.

## Offline verification

Either preserved capture or final drill JSON can be checked without AWS access:

```text
python scripts/provider_durable_storage_drill.py verify --input <external-evidence.json>
```

Offline verification rejects unknown fields, altered digests, profile/location/version substitution,
IAM-principal substitution, incomplete provider request IDs, changed pair identities, non-PASS target
restore and forged closure status. It proves internal content-addressed consistency only; serialized
provider responses are not self-authenticating AWS attestations.

## Closure boundary

LRD-01H remains `IMPLEMENTATION CANDIDATE / REAL PROVIDER EVIDENCE REQUIRED` until the canonical
Definition of Done in `docs/PROVIDER_DURABLE_STORAGE_WORM_V1.md` is satisfied with actual configured
provider resources and live evidence. Public CI uses synthetic/fake provider responses solely to
validate the mechanism and may never convert those fixtures into external provider PASS.
