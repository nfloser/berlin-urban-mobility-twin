from datetime import UTC

import httpx

from berlin_mobility_twin.ingestion.http_client import MobilityHttpClient


def test_http_client_sends_informative_user_agent_and_records_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("berlin-urban-mobility-twin/")
        return httpx.Response(
            200,
            content=b"payload",
            headers={"ETag": '"abc"', "Content-Type": "application/octet-stream"},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as raw:
        client = MobilityHttpClient(client=raw)
        result = client.fetch("https://example.test/data")

    assert result.content == b"payload"
    assert result.etag == '"abc"'
    assert result.content_type == "application/octet-stream"
    assert result.retrieved_at.tzinfo == UTC


def test_http_client_uses_conditional_etag_and_preserves_not_modified_state() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["If-None-Match"] == '"old"'
        return httpx.Response(304, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as raw:
        result = MobilityHttpClient(client=raw).fetch("https://example.test/data", etag='"old"')

    assert result.not_modified is True
    assert result.content is None
