# SOLO_MAINTAINER_MODE

`SOLO_MAINTAINER_MODE` is an explicit certification profile for a repository maintained by a single owner when no independent external human reviewer is available.

## Truth boundary

This mode does **not** claim independent human review. Every maintainer acceptance artifact must record:

- `review_mode: "solo_maintainer"`
- `reviewer_kind: "maintainer"`
- `reviewer_independent: false`
- `independent_external_review: "NOT_PERFORMED"`

The repository profile in `factory/certification_profile.json` is the authoritative mode declaration. The maintainer identity and authorizer must equal the repository owner.

## Gates retained

Solo mode does not waive corpus binding, exact SHA/hash binding, annotation and criticality approval, freeze approval, IAA requirements when applicable, locked-evaluation isolation, Step 16/18 review-package binding, CI, architecture audit, smoke tests, Production Validation evidence, same-SHA release gates, release governance, PII/secrets boundaries, or immutable release behavior.

Only the requirement for authenticated provenance from a separate external human account is replaced by an explicit non-independent maintainer acceptance.

## Independent mode

Independent review remains the fail-closed default when a review artifact omits `review_mode`. It continues to require a genuine independent human reviewer and authenticated GitHub provenance.

## Upgrade path

A later independent external review can be performed without rewriting history. Independent review artifacts omit `review_mode`, use `reviewer_kind: "human"` and `reviewer_independent: true`, and must satisfy the authenticated provenance collector. A solo-certified release must never be described as independently human-reviewed unless that later process is completed and separately recorded.
