"""Unit tests for amsterdam_rental.plotting (skipped if matplotlib is not installed)."""

import os
import sys

import pytest

pytest.importorskip("matplotlib")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from amsterdam_rental.plotting import render_potential_map


def _square(pc4, x0, gem="Amsterdam"):
    ring = [[x0, 52.3], [x0 + 0.01, 52.3], [x0 + 0.01, 52.31], [x0, 52.31], [x0, 52.3]]
    return {
        "type": "Feature",
        "properties": {"pc4_code": pc4, "gem_name": gem},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


FEATURES = [
    _square("1011", 4.80),
    _square("1012", 4.81),
    _square("1013", 4.82),
    _square("1014", 4.83),
    _square("2000", 4.84, gem="Haarlem"),
]


def test_writes_png_and_counts_tiers(tmp_path):
    """Writes a PNG; Amsterdam postcodes are counted per score, missing ones as 0."""
    out = tmp_path / "figs" / "map.png"
    counts = render_potential_map(FEATURES, {"1011": 3, "1012": 2, "1013": 1}, str(out))
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert counts == {3: 1, 2: 1, 1: 1, 0: 1}  # 1014 unscored; Haarlem not drawn


def test_municipality_none_draws_everything(tmp_path):
    """municipality=None draws every feature, including other municipalities."""
    counts = render_potential_map(FEATURES, {}, str(tmp_path / "m.png"), municipality=None)
    assert counts[0] == len(FEATURES)
