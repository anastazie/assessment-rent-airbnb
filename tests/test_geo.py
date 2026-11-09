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

    def test_point_on_shared_edge_gets_a_code(self):
        """Point exactly on the lon=4.90 edge shared by both polygons still gets a code.

        Listings on a postcode boundary must not fall through to None; which side
        wins is an implementation detail of the ray-casting tie-break.
        """
        assert self.index.lookup(4.90, 52.375) in ("1011", "1012")


MULTIPOLYGON_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"pc4_code": "1013"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [4.80, 52.30],
                            [4.82, 52.30],
                            [4.82, 52.32],
                            [4.80, 52.32],
                            [4.80, 52.30],
                        ]
                    ],
                    [
                        [
                            [4.85, 52.30],
                            [4.87, 52.30],
                            [4.87, 52.32],
                            [4.85, 52.32],
                            [4.85, 52.30],
                        ]
                    ],
                ],
            },
        }
    ],
}


class TestPostcodeIndexMultiPolygon:
    def setup_method(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
            json.dump(MULTIPOLYGON_GEOJSON, f)
            path = f.name
        self.index = PostcodeIndex(path)

    def test_point_in_first_part(self):
        """Point inside the first part of a MultiPolygon gets its PC4 code."""
        assert self.index.lookup(4.81, 52.31) == "1013"

    def test_point_in_second_part(self):
        """Point inside the second part is matched too — not only the first ring is checked."""
        assert self.index.lookup(4.86, 52.31) == "1013"

    def test_point_between_parts(self):
        """Point in the gap between the two parts is outside the feature → None."""
        assert self.index.lookup(4.835, 52.31) is None


# Postcode 1014 is a 0.04°×0.04° square with a hole in the middle; postcode 1015
# fills exactly that hole (an enclave). 1014 is listed first, so a lookup that
# ignored holes would wrongly return '1014' for points inside the enclave.
HOLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"pc4_code": "1014"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[4.80, 52.30], [4.84, 52.30], [4.84, 52.34], [4.80, 52.34], [4.80, 52.30]],
                    [[4.81, 52.31], [4.81, 52.33], [4.83, 52.33], [4.83, 52.31], [4.81, 52.31]],
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {"pc4_code": "1015"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[4.81, 52.31], [4.83, 52.31], [4.83, 52.33], [4.81, 52.33], [4.81, 52.31]],
                ],
            },
        },
    ],
}


class TestPostcodeIndexHoles:
    def setup_method(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
            json.dump(HOLE_GEOJSON, f)
            path = f.name
        self.index = PostcodeIndex(path)

    def test_point_in_ring_area_gets_outer_code(self):
        """Point between the outer boundary and the hole belongs to the outer postcode."""
        assert self.index.lookup(4.805, 52.32) == "1014"

    def test_point_in_hole_gets_enclave_code(self):
        """Point inside the hole belongs to the enclave postcode, not the surrounding one."""
        assert self.index.lookup(4.82, 52.32) == "1015"


# Two adjacent PC4s in Amsterdam plus one in a neighbouring municipality, used to
# test zipcode validation against the municipality filter.
MUNICIPALITY_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"pc4_code": "1071", "gem_name": "Amsterdam"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[4.86, 52.35], [4.88, 52.35], [4.88, 52.36], [4.86, 52.36], [4.86, 52.35]]
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {"pc4_code": "1072", "gem_name": "Amsterdam"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[4.88, 52.35], [4.90, 52.35], [4.90, 52.36], [4.88, 52.36], [4.88, 52.35]]
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {"pc4_code": "1111", "gem_name": "Diemen"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[4.95, 52.33], [4.97, 52.33], [4.97, 52.35], [4.95, 52.35], [4.95, 52.33]]
                ],
            },
        },
    ],
}

IN_1071 = (4.87, 52.355)
IN_DIEMEN = (4.96, 52.34)
NOWHERE = (6.00, 53.00)


class TestResolvePc4:
    def setup_method(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
            json.dump(MUNICIPALITY_GEOJSON, f)
            path = f.name
        self.index = PostcodeIndex(path)

    def test_municipality_lookup(self):
        """municipality() maps a PC4 to its gem_name, and unknown codes to None."""
        assert self.index.municipality("1111") == "Diemen"
        assert self.index.municipality("1234") is None
        assert self.index.municipality(None) is None

    def test_valid_zipcode_wins_over_coordinates(self):
        """A stated Amsterdam PC4 is kept even when jittered coords fall in the neighbour."""
        assert self.index.resolve_pc4("1072", *IN_1071) == "1072"

    def test_missing_zipcode_backfilled_from_coordinates(self):
        """No stated zipcode → PC4 from coordinates."""
        assert self.index.resolve_pc4(None, *IN_1071) == "1071"

    def test_zipcode_outside_municipality_replaced_by_coordinates(self):
        """Typo zipcode in another municipality (e.g. '1212AB' on an Oud-Zuid listing) → coords win."""
        assert self.index.resolve_pc4("1111", *IN_1071) == "1071"

    def test_unknown_zipcode_replaced_by_coordinates(self):
        """Placeholder zipcode not in the geojson (e.g. '1234 AB') → coords win."""
        assert self.index.resolve_pc4("1234", *IN_1071) == "1071"

    def test_listing_outside_municipality_dropped(self):
        """Zipcode and coordinates both outside Amsterdam → None (listing is filtered out)."""
        assert self.index.resolve_pc4("1111", *IN_DIEMEN) is None

    def test_coordinates_outside_all_polygons_dropped(self):
        """Invalid zipcode and coords outside every polygon → None."""
        assert self.index.resolve_pc4("1234", *NOWHERE) is None

    def test_no_zipcode_no_coordinates(self):
        """Nothing to go on → None."""
        assert self.index.resolve_pc4(None, None, None) is None

    def test_other_municipality_parameter(self):
        """The municipality is configurable — a Diemen listing resolves when asked for Diemen."""
        assert self.index.resolve_pc4(None, *IN_DIEMEN, municipality="Diemen") == "1111"
