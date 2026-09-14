from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class LocalTimeError(ValueError):
    """Base error for source-local timestamps that cannot be interpreted safely."""


class NonexistentLocalTime(LocalTimeError):
    """Raised for a local timestamp inside a daylight-saving spring-forward gap."""


class AmbiguousLocalTime(LocalTimeError):
    """Raised for a local timestamp that occurs twice during a DST overlap."""


def _candidate(naive: datetime, timezone: ZoneInfo, fold: int) -> datetime | None:
    aware = naive.replace(tzinfo=timezone, fold=fold)
    utc_value = aware.astimezone(UTC)
    round_trip = utc_value.astimezone(timezone)
    if round_trip.replace(tzinfo=None) != naive:
        return None
    opposite = naive.replace(tzinfo=timezone, fold=1 - fold)
    if round_trip.fold != fold and aware.utcoffset() != opposite.utcoffset():
        return None
    return utc_value


def local_to_utc(value: datetime, timezone_name: str, *, fold: int | None = None) -> datetime:
    """Resolve a source-local timestamp without silently guessing at DST transitions."""
    if value.tzinfo is not None and value.utcoffset() is not None:
        if fold is not None:
            raise ValueError("fold is only valid for naive local timestamps")
        return value.astimezone(UTC)
    if fold not in (None, 0, 1):
        raise ValueError("fold must be 0, 1, or None")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone {timezone_name!r}") from exc

    first = _candidate(value, timezone, 0)
    second = _candidate(value, timezone, 1)
    candidates = [candidate for candidate in (first, second) if candidate is not None]
    unique = set(candidates)
    if not unique:
        raise NonexistentLocalTime(
            f"{value.isoformat()} does not exist in timezone {timezone_name}"
        )
    if len(unique) == 1:
        return next(iter(unique))
    if fold is None:
        raise AmbiguousLocalTime(
            f"{value.isoformat()} occurs twice in timezone {timezone_name}; "
            "specify fold=0 or fold=1"
        )
    selected = first if fold == 0 else second
    if selected is None:
        raise NonexistentLocalTime(
            f"{value.isoformat()} with fold={fold} is invalid in timezone {timezone_name}"
        )
    return selected
