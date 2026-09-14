from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from berlin_mobility_twin.domain.models import DataAvailability, FreshnessStatus
from berlin_mobility_twin.ingestion.gtfs_realtime import parse_feed_message


class Message(SimpleNamespace):
    def HasField(self, name: str) -> bool:  # noqa: N802 - protobuf-compatible API
        return hasattr(self, name) and getattr(self, name) is not None


def event(*, time: int | None = None, delay: int | None = None) -> Message:
    return Message(time=time, delay=delay)


def trip_update(*, relationship: int = 0) -> Message:
    stop_update = Message(
        stop_id="S1",
        arrival=event(time=1_789_380_300, delay=300),
        departure=event(time=1_789_380_330, delay=300),
    )
    return Message(
        trip=Message(trip_id="T1", schedule_relationship=relationship),
        stop_time_update=[stop_update],
    )


def feed(*, timestamp: int, relationship: int = 0) -> Message:
    return Message(
        header=Message(timestamp=timestamp, gtfs_realtime_version="2.0"),
        entity=[Message(id="entity-1", trip_update=trip_update(relationship=relationship))],
    )


def test_parse_gtfs_rt_exposes_delay_and_freshness() -> None:
    retrieved_at = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    feed_timestamp = int((retrieved_at - timedelta(seconds=45)).timestamp())

    result = parse_feed_message(
        feed(timestamp=feed_timestamp),
        retrieved_at=retrieved_at,
        source_url="https://production.gtfsrt.vbb.de/data",
        stale_after_seconds=120,
    )

    assert result.freshness is FreshnessStatus.FRESH
    assert result.feed_age_seconds == 45
    assert result.observations[0].availability is DataAvailability.REALTIME
    assert result.observations[0].delay_seconds == 300
    assert result.observations[0].predicted_arrival is not None


def test_parse_gtfs_rt_marks_old_feed_stale() -> None:
    retrieved_at = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    feed_timestamp = int((retrieved_at - timedelta(minutes=10)).timestamp())

    result = parse_feed_message(
        feed(timestamp=feed_timestamp),
        retrieved_at=retrieved_at,
        source_url="https://production.gtfsrt.vbb.de/data",
        stale_after_seconds=120,
    )

    assert result.freshness is FreshnessStatus.STALE
    assert "feed is stale" in result.warnings[0]


def test_cancelled_trip_is_not_inferred_from_absence_but_from_relationship() -> None:
    retrieved_at = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    feed_timestamp = int(retrieved_at.timestamp())

    result = parse_feed_message(
        feed(timestamp=feed_timestamp, relationship=3),
        retrieved_at=retrieved_at,
        source_url="https://production.gtfsrt.vbb.de/data",
    )

    assert result.observations[0].cancelled is True
