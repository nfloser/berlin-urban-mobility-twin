from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

DEFAULT_USER_AGENT = (
    "berlin-urban-mobility-twin/0.1 "
    "(+https://github.com/nfloser/berlin-urban-mobility-twin)"
)


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int
    retrieved_at: datetime
    content: bytes | None
    content_type: str | None
    etag: str | None
    not_modified: bool = False


class MobilityHttpClient:
    """HTTP retrieval adapter with explicit timeout, redirects, metadata and ETag support."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._owned_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        self.user_agent = user_agent

    def close(self) -> None:
        if self._owned_client:
            self._client.close()

    def __enter__(self) -> MobilityHttpClient:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def fetch(self, url: str, *, etag: str | None = None) -> FetchResult:
        headers = {"User-Agent": self.user_agent, "Accept": "*/*"}
        if etag is not None:
            headers["If-None-Match"] = etag
        response = self._client.get(url, headers=headers)
        retrieved_at = datetime.now(UTC)
        if response.status_code == 304:
            return FetchResult(
                url=str(response.url),
                status_code=304,
                retrieved_at=retrieved_at,
                content=None,
                content_type=response.headers.get("Content-Type"),
                etag=response.headers.get("ETag") or etag,
                not_modified=True,
            )
        response.raise_for_status()
        return FetchResult(
            url=str(response.url),
            status_code=response.status_code,
            retrieved_at=retrieved_at,
            content=response.content,
            content_type=response.headers.get("Content-Type"),
            etag=response.headers.get("ETag"),
        )
