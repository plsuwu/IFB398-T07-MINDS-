import re
from functools import lru_cache

from pyproj import Transformer

_EPSG_MAP = {
    ("MGA94", 54): 28354,
    ("MGA94", 55): 28355,
    ("MGA94", 56): 28356,
    ("AMG84", 54): 20354,
    ("AMG84", 55): 20355,
    ("AMG84", 56): 20356,
}

_ZONE_RE = re.compile(r'zone\s*(\d+)', re.IGNORECASE)
_CRS_RE  = re.compile(r'(MGA94|AMG84)',  re.IGNORECASE)


def parse_grid_epsg(grid_str: str) -> int | None:
    """Parse a GRID column string into an EPSG integer code.

    Examples:
        'MGA94 zone 56'  -> 28356
        'AMG84 zone 55'  -> 20355
        ''               -> None
    """
    if not grid_str:
        return None
    zone_match = _ZONE_RE.search(grid_str)
    crs_match  = _CRS_RE.search(grid_str)
    if not zone_match or not crs_match:
        return None
    zone = int(zone_match.group(1))
    crs  = crs_match.group(1).upper()
    return _EPSG_MAP.get((crs, zone))


@lru_cache(maxsize=16)
def _get_transformer(source_epsg: int) -> Transformer:
    return Transformer.from_crs(source_epsg, 4326, always_xy=True)


def projected_to_wgs84(easting: float, northing: float, source_epsg: int) -> tuple[float, float]:
    """Transform projected coordinates to WGS84 geographic coordinates.

    Args:
        easting: X coordinate in source CRS (metres).
        northing: Y coordinate in source CRS (metres).
        source_epsg: EPSG code of the source CRS (e.g. 28356).

    Returns:
        (longitude, latitude) as floats in WGS84.
    """
    transformer = _get_transformer(source_epsg)
    lon, lat = transformer.transform(easting, northing)
    return lon, lat
