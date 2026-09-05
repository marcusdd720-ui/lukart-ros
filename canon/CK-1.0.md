# CK-1.0 — Cognitive Kernel Boundary

Canonical ID: CK-1.0
Title: Cognitive Kernel Boundary
Version: 1.0
Status: CANDIDATE CANON
Class: ARCHITECTURE
Stability Index: 4
Owner: Core Architecture
Depends On: KMeta-1.0; FOUNDATION.md; accepted ADRs
Affects: KMR; KCS; KMS; KMP; Evidence; Reasoning; Strategy; Renderer
Supersedes: none
Validation Method: dependency review + implementation mapping + CI/Audit/Stage Gate
Review Requirement: independent architectural review before CANONICAL
Change Policy: versioned change; no silent semantic mutation

## 1. Purpose

CK-1.0 defines the smallest stable cognitive core of Artur OS / LUKART ROS and, equally importantly, defines what is not part of that core.

The kernel is a semantic contract, not a list of Python modules. Implementations may change without changing CK when the same observable contracts and invariants remain satisfied.

## 2. Scope

The Cognitive Kernel owns only cross-domain cognitive primitives that must remain stable across applications such as legal, investigative, financial, or other case-oriented deployments.

The kernel does not own application workflows, UI, legal doctrine, document templates, client portals, external integrations, or model-provider choices.

## 3. Kernel responsibilities

The kernel MUST provide or define contracts for:

1. identity and versioning of cognitive objects;
2. epistemic-state representation and controlled state transitions;
3. provenance/source binding;
4. immutable historical evidence references where the source contract permits;
5. deterministic query/read semantics for a specified model version;
6. model Build and Update boundaries;
7. contradiction/unknown preservation rules;
8. reproducibility identity sufficient for replay;
9. validation hooks that allow TIMR/KQM/audit layers to inspect state without silently mutating trusted state.

## 4. Kernel non-responsibilities

The kernel MUST NOT own:

- case-specific goals;
- legal strategy;
- problem selection;
- evidence-strength scoring policy specific to a jurisdiction;
- document composition or prose generation;
- portal/client communication;
- process deadlines;
- provider-specific LLM prompts;
- external filing/sending authority;
- autonomous merge/deploy authority;
- certification decisions that require independent review.

## 5. Kernel objects

CK recognizes the following primitive categories without prescribing a single storage backend:

- Cognitive Object — versioned object with identity, type, epistemic status and provenance references;
- Relation — typed relation between cognitive objects, itself a cognitive object where epistemic status is material;
- Source Reference — immutable reference to source/evidence material and its integrity identity;
- Model Snapshot — immutable logical view of model state at a version/time;
- Change Set — explicit delta proposed/applied between model states;
- Open Question — explicit representation of unresolved knowledge need.

Detailed schemas belong to lower documents such as KMR.

## 6. Build / Update / Query contract

The kernel distinguishes three operations:

### Build

Construct an initial model state from an explicit bounded input set and declared contracts.

### Update

Apply a validated Change Set to an existing model version and produce a new version. Historical source references MUST NOT be rewritten to make the new model appear retrospectively correct.

### Query

Read a specified model version under explicit scope. Query MUST NOT silently mutate epistemic state.

## 7. Epistemic invariant

No implementation may promote an uncertain state into a trusted fact solely because a model generated or preferred it.

Transitions MUST be controlled by the canonical epistemic state contract and, where promotion requires evidence, the transition MUST include new qualifying evidence/provenance.

## 8. Reality separation

A Model Snapshot is a representation of the system's state of knowledge. It is never identical with Reality.

The kernel MUST preserve the ability to represent:

- uncertainty,
- disagreement,
- incomplete knowledge,
- rejected hypotheses,
- unresolved contradictions,
- abstention.

## 9. Cognitive locality

The kernel permits bounded views/scopes over global knowledge but does not itself define a legal Case. Case boundaries and policies are defined by KCS/KMS.

No kernel primitive grants one case unrestricted access to another case's private context.

## 10. TIMR / validation boundary

TIMR, KQM, security and audit layers may calculate metrics, detect conflicts, evaluate consistency and produce validation artifacts.

They MUST NOT become an alternate source of truth by silently writing their computed scores or conclusions back as trusted facts without an explicit Update path.

## 11. Renderer boundary

Renderer is outside the kernel. Renderer consumes immutable structured results and MUST NOT alter reasoning state, evidence lineage or epistemic classification.

## 12. Controlled learning boundary

Learning is outside direct kernel mutation authority.

Observed outcome -> Learning Candidate -> Experiment -> Measurement -> Promotion Gate -> Versioned Change

Only the final accepted Versioned Change may enter the kernel/model through the normal Update contract.

## 13. Failure modes

Kernel operation MUST fail closed or return an explicit unresolved state when:

- object identity is ambiguous;
- provenance required by contract is absent;
- requested model version cannot be reconstructed;
- an epistemic transition is unauthorized;
- a Change Set would silently rewrite historical evidence;
- query scope attempts to bypass a Case/privacy boundary;
- a computed metric is presented as source evidence;
- implementation cannot identify the version/SHA/schema required for replay.

## 14. Implementation mapping rule

Existing repository components may implement portions of CK without being renamed. A future mapping artifact SHOULD identify which current components satisfy each CK responsibility.

CK-1.0 does not require immediate refactoring of existing Product modules. It first freezes semantic boundaries, then implementation may converge incrementally.

## 15. Validation

CK-1.0 remains Candidate until all are satisfied:

1. a mapping from CK responsibilities to existing repository components is produced;
2. at least one Case Replay proves model/version/provenance reconstruction through the current implementation;
3. KMR and KCS use the KMeta metadata template and do not conflict with CK boundaries;
4. exact-SHA repository CI/Audit/Stage Gate passes;
5. independent architectural review approves the boundary before CANONICAL.
