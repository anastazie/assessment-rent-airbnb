"""
Static choropleth of investment potential per PC4 postcode.

Plain matplotlib (no geopandas) so it runs unchanged on Databricks serverless and
locally. Called by notebooks/04_report.ipynb; the PNG it writes is the image shown
in the README.
"""

import math
import os
from collections.abc import Mapping
from typing import Optional

# Ordinal single-hue ramp (light -> dark = low -> high potential)
TIER_STYLE = {
    3: ("High potential", "#104281"),
    2: ("Medium potential", "#2a78d6"),
    1: ("Low potential", "#86b6ef"),
    0: ("Not enough data (< 5 listings)", "#e4e3df"),
}
SURFACE = "#ffffff"
INK = "#1f1f1e"
INK_MUTED = "#6b6a66"


def _rings(geometry: dict):
    """Yield the outer ring of every polygon part (holes are separate PC4 features)."""
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"][0]
    elif geometry["type"] == "MultiPolygon":
        for poly in geometry["coordinates"]:
            yield poly[0]


def _ring_area(ring: list) -> float:
    """Unsigned shoelace area in degrees² (only used for draw order)."""
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]))) / 2


def render_potential_map(
    features: list,
    scores: Mapping[str, int],
    out_path: str,
    municipality: Optional[str] = "Amsterdam",
    subtitle: str = "",
) -> dict:
    """Draw every PC4 in ``municipality`` coloured by its potential score and save a PNG.

    ``scores`` maps pc4 -> 0..3 (0 = not scored). Postcodes without a score are drawn
    as "not enough data". Returns {score: postcode count} as drawn.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Polygon

    selected = [
        f
        for f in features
        if municipality is None or f["properties"].get("gem_name") == municipality
    ]
    # Larger postcodes first so enclaves are drawn on top of the postcode around them
    selected.sort(key=lambda f: -sum(_ring_area(r) for r in _rings(f["geometry"])))

    fig, ax = plt.subplots(figsize=(9, 8), dpi=150, facecolor=SURFACE)
    counts = {score: 0 for score in TIER_STYLE}
    lats = []
    for feat in selected:
        score = int(scores.get(feat["properties"]["pc4_code"], 0) or 0)
        counts[score] += 1
        color = TIER_STYLE[score][1]
        for ring in _rings(feat["geometry"]):
            # 0.8pt surface-coloured edge = visible gap between neighbouring fills
            ax.add_patch(Polygon(ring, closed=True, facecolor=color, edgecolor=SURFACE, lw=0.8))
            lats.extend(pt[1] for pt in ring)

    ax.autoscale_view()
    # Equirectangular correction so Amsterdam is not stretched east-west
    ax.set_aspect(1 / math.cos(math.radians(sum(lats) / max(len(lats), 1))))
    ax.set_axis_off()

    handles = [
        Patch(facecolor=color, edgecolor="none", label=f"{label}  ({counts[s]})")
        for s, (label, color) in TIER_STYLE.items()
    ]
    ax.legend(
        handles=handles,
        loc="lower left",
        frameon=False,
        fontsize=9,
        labelcolor=INK,
        title="Postcodes (PC4)",
        title_fontsize=9,
        alignment="left",
    )
    fig.suptitle(
        "Investment potential by Amsterdam postcode",
        x=0.06,
        y=0.97,
        ha="left",
        fontsize=14,
        color=INK,
        fontweight="bold",
    )
    if subtitle:
        fig.text(0.06, 0.925, subtitle, ha="left", va="top", fontsize=9, color=INK_MUTED)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return counts
