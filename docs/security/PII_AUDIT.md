# PII / Confidentiality Audit

## Current-tree status

The public tree must contain only source code, documentation, synthetic fixtures, and explicitly approved anonymized benchmark data.

Real case documents, identifiable party data, unredacted court/ZUS/prosecutorial correspondence, production exports, and generated dossiers are prohibited.

The repository's current-tree gate is fail-closed and denies common legal document formats.

## Historical status

Deleting files from the current tree does not remove them from Git history. Historical clearance therefore remains a separate release blocker until the repository history has been audited and, where required, rewritten and verified.

If credentials or private material were ever committed, affected credentials must be rotated.

## Required controls

1. current-tree PII scan;
2. prohibited legal-artifact scan;
3. Git-history review;
4. secret/credential review;
5. private/public data separation.
