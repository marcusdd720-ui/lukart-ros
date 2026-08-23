# LukArt ROS Quality Model — v1.0

LukArt ROS has three independent quality dimensions. A missing measurement is
`PENDING`, not zero.

## RQM — Engineering Quality

Owned by the existing RQM/factory layer.

Measures:

- tests;
- static analysis;
- deterministic behavior;
- schema compatibility;
- graph integrity;
- CI execution.

Target for release: `RQM >= 95`.

## KQM — Knowledge Quality

Implemented after the Ground Truth Corpus is available.

Measures:

- entity precision/recall/F1;
- relation precision/recall/F1;
- critical recall;
- critical precision;
- critical-fact loss;
- regression delta;
- provenance completeness.

Target for release:

- `KQM >= 90`;
- critical recall `>= 100%`;
- no unresolved critical regression.

`KQM = PENDING` until the locked evaluation corpus exists and has been
validated.

## SQM — Security / PII Quality

Measures:

- public-tree PII scan;
- prohibited legal artifact scan;
- repository history review;
- secret/credential exposure review;
- private-vs-public data separation.

Release requirement: `SQM = PASS`.

## Release Gate

```text
RQM >= 95
AND KQM >= 90
AND critical recall >= 100%
AND SQM == PASS
AND no critical regression
    => READY_FOR_RELEASE
```

Any `PENDING` or `BLOCKED` state prevents a release claim. Engineering quality
cannot substitute for knowledge quality, and knowledge quality cannot override
a security failure.
