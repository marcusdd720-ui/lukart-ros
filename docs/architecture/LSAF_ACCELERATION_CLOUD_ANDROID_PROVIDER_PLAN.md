# LSAF — Acceleration, Cloud, Android & Provider Plan
Date: 2026-10-05
Status: CANONICAL PLAN / IMPLEMENT INCREMENTALLY

## Portfolio order
P0: Generator Pism usable path
P0: UAOS Execution Truth + liveness + soak
P0: BUILD-vs-ADOPT pre-audit operationalization
P1: LSAF provider/capability/evidence foundation
P2: AI Media and LATAM continuation

## Provider topology
Primary builder: OpenAI Codex harness with strongest available included model on the user's authorized plan.
Independent reviewer: different model family/provider (Google Gemini or Anthropic Claude).
Hermes: replaceable execution/orchestration adapter.
Zero-cost pool: only providers that pass live endpoint, pricing, quota, privacy and benchmark verification.
Evidence/CI: GitHub + self-hosted runner + exact-SHA + deterministic tests.

## Canonical Integration Intake Pipeline
1. IDEA_INTAKE
2. CLASSIFY
3. BUILD_vs_ADOPT_PRE_AUDIT
4. DEPENDENCY_MAP
5. DESIGN_CONTRACT
6. BRANCH_WORKTREE
7. IMPLEMENT
8. FOCUSED_TEST
9. REGRESSION
10. INDEPENDENT_REVIEW
11. EXACT_SHA_CI
12. PROMOTION_GATE
13. POST_MERGE_VERIFICATION
14. CLOSURE_RECEIPT

Every idea must have a machine-readable manifest in addition to Markdown.

## Cloud compute strategy
1. Existing PC as control node / source workspace.
2. GitHub Codespaces for burst development when quota is available.
3. Always-free/low-risk cloud VM for always-on lightweight agents/control plane after BUILD-vs-ADOPT verification.
4. Paid VM only after explicit approval.
Never use cloud RAM as the source of truth.

## Android strategy
Phone is primarily a control/approval terminal, not the heavy builder.
Preferred pattern:
Android -> secure tunnel/VPN -> browser/SSH -> remote LSAF control plane -> isolated agents/worktrees.

Optional on-device lane:
Termux + tmux + OpenCode/Codex-compatible CLI for emergency/light tasks.

Do not broadly store production secrets on the phone.

## Security
- zero-trust network access
- no public unauthenticated agent UI
- device-specific credentials
- least-privilege scopes
- human approval for irreversible operations
- secrets never embedded in repository or Markdown
- remote agents isolated per workspace
- paid fallback blocked without explicit authorization

## Operational automation
P0 Orchestrator order:
Generator Pism > UAOS > BUILD-vs-ADOPT > LSAF.

Architecture Review must include:
Execution Truth, Evidence Ledger, layered memory, Capability Genome, Quorum, Provider Darwinism, anti-entropy, trust decay, blast-radius budgets, degradation ladder and vendor-extinction drills.
