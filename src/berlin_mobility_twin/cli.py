from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import uvicorn

from berlin_mobility_twin.api.app import create_app
from berlin_mobility_twin.api.state import RuntimeState
from berlin_mobility_twin.config import Settings
from berlin_mobility_twin.domain.models import (
    IntegrationMobilitySnapshot,
    NetworkDisruption,
)
from berlin_mobility_twin.ingestion.http_client import MobilityHttpClient
from berlin_mobility_twin.ingestion.sources import SOURCES
from berlin_mobility_twin.ingestion.traffic import inspect_traffic_csv_schema
from berlin_mobility_twin.processing.pipeline import refresh_live_sources
from berlin_mobility_twin.storage.json_store import JsonSnapshotStore


def _write_schema(model: type[Any], path: Path) -> None:
    path.write_text(
        json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def export_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        (IntegrationMobilitySnapshot, output_dir / "mobility-snapshot.schema.json"),
        (NetworkDisruption, output_dir / "network-disruption.schema.json"),
    ]
    for model, path in outputs:
        _write_schema(model, path)
    return [path for _, path in outputs]


def _http_client(settings: Settings) -> MobilityHttpClient:
    return MobilityHttpClient(
        timeout_seconds=settings.http_timeout_seconds,
        user_agent=settings.user_agent,
    )


def _refresh_state(state: RuntimeState, settings: Settings, *, include_static: bool) -> int:
    with _http_client(settings) as client:
        report = refresh_live_sources(
            state,
            client,
            include_static=include_static,
            stale_after_seconds=settings.realtime_stale_after_seconds,
        )
    print(
        json.dumps(
            {
                "succeeded": report.succeeded,
                "failed": report.failed,
                "missing_sources": state.missing_sources,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if report.failed else 0


def _cmd_sources(_: argparse.Namespace, __: Settings) -> int:
    print(json.dumps([source.model_dump(mode="json") for source in SOURCES], indent=2))
    return 0


def _cmd_export_schemas(args: argparse.Namespace, _: Settings) -> int:
    paths = export_schemas(Path(args.output_dir))
    for path in paths:
        print(path)
    return 0


def _cmd_inspect_traffic_csv(args: argparse.Namespace, _: Settings) -> int:
    headers = inspect_traffic_csv_schema(Path(args.path).read_bytes(), delimiter=args.delimiter)
    print(json.dumps(headers, indent=2))
    return 0


def _cmd_refresh(args: argparse.Namespace, settings: Settings) -> int:
    state = RuntimeState()
    return_code = _refresh_state(state, settings, include_static=not args.skip_static)
    snapshot = state.snapshot(datetime.now(UTC))
    if args.snapshot:
        JsonSnapshotStore(Path(args.snapshot)).write(snapshot)
    return return_code


def _cmd_serve(args: argparse.Namespace, settings: Settings) -> int:
    state = RuntimeState()
    if args.live:
        _refresh_state(state, settings, include_static=not args.skip_static)
    app = create_app(state)
    uvicorn.run(app, host=args.host or settings.api_host, port=args.port or settings.api_port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="berlin-mobility-twin",
        description="Berlin Urban Mobility Twin command-line interface",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser("sources", help="Print configured authoritative data sources")
    sources.set_defaults(handler=_cmd_sources)

    schemas = subparsers.add_parser("export-schemas", help="Generate integration JSON schemas")
    schemas.add_argument("--output-dir", default="schemas")
    schemas.set_defaults(handler=_cmd_export_schemas)

    inspect_csv = subparsers.add_parser(
        "inspect-traffic-csv",
        help="Inspect archived traffic CSV headers without guessing field semantics",
    )
    inspect_csv.add_argument("path")
    inspect_csv.add_argument("--delimiter", default=";")
    inspect_csv.set_defaults(handler=_cmd_inspect_traffic_csv)

    refresh = subparsers.add_parser("refresh", help="Retrieve currently supported live/open sources")
    refresh.add_argument("--skip-static", action="store_true")
    refresh.add_argument("--snapshot", help="Optional path for a resulting point-in-time snapshot")
    refresh.set_defaults(handler=_cmd_refresh)

    serve = subparsers.add_parser("serve", help="Run the versioned FastAPI service")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--live", action="store_true", help="Retrieve real sources once before serving")
    serve.add_argument("--skip-static", action="store_true")
    serve.set_defaults(handler=_cmd_serve)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings()
    handler = args.handler
    return int(handler(args, settings))


if __name__ == "__main__":
    raise SystemExit(main())
