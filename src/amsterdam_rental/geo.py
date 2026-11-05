"""
Point-in-polygon lookup for backfilling missing Airbnb zipcodes.

Uses the post_codes.geojson dataset (474 PC4 polygons covering greater Amsterdam)
to assign a 4-digit postcode to any listing that has lat/lon but no zipcode.
Avoids a Spark dependency — runs as a broadcast lookup on the driver.
"""

import json
from typing import Optional


def _point_in_polygon(lon: float, lat: float, polygon_coords: list) -> bool:
    """
    Ray-casting algorithm to test whether (lon, lat) is inside a polygon.
    Works for GeoJSON coordinate order [longitude, latitude].
    """
    x, y = lon, lat
    inside = False
    coords = polygon_coords[0]  # outer ring only
    n = len(coords)
    j = n - 1
    for i in range(n):
        xi, yi = coords[i]
        xj, yj = coords[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_feature(lon: float, lat: float, feature: dict) -> bool:
    geometry = feature["geometry"]
    if geometry["type"] == "Polygon":
        return _point_in_polygon(lon, lat, geometry["coordinates"])
    elif geometry["type"] == "MultiPolygon":
        return any(
            _point_in_polygon(lon, lat, poly)
            for poly in geometry["coordinates"]
        )
    return False


class PostcodeIndex:
    """
    Loads the post_codes.geojson once and answers lookup(lon, lat) -> pc4_code.

    Intended to be instantiated once per driver/executor and reused across rows.
    On Databricks, broadcast as a closure variable in a UDF.
    """

    def __init__(self, geojson_path: str):
        with open(geojson_path) as f:
            data = json.load(f)
        self._features = data["features"]

    def lookup(self, lon: float, lat: float) -> Optional[str]:
        """Return the PC4 code for the given coordinates, or None if not found."""
        if lon is None or lat is None:
            return None
        for feature in self._features:
            if _point_in_feature(lon, lat, feature):
                return feature["properties"]["pc4_code"]
        return None
