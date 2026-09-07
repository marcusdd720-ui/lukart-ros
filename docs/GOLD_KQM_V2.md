# Gold Corpus / KQM v2

Status: PHX-02 active engineering contract
PHX-01 baseline: `main @ 796bbce41ecfa5bc8bdabea70a4d31d6b4ff2cfd`
Authority class: immutable evaluation input + deterministic measurement projection

## 1. Boundary

Gold Corpus / KQM v2 is not a Product truth authority and is not a writable case-history
system. The Canonical Case Ledger remains the only authoritative writable SSOT for case
history.

PHX-02 may:

- verify exact Gold source bytes;
- derive canonical semantic corpus identity;
- describe exact split membership;
- bind a KQM policy and evaluator identity;
- bind evaluation to exact per-case Canonical Ledger heads;
- produce immutable deterministic KQM measurement projections.

PHX-02 may not:

- append to or rewrite Canonical Case Ledger history;
- promote any assertion to trusted epistemic state;
- tune against locked evaluation data outside explicit certification purpose;
- manufacture independent freeze/review evidence;
- silently relax a threshold;
- accept unknown schema, canonicalization or digest identifiers.

## 2. Gold identity

`GoldCorpusIdentity` separates two forms of identity:

1. `source_digest` — SHA-256 of the exact source file bytes. This detects any source-file
   modification, including formatting changes.
2. `canonical_content_digest` — content address of the parsed semantic JSON value using
   `lukart.canonical-json.v1`. This identifies semantic corpus content independently from
   non-semantic JSON formatting.

The Gold identity also binds:

- exact manifest content address;
- corpus id/version;
- immutable baseline release/SHA;
- privacy classification;
- exact, disjoint case membership for development, validation and locked evaluation;
- locked-evaluation policy;
- explicit review state.

The current candidate remains `candidate_pending_independent_freeze` with no reviewer.
The PHX-02 code intentionally has no `freeze()` or `certify()` operation. A future
independent freeze requires separately verifiable external evidence and a separately
versioned contract; repository text alone is insufficient.

## 3. Locked evaluation

Locked evaluation is policy-constrained data, not a convenience flag.
`locked_evaluation` may be included in `EvaluationInputIdentity` only when the evaluation
purpose is exactly `certification`. Development and validation purposes fail closed if
locked cases are requested.

This contract does not itself execute the locked suite; it only makes any authorized
future execution exact, attributable and content-addressed.

## 4. KQM policy

`KQMPolicy` v2 is immutable and content-addressed. It binds metric names, direction,
warning threshold, release threshold, baseline and safety controls.

Required safety controls are:

- `missing_metric = FAIL`;
- threshold relaxation requires a versioned policy change;
- evaluator may not mutate Product state;
- all thresholds must be finite;
- only `min` and `max` directions are accepted;
- threshold ordering must be internally consistent.

Unknown or unexpected metrics do not silently join the metric set. They are a contract
failure until an explicit versioned policy change introduces them.

## 5. Evaluator identity

`EvaluatorIdentity` binds:

- logical evaluator id;
- evaluator version;
- exact evaluator code SHA;
- exact `RuntimeIdentity` digest, including declared provider/plugin/config/corpus
  identity according to the runtime identity contract.

Provider/model changes therefore produce a different evaluator identity without PHX-02
embedding provider-specific semantics.

## 6. Evaluation input identity

`EvaluationInputIdentity` binds the exact identities of:

- Gold corpus;
- KQM policy;
- evaluator;
- evaluation purpose;
- selected split(s);
- selected case ids;
- exact Canonical Ledger head for every selected case.

The ledger-head set must exactly cover the selected case set. A different event head,
including a transition from an explicit empty/genesis state to a concrete head, produces
a different evaluation input identity.

This is a read-side dependency contract. It does not grant ledger write capability.

## 7. KQM projection

`KQMProjection` is an immutable measurement artifact over one exact
`EvaluationInputIdentity`.

It binds:

- evaluation input identity;
- policy identity;
- evaluator identity;
- exact finite metric values;
- deterministic PASS/FAIL result;
- explicit failure reasons;
- content-addressed projection identity.

Missing required metrics produce a deterministic FAIL projection. Non-finite values and
unregistered metrics fail the contract. A projection cannot change Product state and
cannot be interpreted as an epistemic promotion.

## 8. Offline tamper verification

Gold identity, policy, evaluator and projection structures carry content addresses over
their canonical bodies. Re-reading a serialized artifact with modified semantic fields
while retaining the original identity fails verification.

Content addressing proves consistency with an expected identity. It is not a replacement
for signatures, authorization or independent review attestations.

## 9. Relationship to existing components

Existing Post-v1 and P3 KQM implementations remain useful evaluators and historical
measurement/provenance transports. They do not become competing truth authorities.

`PersistentLongitudinalQualityStore` may retain historical quality points; new PHX-02
identity contracts define what exact corpus/policy/evaluator/ledger state a measurement
refers to. A later migration of quality-history persistence must preserve these identities
rather than create a second writable case-history authority.

## 10. Acceptance evidence

PHX-02 engineering closure requires one exact candidate SHA with:

- current real Gold corpus/manifest raw-byte verification;
- deterministic Gold identity;
- exact split membership and duplicate/mismatch rejection;
- pending independent review preserved;
- deterministic KQM policy/evaluator/input/projection identities;
- locked-split misuse rejection;
- ledger-head change invalidating evaluation-input identity;
- missing/unexpected/non-finite metric adversarial tests;
- unknown schema/profile/algorithm rejection;
- offline tamper rejection;
- static proof of no Canonical Ledger write path in the PHX-02 loader;
- strict MyPy trust boundary;
- Ruff, MyPy, focused/adversarial tests, full regression and required CI;
- guarded exact-SHA merge;
- post-merge validation on resulting `main`.

Engineering PASS does not constitute independent Gold freeze, analytical certification,
external security review or regulatory certification.
