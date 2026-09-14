from __future__ import annotations

import argparse
import json

from berlin_mobility_twin.api.state import RuntimeState
from berlin_mobility_twin.config import Settings
from berlin_mobility_twin.ingestion.http_client import MobilityHttpClient
from berlin_mobility_twin.processing.pipeline import refresh_live_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test real authoritative mobility sources.")
    parser.add_argument(
        "--include-static",
        action="store_true",
        help="Also download and validate the larger VBB static GTFS archive.",
    )
    args = parser.parse_args()
    settings = Settings()
    state = RuntimeState()
    with MobilityHttpClient(
        timeout_seconds=settings.http_timeout_seconds,
        user_agent=settings.user_agent,
    ) as client:
        report = refresh_live_sources(
            state,
            client,
            include_static=args.include_static,
            stale_after_seconds=settings.realtime_stale_after_seconds,
        )
    result = {
        "succeeded": report.succeeded,
        "failed": report.failed,
        "counts": {
            "stops": len(state.stops),
            "realtime_observations": len(state.transit_observations),
            "detectors": len(state.traffic_detectors),
            "disruptions": len(state.disruptions),
        },
        "synthetic_production_data": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if report.succeeded else 2


if __name__ == "__main__":
    raise SystemExit(main())
