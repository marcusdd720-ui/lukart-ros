# LRD-01A acceptance boundary

Acceptance is exact-SHA only. A branch, commit, PR or partial green state is not closure.

Required terminal sequence:

`exact PR head -> complete required CI -> unchanged head/base -> guarded merge -> resulting main -> post-merge validation -> immutable v1.0.1 baseline verification`.

This marker carries no release, Product, CCL, Gold, trust-promotion or certification authority.
