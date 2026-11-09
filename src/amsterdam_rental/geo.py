"""
Point-in-polygon lookup for backfilling missing Airbnb zipcodes.

Uses the post_codes.geojson dataset (474 PC4 polygons covering greater Amsterdam)
to assign a 4-digit postcode to any listing that has lat/lon but no zipcode.
Avoids a Spark dependency — runs as a broadcast lookup on the driver.
"""

import json
from typing import Optional


def _point_in_ring(x: float, y: float, ring: list) -> bool:
    """Ray-casting test for a single linear ring of [lon, lat] coordinates."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_polygon(lon: float, lat: float, polygon_coords: list) -> bool:
    """
    Test whether (lon, lat) is inside a GeoJSON polygon.

    polygon_coords[0] is the outer ring; any further rings are holes. A point in a
    hole is outside the polygon — in the PC4 data those holes are usually other
    postcodes enclosed by this one, so ignoring them mis-assigns the enclave.
    """
    outer, *holes = polygon_coords
    if not _point_in_ring(lon, lat, outer):
        return False
    return not any(_point_in_ring(lon, lat, hole) for hole in holes)


def _point_in_feature(lon: float, lat: float, feature: dict) -> bool:
    geometry = feature["geometry"]
    if geometry["type"] == "Polygon":
        return _point_in_polygon(lon, lat, geometry["coordinates"])
    elif geometry["type"] == "MultiPolygon":
        return any(_point_in_polygon(lon, lat, poly) for poly in geometry["coordinates"])
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
        self._municipality = {
            feat["properties"]["pc4_code"]: feat["properties"].get("gem_name")
            for feat in self._features
        }

    def lookup(self, lon: float, lat: float) -> Optional[str]:
        """Return the PC4 code for the given coordinates, or None if not found."""
        if lon is None or lat is None:
            return None
        for feature in self._features:
            if _point_in_feature(lon, lat, feature):
                return feature["properties"]["pc4_code"]
        return None

    def municipality(self, pc4: Optional[str]) -> Optional[str]:
        """Return the municipality (gem_name) a PC4 belongs to, or None if unknown."""
        return self._municipality.get(pc4)

    def resolve_pc4(
        self,
        zipcode: Optional[str],
        lon: Optional[float],
        lat: Optional[float],
        municipality: str = "Amsterdam",
    ) -> Optional[str]:
        """
        Return a trustworthy PC4 inside `municipality`, or None if there is none.

        1. Keep the stated zipcode if it is a known PC4 in the municipality. Stated
           zipcodes win over coordinates because Airbnb jitters listing coordinates
           by up to ~150 m, which often lands them in the neighbouring PC4.
        2. Otherwise (missing, typo, placeholder, or outside the municipality),
           fall back to the PC4 the coordinates fall in — if that is in the
           municipality.
        3. Otherwise return None: the listing is outside the municipality.
        """
        if self.municipality(zipcode) == municipality:
            return zipcode
        from_coords = self.lookup(lon, lat)
        if self.municipality(from_coords) == municipality:
            return from_coords
        return None
