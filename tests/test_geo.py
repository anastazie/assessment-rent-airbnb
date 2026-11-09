"""Unit tests for amsterdam_rental.geo PostcodeIndex.

Uses a minimal inline GeoJSON fixture rather than the full file,
so the test runs fast and without filesystem dependencies.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from amsterdam_rental.geo import PostcodeIndex

FIXTURE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"pc4_code": "1011"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [4.88, 52.37],
                        [4.90, 52.37],
                        [4.90, 52.38],
                        [4.88, 52.38],
                        [4.88, 52.37],
                    ]
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {"pc4_code": "1012"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [4.90, 52.37],
                        [4.92, 52.37],
                        [4.92, 52.38],
                        [4.90, 52.38],
                        [4.90, 52.37],
                    ]
                ],
            },
        },
    ],
}


def _make_index():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump(FIXTURE_GEOJSON, f)
        path = f.name
    return PostcodeIndex(path)


class TestPostcodeIndex:
    def setup_method(self):
        self.index = _make_index()

    def test_point_in_first_polygon(self):
        """Point inside the first polygon is assigned its PC4 code → '1011'."""
        assert self.index.lookup(4.89, 52.375) == "1011"

    def test_point_in_second_polygon(self):
        """Point inside the second polygon is assigned its PC4 code → '1012'."""
        assert self.index.lookup(4.91, 52.375) == "1012"

    def test_point_outside_all_polygons(self):
        """Point outside all polygons returns None — no zipcode can be assigned."""
        assert self.index.lookup(5.00, 53.00) is None

    def test_none_coordinates(self):
        """Both coordinates None returns None — guards against missing lat/lon rows."""
        assert self.index.lookup(None, None) is None

    def test_partial_none(self):
        """One coordinate None returns None — incomplete coordinates cannot be matched."""
        assert self.index.lookup(4.89, None) is None
