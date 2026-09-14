from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class DataAvailability(StrEnum):
    SCHEDULED = "scheduled"
    OBSERVED = "observed"
    REALTIME = "realtime"
    HISTORICAL = "historical"
    MISSING = "missing"
    UNKNOWN = "unknown"


class QualitySeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DataQuality(BaseModel):
    model_config = ConfigDict(frozen=True)

    warnings: list[str] = Field(default_factory=list)
    severity: QualitySeverity = QualitySeverity.INFO
    is_valid: bool = True


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    dataset_title: str = Field(min_length=1)
    retrieved_at: AwareDatetime
    observation_at: AwareDatetime | None = None
    source_url: str = Field(min_length=1)
    source_metadata_url: str | None = None
    licence: str = Field(min_length=1)
    schema_version: str | None = None
    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN
    quality_warnings: list[str] = Field(default_factory=list)


class DataSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    provider: str
    dataset_title: str
    source_url: str
    licence: str
    update_frequency: str | None = None
    temporal_coverage: str | None = None
    spatial_coverage: str | None = None
    limitations: list[str] = Field(default_factory=list)


class TransitStop(BaseModel):
    model_config = ConfigDict(frozen=True)

    stop_id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    parent_station: str | None = None


class TransitRoute(BaseModel):
    model_config = ConfigDict(frozen=True)

    route_id: str
    agency_id: str | None = None
    short_name: str | None = None
    long_name: str | None = None
    route_type: int


class TransitTrip(BaseModel):
    model_config = ConfigDict(frozen=True)

    trip_id: str
    route_id: str
    service_id: str
    headsign: str | None = None
    direction_id: int | None = Field(default=None, ge=0, le=1)


class TransitObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    trip_id: str
    stop_id: str | None = None
    observed_at: AwareDatetime
    scheduled_arrival: AwareDatetime | None = None
    predicted_arrival: AwareDatetime | None = None
    delay_seconds: int | None = None
    cancelled: bool | None = None
    availability: DataAvailability
    quality: DataQuality
    provenance: Provenance


class TrafficDetector(BaseModel):
    model_config = ConfigDict(frozen=True)

    detector_id: str
    road: str | None = None
    location_description: str | None = None
    direction: str | None = None
    lane: str | None = None
    start_of_operation: date | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    crs: str = "EPSG:4326"
    provenance: Provenance | None = None


class TrafficObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    detector_id: str
    observed_at: AwareDatetime
    vehicle_count: int | None = Field(default=None, ge=0)
    heavy_vehicle_count: int | None = Field(default=None, ge=0)
    speed_kmh: float | None = Field(default=None, ge=0, le=250)
    availability: DataAvailability
    quality: DataQuality
    provenance: Provenance
    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_composition(self) -> TrafficObservation:
        if (
            self.vehicle_count is not None
            and self.heavy_vehicle_count is not None
            and self.heavy_vehicle_count > self.vehicle_count
        ):
            raise ValueError("heavy_vehicle_count cannot exceed vehicle_count")
        return self


class DisruptionCategory(StrEnum):
    CONSTRUCTION = "construction"
    CLOSURE = "closure"
    INCIDENT = "incident"
    EVENT = "event"
    OTHER = "other"
    UNKNOWN = "unknown"


class Disruption(BaseModel):
    model_config = ConfigDict(frozen=True)

    disruption_id: str
    category: DisruptionCategory
    description: str | None = None
    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    geometry: dict[str, Any]
    crs: str = "EPSG:4326"
    affected_network_segment: str | None = None
    network_match_confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: Provenance
    quality: DataQuality = Field(default_factory=DataQuality)

    @model_validator(mode="after")
    def validate_interval(self) -> Disruption:
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must not precede valid_from")
        return self


class NetworkDisruption(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: AwareDatetime
    geometry: dict[str, Any]
    category: DisruptionCategory
    observation_status: DataAvailability
    provenance: Provenance
    freshness: FreshnessStatus
    quality: DataQuality
    confidence: float | None = Field(default=None, ge=0, le=1)


class MobilitySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: AwareDatetime
    transit: list[TransitObservation] = Field(default_factory=list)
    traffic: list[TrafficObservation] = Field(default_factory=list)
    disruptions: list[Disruption] = Field(default_factory=list)
    source_status: dict[str, FreshnessStatus] = Field(default_factory=dict)
    missing_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
