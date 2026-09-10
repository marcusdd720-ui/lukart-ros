# CASE-OPS-05 — Operator Recovery & Custody v1

Status: `CASE-OPS-05 engineering contract`
Parent program: `continuous LRD-01`
Predecessor: `CASE-OPS-04 — Redundant Offline Recovery Set & Restore Drill v1`
Deployment boundary: `LOCAL / NON-CLOUD`

## Problem and measured gap

CASE-OPS-04 proves a two-member `1-of-2` recovery design in code and synthetic CI, but the
closed stage deliberately does not claim that two real removable devices, independent custody,
an offline workstation state, or an actual operator disaster-recovery drill exist.

A second practical gap is lifecycle management. The CASE-OPS-04 recovery-set object is
content-addressed but was returned only in memory by the core API. There was no operator command
that persisted identical digest-only set records beside both members, no operator evidence record
that separated machine proof from physical assertions, and no supported way to issue a fresh
recovery set from one surviving member after a recovery-secret compromise or loss.

CASE-OPS-05 closes those engineering and operator-tooling gaps without claiming to perform a real
physical drill from public CI.

## Evidence and alternatives

Existing controls already provide:

- CASE-OPS-03 authenticated recovery capsules with encrypted evidence/provenance and wrapped
  historical/active evidence keys;
- CASE-OPS-04 two independently wrapped members on distinct filesystem-device observations;
- exact snapshot/capsule/key-envelope identities;
- single-member restore and two-member machine drill;
- case-scoped authorization and fail-closed verification.

Material alternatives:

1. **Document-only runbook.** Rejected as insufficient because it leaves set identity, drill
   evidence and recovery-secret rotation as manual conventions.
2. **Custom threshold/Shamir custody.** Rejected: it creates new cryptographic share lifecycle and
   operator complexity before existing validated primitives are exhausted.
3. **TPM/HSM/OS-keystore as mandatory recovery authority.** Rejected for this portable local
   baseline because replacement-machine recovery would inherit platform/hardware dependencies.
4. **Operator layer over CASE-OPS-03/04 with canonical records, explicit assertions and fresh-set
   rotation from one surviving member.** Selected as the smallest justified improvement.

## Trust and authority boundary

The Canonical Case Ledger remains the only authoritative writable SSOT for case history.
CASE-OPS-05 records are operational recovery evidence only. They do not alter evidence bytes,
CCL events, Epistemic State, Trust Graph, reasoning output or release authority.

Recovery-set records, operator drill evidence and rotation receipts contain digests and bounded
metadata only. They contain no plaintext evidence, source filename/path, raw evidence key,
recovery passphrase or cloud credential.

## Recovery-set record

`write_redundant_recovery_set_records()` writes the exact canonical CASE-OPS-04
`RecoverySetV1` JSON beside both recovery members. The two files are byte-identical and can be
reconstructed from either surviving copy. The record remains a projection over the underlying
capsule identities; losing it does not make a CASE-OPS-03 capsule unreadable.

Records are written with exclusive creation, mode `0600` where applicable and outside the public
repository. Parsing requires exact canonical JSON and strict CASE-OPS-04 schema/profile validation.
Unknown or additional fields fail closed.

## Operator drill evidence

A real disaster-recovery drill has two evidence classes that MUST NOT be conflated:

### Machine-verified

The existing CASE-OPS-04 machine drill verifies both recovery members, exact snapshot identity,
case scope, passphrase authentication, recovered key identities and independent restore of both
members.

### Operator-asserted

Repository code cannot independently prove these physical facts on a hosted CI runner:

- the source workstation was unavailable for the drill;
- networking was disconnected;
- the two recovery media were physically separate;
- the two recovery secrets were separately custodied.

CASE-OPS-05 records these booleans under assertion class
`OPERATOR_ASSERTED_NOT_INDEPENDENTLY_VERIFIED`. The result can be
`OPERATOR_ATTESTED_MACHINE_PASS` only when the machine drill is PASS and all four assertions are
explicitly true. Missing assertions yield `INCOMPLETE_OPERATOR_ASSERTIONS`, never implicit PASS.

This is operator evidence, not independent audit, security certification or proof of geography.

## Recovery-secret rotation from one surviving member

`rotate_recovery_set_secrets()` accepts one exact surviving recovery member and its current
passphrase, restores only encrypted evidence/provenance into a temporary local staging store and
issues a completely fresh CASE-OPS-04 two-member set under two new independent passphrases.

The operation requires:

- exact source member identity from the old recovery-set record;
- exact tenant/case authorization;
- valid old passphrase for the selected surviving member;
- two new passphrases different from each other;
- neither new passphrase may reuse the surviving old passphrase;
- two new recovery destinations satisfying the CASE-OPS-04 distinct-device policy;
- exact snapshot identity preserved from old set to new set.

The temporary restored store contains encrypted evidence/provenance only and is removed on exit.
Recovered raw AES keys exist only in memory. Historical capsules are never rewritten and old
recovery members are never automatically deleted. Rotation therefore creates a new immutable
recovery-set identity and a digest-only lineage receipt instead of mutating history.

If a new set is created but post-creation snapshot/identity invariants fail, the newly created
members are removed on a best-effort basis and the operation fails closed.

## Operator CLI

`scripts/private_case_recovery.py` remains the single recovery entry point and now supports:

- `create` / `verify` / `restore` for one CASE-OPS-03 capsule;
- `set-create` for a CASE-OPS-04 two-member set plus redundant canonical records;
- `set-verify` for exact two-member verification;
- `set-drill` for two-member restore plus CASE-OPS-05 operator evidence;
- `set-rotate` for fresh recovery-secret issuance from one surviving member.

Recovery passphrases are collected only with `getpass`; they are never accepted as command-line
arguments, persisted in receipts or printed. Key files used for live-store set creation must remain
outside the public repository.

## Real drill procedure

The engineering control is ready for a real local drill, but a real drill is not complete until an
operator performs it on actual local hardware. The required operational sequence is:

1. Place member A and member B on two physically separate recovery media that are each separate
   from the live case-data device.
2. Custody passphrase A and passphrase B independently; do not store both in the same uncontrolled
   device/account/location.
3. Disconnect networking and make the source workstation/data root unavailable to the drill
   environment.
4. Run `set-verify` using the duplicated recovery-set record and both members.
5. Run `set-drill` into two empty local restore targets with all four explicit operator assertions.
6. Verify that the command emits `OPERATOR_ATTESTED_MACHINE_PASS` and store the digest-only drill
   receipt with operational records, not in the public repository.
7. If one secret/member is lost or suspected compromised, use `set-rotate` from the surviving
   exact member and issue a new two-member set before retiring the old custody material.

The operator must not interpret a hosted CI PASS as evidence that steps 1–3 happened in reality.

## Failure and adversarial requirements

Synthetic tests must cover at least:

- canonical byte-identical duplicated recovery-set records;
- record unknown-field/tamper rejection;
- repository-tree record refusal;
- machine drill PASS separated from operator assertions;
- incomplete assertions never becoming attested PASS;
- recovery-secret rotation from one surviving member after the other member is removed;
- exact snapshot and evidence-key identity preservation through rotation;
- fresh recovery-set identity after rotation;
- old-passphrase reuse rejection before restore;
- wrong surviving passphrase leaving no new rotation members;
- no passphrase/raw-key/path leakage in set, drill or rotation records.

CASE-OPS-01 through CASE-OPS-04 regressions remain mandatory. Public CI remains synthetic-only.

## Residual risk / next stage

CASE-OPS-05 makes the real drill executable and auditable, but it cannot itself manufacture the
external fact that the operator used two real devices, disconnected networking or maintained
independent custody. The first remaining P0 item after engineering closure is therefore a genuine
local operator run producing a real digest-only CASE-OPS-05 drill receipt.

A separate real-case pilot is also still required. Public CI must not receive real case bytes,
private keys or real passphrases. Subsequent engineering may strengthen OCR runtime fingerprinting,
legacy encrypted-backup migration and unified local operator workflows, but those stages must not
reinterpret an unperformed physical drill as completed.
