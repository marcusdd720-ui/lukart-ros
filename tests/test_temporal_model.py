import pytest

from knowledge.temporal import (
    TemporalCertainty,
    TemporalCoordinates,
    TemporalRevision,
    TemporalValue,
    TimelineProjectionRef,
    known_order,
)


def _exact(value: str, provenance: str) -> TemporalValue:
    return TemporalValue(
        value=value,
        certainty=TemporalCertainty.EXACT,
        provenance_ref=provenance,
    )


def test_four_time_axes_remain_distinct() -> None:
    coordinates = TemporalCoordinates(
        event_time=_exact("2026-01-01", "prov:event"),
        source_time=_exact("2026-01-02", "prov:source"),
        knowledge_time=_exact("2026-01-05T10:00:00Z", "prov:ingest"),
        system_time=_exact("2026-01-05T10:01:00Z", "prov:commit"),
    )

    values = {
        coordinates.event_time.value,
        coordinates.source_time.value,
        coordinates.knowledge_time.value,
        coordinates.system_time.value,
    }
    assert len(values) == 4


def test_approximate_time_is_not_silently_ordered_as_exact() -> None:
    approximate = TemporalValue(
        value="2026-01",
        certainty=TemporalCertainty.APPROXIMATE,
        provenance_ref="prov:approximate-source",
    )
    exact = _exact("2026-01-15", "prov:exact-source")

    assert approximate.certainty is TemporalCertainty.APPROXIMATE
    assert known_order(approximate, exact) is None


def test_relative_time_requires_reliable_anchor() -> None:
    with pytest.raises(ValueError, match="anchor"):
        TemporalValue(
            value="three days later",
            certainty=TemporalCertainty.RELATIVE,
            provenance_ref="prov:relative",
        )


def test_revision_preserves_historical_knowledge_state() -> None:
    original = TemporalRevision(
        object_id="OBJ-TIME-1",
        object_version="v1",
        coordinates=TemporalCoordinates(
            event_time=_exact("2026-02-01", "prov:event:v1"),
            source_time=_exact("2026-02-02", "prov:source"),
            knowledge_time=_exact("2026-02-03T09:00:00Z", "prov:knowledge:v1"),
            system_time=_exact("2026-02-03T09:01:00Z", "prov:system:v1"),
        ),
    )

    corrected = original.revise_event_time(
        object_version="v2",
        event_time=_exact("2026-01-31", "prov:event:v2"),
        knowledge_time=_exact("2026-02-10T11:00:00Z", "prov:knowledge:v2"),
        system_time=_exact("2026-02-10T11:01:00Z", "prov:system:v2"),
    )

    assert original.coordinates.event_time.value == "2026-02-01"
    assert original.coordinates.knowledge_time.value == "2026-02-03T09:00:00Z"
    assert corrected.coordinates.event_time.value == "2026-01-31"
    assert corrected.coordinates.source_time == original.coordinates.source_time
    assert corrected.supersedes_version == "v1"


def test_temporal_correction_requires_new_object_version() -> None:
    revision = TemporalRevision(
        object_id="OBJ-TIME-1",
        object_version="v1",
        coordinates=TemporalCoordinates(
            event_time=_exact("2026-03-01", "prov:event"),
            source_time=_exact("2026-03-02", "prov:source"),
            knowledge_time=_exact("2026-03-03T10:00:00Z", "prov:knowledge"),
            system_time=_exact("2026-03-03T10:01:00Z", "prov:system"),
        ),
    )

    with pytest.raises(ValueError, match="new object version"):
        revision.revise_event_time(
            object_version="v1",
            event_time=_exact("2026-02-28", "prov:corrected-event"),
            knowledge_time=_exact("2026-03-04T10:00:00Z", "prov:knowledge:v2"),
            system_time=_exact("2026-03-04T10:01:00Z", "prov:system:v2"),
        )


def test_unknown_and_disputed_times_preserve_partial_order() -> None:
    unknown = TemporalValue(value=None, certainty=TemporalCertainty.UNKNOWN)
    disputed = TemporalValue(
        value="2026-04-01",
        certainty=TemporalCertainty.DISPUTED,
        provenance_ref="prov:disputed",
    )
    exact = _exact("2026-04-02", "prov:exact")

    assert known_order(unknown, exact) is None
    assert known_order(disputed, exact) is None


def test_timeline_projection_keeps_object_version_and_provenance() -> None:
    projection = TimelineProjectionRef(
        object_id="OBJ-1",
        object_version="v3",
        event_time=_exact("2026-05-01", "prov:event:v3"),
        provenance_refs=("source:doc:v2", "transform:timeline:v1"),
    )

    assert projection.object_version == "v3"
    assert projection.provenance_refs == (
        "source:doc:v2",
        "transform:timeline:v1",
    )


def test_valid_to_without_valid_from_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid_to"):
        TemporalCoordinates(
            event_time=_exact("2026-06-01", "prov:event"),
            source_time=_exact("2026-06-02", "prov:source"),
            knowledge_time=_exact("2026-06-03T08:00:00Z", "prov:knowledge"),
            system_time=_exact("2026-06-03T08:01:00Z", "prov:system"),
            valid_to=_exact("2026-06-30", "prov:valid-to"),
        )


def test_exact_temporal_values_can_be_ordered_deterministically() -> None:
    left = _exact("2026-07-01T10:00:00Z", "prov:left")
    right = _exact("2026-07-01T11:00:00Z", "prov:right")

    assert known_order(left, right) == -1
    assert known_order(right, left) == 1
    assert known_order(left, left) == 0
