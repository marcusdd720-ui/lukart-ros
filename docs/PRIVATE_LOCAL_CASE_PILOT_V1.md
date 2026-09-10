# CASE-OPS-06 — Private Local End-to-End Pilot Evidence v1

Status: `CASE-OPS-06 engineering contract`
Parent program: `continuous LRD-01`
Predecessor: `CASE-OPS-05 — Operator Recovery & Custody v1`
Deployment boundary: `PRIVATE LOCAL / NON-CLOUD`

## Problem

The repository already verifies private encrypted evidence, immutable derivation provenance,
Canonical Case Ledger registration, Product Runtime v1 and Case Replay v2 independently. A real
private case still needs one fail-closed local path proving that the exact verified private
evidence projection is the projection registered in an exact CCL bundle and that this same bundle
can traverse Product Runtime and replay without introducing another case-history authority.

The pilot must not infer or manufacture CCL history from files. A local directory, document
inventory or successful decryption is not sufficient evidence that authoritative case history
contains the projection.

## Decision

CASE-OPS-06 composes existing controls instead of adding a new reasoning or persistence system:

`verified private evidence -> CASE-OPS projection -> exact CCL registration event ->`
`Epistemic projection -> Evidence Trust Graph -> bounded fixed pilot reasoning ->`
`ProductRuntimeProofV1 -> Case Replay v2 -> digest-only pilot receipt`

The CCL remains the sole authoritative writable case-history SSOT. CASE-OPS-06 has no CCL append,
restore or mutation API.

## Required bindings

A pilot passes only when all of the following are true:

- the private evidence store rebuilds a verified CASE-OPS-02 projection from immutable derivation
  receipts and decryptable evidence;
- the CCL bundle verifies its complete event chain and content address;
- the bundle `case_id` exactly matches the private projection case;
- the bundle contains exactly one `private.evidence.projection.registered.v1` event whose canonical
  payload equals the exact current private projection payload;
- the supplied RuntimeIdentity is v3 and `complete_for_replay`;
- that RuntimeIdentity explicitly contains the private projection digest in its declared evidence
  inventory;
- the registration event's runtime identity digest equals the supplied RuntimeIdentity digest;
- Product Runtime v1 rebuilds Epistemic v2, Trust Graph and Case Replay v2 from that exact bundle;
- the fixed pilot reasoning evidence reference resolves to the exact CCL registration EVENT node;
- the complete Product runtime and replay verify before a receipt is emitted.

Unknown/unbound fields in an externally supplied CCL bundle are rejected by comparing the parsed
bundle back to its exact canonical representation. This closes the base bundle parser's deliberate
forward-compatibility surface at the private pilot trust boundary.

## Pilot reasoning boundary

CASE-OPS-06 intentionally does **not** perform substantive legal/factual case reasoning. The fixed
reasoning target proves only the operational proposition that the verified private projection is
registered in CCL and can traverse the Product trust chain. It therefore cannot be misread as a
legal conclusion about a person's case.

Substantive facts, claims, hypotheses and recommendations continue to require their own exact CCL
and epistemic evidence. No FACT about the underlying case is created by this pilot.

## Receipt and privacy

The pilot receipt is content-addressed and contains only bounded identities/counts/statuses:

- opaque case-scope digest;
- private projection identity and document count;
- exact CCL bundle/head and registration-event digests;
- RuntimeIdentity digest;
- Product runtime proof identity;
- replay manifest/bundle identities;
- Epistemic and Trust Graph identities;
- reasoning result digest/outcome;
- explicit input class and PASS result.

It does not contain evidence bytes, filenames, paths, names, case title, reasoning source text,
private keys or credentials. Operator receipts are written outside the public repository and are
ignored by Git.

`SYNTHETIC_TEST` and `OPERATOR_DECLARED_PRIVATE_LOCAL_CASE` are explicit input classes. The latter
is an operator declaration, not something public CI can independently verify.

## Operator contract

`scripts/private_case_pilot.py` requires:

- a private local case key/data root;
- exact tenant identity;
- every historical/active local evidence key required to verify the private store;
- an exported exact CCL bundle JSON kept outside the public repository;
- a complete RuntimeIdentity v3 JSON kept outside the public repository;
- an output location outside the public repository;
- explicit `--confirm-private-local-case` declaration.

The script prints digests/statuses only. Real private case bytes or keys must never be copied into
GitHub, public CI, workflow artifacts or chat merely to obtain a pilot PASS.

## Adversarial requirements

Synthetic CI must prove:

- exact private evidence -> projection -> CCL -> Product Runtime -> Replay PASS;
- deterministic receipt for identical exact inputs;
- receipt contains no evidence content/path/filename;
- repository receipt output is refused;
- missing exact projection registration fails closed;
- runtime identity not binding the projection fails closed;
- incomplete RuntimeIdentity v3 fails closed;
- external CCL JSON with unbound/unknown fields fails closed;
- runtime identity parser rejects unknown/incomplete shapes;
- existing CASE-OPS, Product Runtime and Case Replay regressions remain green.

## Non-claims / operational boundary

Engineering PASS means the local pilot mechanism is implemented and validated with synthetic data.
It does not mean a real private case was executed on the user's workstation. The operational
milestone is complete only after a local operator runs the command against private evidence and an
actual CCL bundle and obtains a digest-only receipt.

No independent review, cloud durability, geographic custody, legal correctness or external
security certification is implied.
