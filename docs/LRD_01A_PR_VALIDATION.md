# LRD-01A PR validation intent

Candidate branch: `lrd-01a-replay-closure-architecture`.

Exact-head validation must cover the strict coverage parser, the 30-item matrix, adversarial
negative cases, full regression, Ruff, strict MyPy, repository security/policy workflows and
the immutable v1.0.1 release guard. Any subsequent candidate change invalidates prior PASS
and requires fresh exact-head evidence.
