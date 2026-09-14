from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from berlin_mobility_twin.domain.models import MobilitySnapshot


class JsonSnapshotStore:
    """Small atomic JSON snapshot store for machine-readable integration output."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, snapshot: MobilitySnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, delete=False
        ) as handle:
            handle.write(snapshot.model_dump_json(indent=2))
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, self.path)

    def read(self) -> MobilitySnapshot | None:
        if not self.path.exists():
            return None
        return MobilitySnapshot.model_validate_json(self.path.read_text(encoding="utf-8"))
