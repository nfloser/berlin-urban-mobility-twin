from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO, TextIOWrapper
from zipfile import BadZipFile, ZipFile

from berlin_mobility_twin.domain.models import TransitRoute, TransitStop, TransitTrip


class GtfsError(ValueError):
    """Base error for malformed GTFS schedule data."""


class GtfsIntegrityError(GtfsError):
    """Raised when GTFS entity references are inconsistent."""


@dataclass(frozen=True)
class GtfsStopTime:
    trip_id: str
    stop_id: str
    stop_sequence: int
    arrival_seconds: int | None
    departure_seconds: int | None


@dataclass(frozen=True)
class ServiceCalendar:
    service_id: str
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    start_date: date
    end_date: date


@dataclass(frozen=True)
class CalendarException:
    service_id: str
    date: date
    exception_type: int


@dataclass
class IngestionDiagnostics:
    rows_read: int = 0
    invalid_rows: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GtfsDataset:
    stops: dict[str, TransitStop]
    routes: dict[str, TransitRoute]
    trips: dict[str, TransitTrip]
    stop_times: list[GtfsStopTime]
    calendar: dict[str, ServiceCalendar]
    calendar_dates: list[CalendarException]
    diagnostics: IngestionDiagnostics


def parse_gtfs_time(value: str) -> int:
    """Parse a GTFS service-day HH:MM:SS value into seconds since service-day start."""
    parts = value.split(":")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid GTFS time: {value!r}")
    hours, minutes, seconds = map(int, parts)
    if hours < 0 or minutes not in range(60) or seconds not in range(60):
        raise ValueError(f"invalid GTFS time: {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def _optional_gtfs_time(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return parse_gtfs_time(value)


def _date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def _rows(archive: ZipFile, name: str, *, required: bool = True) -> list[dict[str, str]]:
    try:
        raw = archive.open(name)
    except KeyError:
        if required:
            raise GtfsError(f"required GTFS table missing: {name}") from None
        return []
    with raw, TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
        return list(csv.DictReader(text))


def parse_gtfs_zip(payload: bytes, *, strict: bool = True) -> GtfsDataset:
    """Parse the GTFS tables needed by the twin and validate cross-table references."""
    diagnostics = IngestionDiagnostics()
    try:
        archive = ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise GtfsError("payload is not a valid GTFS ZIP archive") from exc

    with archive:
        stop_rows = _rows(archive, "stops.txt")
        route_rows = _rows(archive, "routes.txt")
        trip_rows = _rows(archive, "trips.txt")
        stop_time_rows = _rows(archive, "stop_times.txt")
        calendar_rows = _rows(archive, "calendar.txt", required=False)
        calendar_date_rows = _rows(archive, "calendar_dates.txt", required=False)

    if not calendar_rows and not calendar_date_rows:
        raise GtfsError("GTFS must contain calendar.txt and/or calendar_dates.txt")

    stops: dict[str, TransitStop] = {}
    routes: dict[str, TransitRoute] = {}
    trips: dict[str, TransitTrip] = {}
    stop_times: list[GtfsStopTime] = []
    calendars: dict[str, ServiceCalendar] = {}
    calendar_dates: list[CalendarException] = []

    def invalid(message: str, exc: Exception | None = None) -> None:
        diagnostics.invalid_rows += 1
        diagnostics.warnings.append(message)
        if strict:
            if exc is None:
                raise GtfsError(message)
            raise GtfsError(message) from exc

    for row in stop_rows:
        diagnostics.rows_read += 1
        try:
            stop = TransitStop(
                stop_id=row["stop_id"],
                name=row["stop_name"],
                latitude=float(row["stop_lat"]),
                longitude=float(row["stop_lon"]),
                parent_station=row.get("parent_station") or None,
            )
            stops[stop.stop_id] = stop
        except (KeyError, TypeError, ValueError) as exc:
            invalid(f"invalid stops.txt row: {row!r}", exc)

    for row in route_rows:
        diagnostics.rows_read += 1
        try:
            route = TransitRoute(
                route_id=row["route_id"],
                agency_id=row.get("agency_id") or None,
                short_name=row.get("route_short_name") or None,
                long_name=row.get("route_long_name") or None,
                route_type=int(row["route_type"]),
            )
            routes[route.route_id] = route
        except (KeyError, TypeError, ValueError) as exc:
            invalid(f"invalid routes.txt row: {row!r}", exc)

    for row in calendar_rows:
        diagnostics.rows_read += 1
        try:
            calendar = ServiceCalendar(
                service_id=row["service_id"],
                monday=row["monday"] == "1",
                tuesday=row["tuesday"] == "1",
                wednesday=row["wednesday"] == "1",
                thursday=row["thursday"] == "1",
                friday=row["friday"] == "1",
                saturday=row["saturday"] == "1",
                sunday=row["sunday"] == "1",
                start_date=_date(row["start_date"]),
                end_date=_date(row["end_date"]),
            )
            calendars[calendar.service_id] = calendar
        except (KeyError, TypeError, ValueError) as exc:
            invalid(f"invalid calendar.txt row: {row!r}", exc)

    for row in calendar_date_rows:
        diagnostics.rows_read += 1
        try:
            exception = CalendarException(
                service_id=row["service_id"],
                date=_date(row["date"]),
                exception_type=int(row["exception_type"]),
            )
            if exception.exception_type not in (1, 2):
                raise ValueError("exception_type must be 1 or 2")
            calendar_dates.append(exception)
        except (KeyError, TypeError, ValueError) as exc:
            invalid(f"invalid calendar_dates.txt row: {row!r}", exc)

    valid_services = set(calendars) | {item.service_id for item in calendar_dates}
    for row in trip_rows:
        diagnostics.rows_read += 1
        try:
            route_id = row["route_id"]
            service_id = row["service_id"]
            if route_id not in routes:
                raise GtfsIntegrityError(f"trip references unknown route_id {route_id!r}")
            if valid_services and service_id not in valid_services:
                raise GtfsIntegrityError(f"trip references unknown service_id {service_id!r}")
            direction_raw = row.get("direction_id") or None
            trip = TransitTrip(
                trip_id=row["trip_id"],
                route_id=route_id,
                service_id=service_id,
                headsign=row.get("trip_headsign") or None,
                direction_id=int(direction_raw) if direction_raw is not None else None,
            )
            trips[trip.trip_id] = trip
        except GtfsIntegrityError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            invalid(f"invalid trips.txt row: {row!r}", exc)

    for row in stop_time_rows:
        diagnostics.rows_read += 1
        try:
            trip_id = row["trip_id"]
            stop_id = row["stop_id"]
            if trip_id not in trips:
                raise GtfsIntegrityError(f"stop_time references unknown trip_id {trip_id!r}")
            if stop_id not in stops:
                raise GtfsIntegrityError(f"stop_time references unknown stop_id {stop_id!r}")
            stop_times.append(
                GtfsStopTime(
                    trip_id=trip_id,
                    stop_id=stop_id,
                    stop_sequence=int(row["stop_sequence"]),
                    arrival_seconds=_optional_gtfs_time(row.get("arrival_time")),
                    departure_seconds=_optional_gtfs_time(row.get("departure_time")),
                )
            )
        except GtfsIntegrityError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            invalid(f"invalid stop_times.txt row: {row!r}", exc)

    return GtfsDataset(
        stops=stops,
        routes=routes,
        trips=trips,
        stop_times=stop_times,
        calendar=calendars,
        calendar_dates=calendar_dates,
        diagnostics=diagnostics,
    )
