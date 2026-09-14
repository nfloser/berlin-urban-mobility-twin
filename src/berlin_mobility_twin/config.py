from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from berlin_mobility_twin.ingestion.http_client import DEFAULT_USER_AGENT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOBILITY_", env_file=".env", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    http_timeout_seconds: float = Field(default=30.0, gt=0)
    user_agent: str = DEFAULT_USER_AGENT
    realtime_stale_after_seconds: int = Field(default=120, ge=1)
