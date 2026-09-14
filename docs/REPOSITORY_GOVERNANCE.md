# Repository Governance

This document describes the repository-governance trust boundary for `lukart-ros`.
`docs/WORKING_PRINCIPLES.md` remains the superior engineering standard and
`config/enterprise_v1.json` remains the canonical machine-enforced enterprise policy.

## Governance modes

The repository supports two truthful governance modes:

1. **Independent review** — the default/fail-closed mode. Required approvals must
   come from genuine independent reviewers with authenticated GitHub provenance.
2. **Solo maintainer** — an explicitly selected mode for a repository maintained
   by one owner when independent external reviewers are not available.

Solo-maintainer governance never claims independent review or independent
certification. The truthful state is:

- `reviewer_independent: false`
- `independent_external_review: NOT_PERFORMED`

The historical product-certification SOLO_MAINTAINER_MODE and repository
governance are separate controls. Product certification mode does not by itself
change branch protection, rulesets, required checks, or merge authority.

## Solo-maintainer compensating controls

A safe solo-maintainer cutover must retain all controls that do not logically
require a second human:

- pull-request-only changes to `main`;
- deletion and non-fast-forward protection;
- empty bypass list;
- merge-commit-only repository policy;
- strict required status checks;
- exact-SHA CI and governance validation;
- action full-SHA pinning and least-privilege workflow permissions;
- CodeQL, architectural audit, smoke tests, Production Validation and Enterprise
  Hardcore Gate;
- required-check source binding and collision detection;
- review-thread resolution;
- post-merge validation;
- truthful absence of independent external review.

In solo mode, native approval requirements that are impossible for one account
must not be represented as satisfied. Instead, a required `solo-governance`
check provides head-bound maintainer acceptance after terminal technical checks.

## Head-bound maintainer attestation

The final maintainer acceptance is a GitHub PR conversation comment authored by
the repository owner with `author_association=OWNER`.

Canonical form:

```text
LUKART-SOLO-MAINTAINER-ATTESTATION-V1
candidate_sha: <40-character final PR head SHA>
decision: ACCEPT
independent_external_review: NOT_PERFORMED
risk_class: <ordinary|critical|governance>
```

A later attestation for the same candidate with `decision: REVOKE` invalidates an
earlier acceptance. Any new push changes the candidate SHA and therefore
invalidates the previous attestation automatically.

The attestation is valid only after every technical required check for the same
candidate SHA is terminal `success`.

## Cooling-off policy

Cooling-off time is measured from server-side GitHub timestamps after the last
required technical check becomes successful:

- ordinary change: 0 seconds;
- critical change: 2 hours;
- governance/self-protection change: 24 hours.

This delay is a compensating control, not an independent review substitute.

## Change classification and topology

Critical paths are defined by the canonical enterprise policy.

Governance/self-protection paths include the enterprise governance config,
CODEOWNERS, governance workflows, governance gate scripts/tests, this document
and `docs/WORKING_PRINCIPLES.md`.

A PR that changes governance/self-protection files must be governance-only. It
must not mix those changes with unrelated product/runtime modifications. This
prevents a maintainer from weakening the trust boundary and shipping unrelated
code in the same acceptance event.

## Cutover protocol

The transition from independent review to solo-maintainer governance is
two-phase and fail-closed:

1. Implement and validate the solo gate while the existing independent-review
   ruleset remains active.
2. Add `solo-governance` as a required check before reducing human-review
   requirements.
3. Verify live readback.
4. Change the canonical enterprise policy to `solo_maintainer`, refresh any
   privileged ruleset snapshot, and produce a fresh candidate SHA.
5. Re-run the complete exact-SHA validation envelope.
6. Wait for the risk-class cooling-off period.
7. Record the final head-bound maintainer attestation.
8. Re-run `solo-governance` and verify all required checks.
9. Merge only through the protected merge path.
10. Perform post-merge validation on the resulting `main` SHA.

At no point may the repository claim independent human review when none occurred.

## Break-glass

There is no permanent bypass actor. Emergency recovery must use an explicit,
auditable repair path and must not silently weaken the ruleset or required
checks.

## Signing and release integrity

Required signed commits are a separate control and must not be enabled until
every authorized write path can produce representative verified commits.

GitHub Release immutability is also a separate control from tag protection and
from historical baseline semantics. It must be verified independently before
being claimed.
