from __future__ import annotations

from functools import lru_cache

from pyproj import Transformer

EXTERNAL_CRS = "EPSG:4326"
BERLIN_METRIC_CRS = "EPSG:25833"


@lru_cache(maxsize=4)
def _transformer(source_crs: str, target_crs: str) -> Transformer:
    return Transformer.from_crs(source_crs, target_crs, always_xy=True)


def project_point(
    point: tuple[float, float],
    *,
    source_crs: str = EXTERNAL_CRS,
    target_crs: str = BERLIN_METRIC_CRS,
) -> tuple[float, float]:
    """Project an x/y point between explicit CRSs using always-xy axis order."""
    x, y = _transformer(source_crs, target_crs).transform(*point)
    return float(x), float(y)


def distance_meters(
    first: tuple[float, float],
    second: tuple[float, float],
    *,
    source_crs: str = EXTERNAL_CRS,
    metric_crs: str = BERLIN_METRIC_CRS,
) -> float:
    """Compute distance after projection to a metric CRS appropriate for Berlin."""
    first_x, first_y = project_point(first, source_crs=source_crs, target_crs=metric_crs)
    second_x, second_y = project_point(second, source_crs=source_crs, target_crs=metric_crs)
    return ((second_x - first_x) ** 2 + (second_y - first_y) ** 2) ** 0.5
