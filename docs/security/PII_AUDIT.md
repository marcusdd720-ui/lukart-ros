# PII / Confidentiality Audit — 2026-08-23

## Scope

Audit target: public repository `marcusdd720-ui/lukart-ros`, hardening branch
`hardening/10-10-quality-gate`.

## Finding

A repository case directory contained identifiable case information in
Markdown plus tracked DOCX/TXT legal artifacts. The finding is sufficient to
classify the public repository as **NOT CLEARED** for legal-data handling.

The affected material must not remain in the public source tree.

## Immediate remediation

1. Remove the affected case material from the current tree.
2. Add a fail-closed PII/security scan to CI.
3. Deny tracked PDF/DOC/DOCX/ODT/RTF/ZIP legal artifacts in the public tree.
4. Keep real case documents in private storage; use synthetic/anonymized
   fixtures for tests and the Ground Truth Corpus.

## Historical remediation

Deleting files from the current tree does **not** remove them from Git history.
Before any production/public release, the repository history must be reviewed
and, where required, rewritten to remove sensitive blobs. Credentials or
private material must also be rotated if they were ever committed.

This audit therefore records two independent statuses:

- current-tree clearance: pending until the affected material is removed and
  the automated gate passes;
- history clearance: pending until a repository-history audit is completed.

## Policy

The public repository may contain:

- source code;
- documentation;
- synthetic fixtures;
- anonymized benchmark data explicitly approved for publication.

It must not contain:

- real client/case documents;
- identifiable party data;
- unredacted court/ZUS/prosecutorial correspondence;
- production exports or generated dossiers containing case data.
