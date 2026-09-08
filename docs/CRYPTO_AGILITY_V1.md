# CRY-01 — Crypto Agility / Trust-Set / Key Lifecycle v1

Status: `CLOSED / ENGINEERING PASS`

Implementation PR: `#170`
Validated PR head: `69108c93d224803c21d9ba76b93a883eada32fe1`
Implementation merge: `main @ 2c705dde2c077f04b6c820e2104cb27cb320ab36`

## Problem

The Enterprise E3 attestation boundary already provides Ed25519 signing, canonical payload
binding, key IDs, expiry and caller-supplied revocation. XCH-01 correctly reuses that
primitive for offline-verifiable provenance.

The remaining long-horizon weakness is the verification context itself. A caller currently
provides a public-key map plus revoked key IDs, but that trust context has no independent,
content-addressed identity and no explicit rotation lineage. Two verifications can therefore
use different trust material without producing an artifact that proves which exact trust set
was used.

CRY-01 closes that gap without replacing the existing cryptographic primitive.

## Decision

CRY-01 introduces a separately versioned `CryptoTrustSetV1` around the existing Enterprise
`AttestationSigner` / `AttestationVerifier`.

The trust set binds:

- exact public verification key bytes;
- immutable `key_id`;
- explicit algorithm identifier;
- lifecycle state: `ACTIVE`, `RETIRED` or `REVOKED`;
- activation time and optional planned retirement time;
- least-privilege attestation purposes;
- explicit predecessor key ID for planned rotation;
- optional prior trust-set digest;
- deterministic content-addressed trust-set identity.

Private key material remains runtime-supplied and outside repository state.

## Algorithm agility

The v1 registry implements only `ED25519` because that is the cryptographic primitive already
implemented and validated by the Product/Enterprise runtime. Unknown or unimplemented
algorithms fail closed.

The algorithm identifier is explicit so a future adapter can add a new signature algorithm
without changing the meaning of historical Ed25519 artifacts. Adding ML-DSA, SLH-DSA or any
other post-quantum signature requires a separately versioned implementation, dependency and
migration decision plus focused/adversarial validation. CRY-01 does not claim post-quantum
support merely because the contract is algorithm-agile.

This follows the long-horizon principle of crypto agility: replaceability and migration are
designed now, while cryptographic support is claimed only after implemented evidence exists.

## Trust-set identity

`CryptoTrustSetV1.trust_set_digest` is derived from canonical trust-set content. Verification
requires the caller to supply an independently expected digest and fails if the supplied
trust set does not match it.

A trust-set lineage pointer is continuity metadata, not self-authentication. A new trust set
cannot become trusted merely by naming an old digest; the expected trust-set identity must
still cross the normal configuration/governance trust boundary.

## Key lifecycle semantics

### ACTIVE

An ACTIVE key may sign new attestations only when:

- its exact public key matches the runtime signer;
- the requested purpose is explicitly allowed;
- issuance is not before activation;
- issuance is before any planned retirement time;
- the exact trust-set digest matches the externally pinned expected identity.

### RETIRED

RETIREMENT is planned lifecycle management, not evidence of compromise.

A RETIRED key cannot sign new attestations. A historical cryptographically valid attestation
issued before its recorded retirement may still verify, subject to normal attestation expiry.
This preserves long-term offline verification of historical artifacts after planned rotation.

### REVOKED

REVOCATION represents loss of trust, including compromise. A REVOKED key is rejected
unconditionally. A signature cannot regain trust by carrying an earlier `issued_at`, because
that timestamp is inside the signed artifact and is not an independent trusted timestamp.

This intentionally differs from planned retirement.

## Verification receipt

Successful verification creates `CryptoVerificationV1`, binding:

- exact attestation digest;
- exact trust-set digest;
- exact trust-key digest;
- exact algorithm identifier;
- content-addressed verification identity.

The receipt proves which cryptographic verification context produced the result. It does not
prove epistemic truth, human review, regulatory compliance or release authorization.

## Rotation

Planned rotation keeps historical keys in the trust set and links a successor to a known
predecessor. The predecessor must already exist in the same trust set and must have an earlier
activation time. Duplicate IDs, self-predecessors, missing predecessors and time-reversed
lineage fail closed.

This v1 contract intentionally does not automate trust-root promotion. Automatic
`old -> new = trusted` would make repository/runtime metadata a competing trust authority.
Trust-set acceptance remains an external governance/configuration decision.

## Serialization and compatibility

Trust keys and trust sets have strict schemas and strict field sets. Unknown schema values,
unknown algorithms, unknown lifecycle states, unknown purposes, malformed public keys,
invalid digests and unknown serialized fields fail closed.

Historical E3/XCH-01 artifacts remain valid at their original trust level. They are not
silently rewritten or reclassified as CRY-01 evidence. A later XCH-02 stage may bind new
exchange artifacts to CRY-01 verification receipts without mutating XCH-01 history.

## Trust boundaries

CRY-01:

- has no Canonical Case Ledger write path;
- creates no Product truth or epistemic promotion authority;
- stores no private key material;
- introduces no second signature implementation;
- cannot authorize a release;
- cannot manufacture independent/security/external certification;
- cannot claim post-quantum protection until a separately implemented algorithm adapter is
  validated;
- treats trust-set lineage as evidence metadata, never automatic root-of-trust promotion.

## Long-horizon migration posture

For the 10+ year horizon, the intended sequence is:

1. inventory and bind every trust context by exact identity;
2. rotate Ed25519 keys without losing historical verification;
3. keep algorithm choice explicit and replaceable;
4. introduce a separately versioned post-quantum adapter only after runtime support and
   interoperability are measurable;
5. exercise hybrid/cross-algorithm migration under explicit policy rather than silently
   replacing historical signatures;
6. preserve old verification material for offline replay while denying compromised keys;
7. bind later exchange/release/policy artifacts to exact trust-set and algorithm identities.

## Validation requirements

Closure requires one exact PR-head SHA to pass:

- deterministic trust-set identity and strict serialization round trip;
- ACTIVE sign/verify happy path;
- planned rotation and historical RETIRED verification;
- rejection of new RETIRED signing;
- unconditional REVOKED rejection including a valid backdated signature;
- wrong expected trust-set identity rejection;
- least-privilege purpose rejection;
- signer/public-key substitution rejection;
- unknown algorithm/field rejection;
- missing or invalid predecessor rejection;
- Ruff and MyPy;
- full pytest regression;
- Stage Gate and repository security/policy workflows;
- guarded exact-head merge;
- resulting-main post-merge validation;
- immutable `v1.0.1` baseline/release side-effect check.

## Exact closure evidence

- PR #170 exact validated head `69108c93d224803c21d9ba76b93a883eada32fe1` passed all 11 required PR workflows, including CI Foundation, Stage Gate, Enterprise Hardcore Gate and Enterprise CodeQL.
- Guarded merge used the unchanged validated head and expected `main` base.
- Implementation merge is `main @ 2c705dde2c077f04b6c820e2104cb27cb320ab36`.
- The implementation merge completed nine post-merge workflow runs, all `SUCCESS`, with zero queued or in-progress runs at closure evaluation and no failed run observed.
- Historical `v1.0.1` tag object remained `9f7c0b28f766c8921e63b1d517fefcc96aa991d4` and its target commit remained `802013c4d0e53dc12306a97e1877ebba86af64a7`.
- No new release was published as a CRY-01 side effect.
- Engineering closure does not claim independent cryptographic, external, regulatory or post-quantum certification.

Engineering PASS does not imply independent cryptographic review or certification.
