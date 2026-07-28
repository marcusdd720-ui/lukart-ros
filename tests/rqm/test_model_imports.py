from factory.rqm.model import (
    Finding,
    Metadata,
    Report,
    Result,
    Severity,
)


def test_imports():

    assert Severity is not None
    assert Finding is not None
    assert Result is not None
    assert Report is not None
    assert Metadata is not None
