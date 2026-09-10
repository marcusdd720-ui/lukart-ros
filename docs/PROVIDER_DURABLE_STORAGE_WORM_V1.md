# LRD-01H — Provider-Verified Durable Storage Adapter & WORM Evidence v1

Status: `IMPLEMENTATION CANDIDATE / REAL PROVIDER EVIDENCE REQUIRED`
Parent program: `continuous LRD-01`
Depends on: `LRD-01G CLOSED / ENGINEERING PASS`
Measured base: `main @ ab166733cc28c224dbf5064c2676253db1120a10`
First provider adapter: `AWS S3 Object Lock`
Writable case-history SSOT: Canonical Case Ledger only
Historical release baseline: `v1.0.1` unchanged and outside this stage's release authority

## Execution deferral — owner decision

Real AWS resource provisioning and the live provider-evidence drill are deferred until **March 2027**
by explicit owner/business sequencing decision. Before that execution window, no AWS account,
bucket, Object Lock policy, retention policy, IAM principal or credential domain is to be provisioned
for LRD-01H unless a new explicit owner/business decision supersedes this deferral.

This scheduling decision does not weaken or satisfy any LRD-01H Definition-of-Done requirement.
External provider evidence remains `INCOMPLETE`, LRD-01H remains an implementation candidate, and no
mock, fixture, repository CI result or planning text may be promoted to real provider evidence.

The parent `continuous LRD-01` program may continue with provider-neutral/offline engineering while
this external-evidence dependency is parked. Subsequent work must not inherit, imply or claim an
LRD-01H provider PASS. The planned order before returning to the live provider drill is:

1. post-01H gap audit;
2. offline long-range survivability;
3. crypto migration/renewal;
4. cross-environment replay;
5. expanded critical-invariant verification;
6. further provider-neutral durability/recovery;
7. live AWS LRD-01H closure work in the March 2027 execution window.

## 1. Problem

LRD-01G proves backend-neutral two-location replication and restore conformance, while deliberately
leaving provider-side WORM, delete protection, retention, geographic separation and credential
isolation unverified. Repository CI cannot convert self-declared cloud metadata into external
durability evidence.

LRD-01H adds the first provider-specific adapter below the existing
`ArtifactEscrowBackendV1` boundary. The adapter preserves LRD-01C SHA-256/size artifact identity and
adds exact S3 object-version provenance plus read-only provider verification. It does not create a
new storage authority, Product truth store, CCL writer, Gold authority, trust root, release gate or
archival certification.

## 2. Provider semantics used by the contract

The design follows current AWS S3 Object Lock semantics:

- S3 Object Lock is version-aware WORM protection and requires versioning;
- `COMPLIANCE` retention protects an object version from permanent deletion during the active
  retention period, including against the account root user;
- `GOVERNANCE` is intentionally weaker because principals with
  `s3:BypassGovernanceRetention` can bypass it;
- legal hold is an independent mechanism and is recorded independently from time-based retention;
- provider APIs can independently read bucket Object Lock configuration, exact-version retention
  and exact-version legal hold;
- exact object-version verification uses `VersionId`; ETag is never treated as SHA-256.

Authoritative AWS references used for this design:

- `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html`
- `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html`
- `https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObjectRetention.html`
- `https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html`

## 3. Alternatives and decision

### A. Add boto3 directly to Product runtime

Rejected. The Product does not need AWS SDK authority. Pulling a provider SDK into base runtime
would increase dependency and supply-chain surface and make the first provider adapter less
replaceable.

### B. Shell out to AWS CLI as the canonical adapter

Rejected. CLI availability/version/environment would become implicit runtime identity and would
make byte-stream and exact-VersionId semantics harder to test deterministically.

### C. Narrow typed provider protocols with injected clients — selected

`core.provider_durable_storage_v1` defines minimal S3, STS and optional IAM policy-simulator
protocols. Real boto3 clients satisfy the protocols structurally, but boto3 is not a base runtime
dependency. Tests use deterministic fakes to validate decision logic only. Fake/test responses are
never external provider evidence.

## 4. AWS storage profile

`AwsS3ObjectLockProfileV1` is secret-free and content-addressed. It binds:

- region;
- bucket;
- canonical key prefix;
- expected bucket owner;
- credential-domain ID;
- optional IAM `PolicySourceArn` for read-only policy simulation.

The profile produces the existing DR-02 `StorageProfileV1`; no competing profile authority exists.
Credentials, tokens and private material are structurally absent from the profile and remain outside
the repository.

## 5. Adapter under ArtifactEscrowBackendV1

`AwsS3ObjectLockEscrowBackendV1` implements the existing two-method byte-store contract:

- `publish(data, limits) -> EscrowBlobIdentityV1`;
- `read(identity, limits) -> bytes`.

Publication uses the deterministic content-addressed key
`<prefix>/sha256/<first-two>/<sha256>` and requires S3 to return an exact `VersionId`. The adapter
binds that version to the unchanged LRD-01C SHA-256/size identity and immediately rereads the exact
version. Every later read supplies the exact `VersionId` and `ExpectedBucketOwner` and recomputes
SHA-256/size.

The adapter intentionally exposes no delete API, retention mutation API, legal-hold mutation API or
bucket-policy/Object-Lock configuration API.

## 6. Provider object-lock evidence

`verify_object_lock_version_v1()` performs read-only provider calls and binds evidence to one exact
S3 version. It verifies:

1. STS caller account and principal ARN;
2. provider-observed bucket region;
3. bucket Object Lock configuration;
4. exact-version retention mode and retain-until timestamp;
5. exact-version legal-hold state;
6. exact provider request identifiers as provenance metadata.

Provider state is `VERIFIED` only when:

- expected owner/account matches;
- provider-observed region matches the profile;
- Object Lock is enabled;
- retention mode is `COMPLIANCE`;
- retain-until exists and is strictly later than the observation timestamp.

`GOVERNANCE`, missing retention, expired retention, wrong account/region, disabled Object Lock,
provider API failure or version substitution never become WORM/delete-protection `VERIFIED`.
Legal hold is recorded independently and is not required to replace a valid active COMPLIANCE
retention period.

## 7. Credential least-privilege evidence

Actual credential scope is not inferred from an ARN or from successful API calls.
`verify_credential_scope_v1()` optionally uses a separate read-only IAM policy-simulator client to
check the storage principal. The storage principal itself does not need permission to inspect IAM.

Required storage capabilities are limited to:

- `s3:GetBucketLocation`;
- `s3:GetBucketObjectLockConfiguration`;
- `s3:GetObjectLegalHold`;
- `s3:GetObjectRetention`;
- `s3:GetObjectVersion`;
- `s3:PutObject`.

The following capabilities must evaluate denied for a `VERIFIED` least-privilege result:

- `s3:BypassGovernanceRetention`;
- `s3:DeleteObject`;
- `s3:DeleteObjectVersion`;
- `s3:PutObjectLegalHold`;
- `s3:PutObjectRetention`.

If policy simulation is unavailable, credential scope remains `UNVERIFIED`; it is never promoted
from self-declaration. AWS documents that policy simulation does not execute the simulated API
operations, but simulator results can differ from the live environment. Therefore simulation is one
bounded evidence surface, not an independent security certification.

## 8. Whole-location and two-location evidence

`verify_s3_location_v1()` binds the exact 01G generic location, DR-02 storage profile, AWS profile,
escrow manifest, exact S3 version inventory, provider Object Lock evidence and credential-scope
evidence. It rereads every escrow blob before provider promotion.

`build_provider_pair_report_v1()` requires two independently provider-verified locations and checks:

- distinct provider-observed regions;
- distinct provider principal ARNs;
- distinct declared credential-domain IDs;
- exact same escrow manifest identity across both locations.

A different AWS region is evidence of provider region separation only. It is not a claim of legal,
organizational or physical custody independence beyond what AWS exposes.

## 9. Replication and source-loss restore

LRD-01H deliberately reuses 01G:

- `build_multi_location_plan_v1()`;
- `replicate_escrow_manifest_v1()`;
- `verify_location_restore_v1()`.

The S3 adapter therefore participates in the existing verified-read -> publish -> identity equality
-> verified-reread path. A source-loss drill must prove complete target restore while the source is
unavailable; it must not try to defeat COMPLIANCE retention by deleting a protected source version.
Repository adversarial tests model source unavailability and prove target-only recovery semantics.
A real provider drill needs independently configured AWS resources and credentials.

## 10. Adversarial acceptance

The implementation must fail closed for:

- missing exact `VersionId`;
- stale/substituted version;
- missing target object;
- SHA-256/size mismatch;
- wrong bucket or expected owner/account;
- provider-observed region mismatch;
- Object Lock disabled;
- missing retention;
- expired retention;
- `GOVERNANCE` retention, regardless of claimed bypass capability;
- IAM permission overreach including governance bypass/delete/retention mutation;
- missing IAM policy evidence when least privilege is claimed;
- location/profile/credential-domain substitution;
- same-region, same-principal or same-credential-domain pair collision;
- unknown serialized fields and digest tampering;
- any attempted ten-year durability claim.

Existing LRD-01C/01G escrow, recovery, health and drift suites remain regression dependencies.

## 11. External evidence boundary

Repository CI can provide `ENGINEERING PASS` for the adapter/verifier implementation only. It cannot
create real AWS provider evidence because no provider response is authoritative unless it comes from
an actual configured AWS account, bucket, exact object version and credential context.

Real provider closure requires two real S3 Object Lock profiles with:

- Object Lock enabled;
- active COMPLIANCE retention on every exact tested version;
- distinct regions;
- distinct credential domains/principals;
- expected bucket-owner checks;
- least-privilege policy-simulation evidence or an explicitly equivalent provider evidence path;
- verified replication and target-only restore after source unavailability;
- preserved provider receipts and exact version identities outside secrets;
- no static credentials committed to GitHub.

Until those resources exist and the live drill is executed, external provider evidence remains
`INCOMPLETE`. No mock, fixture or repository text may change that state.

## 12. Explicit non-claims

LRD-01H grants or claims no:

- Canonical Case Ledger write authority;
- Product/Gold/policy/trust mutation authority;
- release/tag authority;
- provider credential storage authority;
- automatic legal-hold mutation;
- regulatory/archival/security certification;
- provider SLA;
- ten-year durability SLA.

`ten_year_durability_claim` is structurally forced to `false` in the pair report.

## 13. Definition of Done

LRD-01H may be `CLOSED / ENGINEERING PASS` only after one exact closure line proves:

1. AWS adapter remains below `ArtifactEscrowBackendV1`;
2. exact S3 `VersionId` + SHA-256 + size binding;
3. active COMPLIANCE/Object-Lock provider verification from real AWS APIs;
4. read-only retention/legal-hold/Object-Lock/caller evidence;
5. least-privilege credential evidence with destructive/governance-bypass overreach rejected;
6. two real provider locations with distinct region/principal/credential domains;
7. exact 01G replication path and verified reread;
8. target-only restore after real source unavailability;
9. focused/adversarial tests and LRD-01C/01G/recovery regression;
10. Ruff, strict MyPy, full repository regression and security/policy gates;
11. exact-head CI on one unchanged candidate SHA;
12. guarded merge and resulting-main post-merge validation;
13. historical `v1.0.1` tag/target/release unchanged;
14. real provider evidence preserved and explicitly distinguished from repository test evidence.

If real AWS resources or credentials are unavailable after all repository engineering work is
complete, that absence is a true external-evidence `HARD BLOCKER`, not a reason to weaken the gate.
