"""
Pure transformation functions for the Amsterdam rental pipeline.

Kept as plain Python (no Spark dependency) so they can be unit tested
without a cluster. The notebooks import these and apply them via UDFs
or pandas_udf where needed.
"""

import re
from typing import Optional


def parse_eur(raw) -> Optional[float]:
    """Extract a numeric value from a raw euro string like '\\n€ 750\\n'."""
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    if not raw:
        return None
    cleaned = re.sub(r"[€\s]", "", str(raw)).replace(",", "")
    m = re.search(r"[\d.]+", cleaned)
    return float(m.group()) if m else None


def parse_sqm(raw) -> Optional[int]:
    """Extract integer area from a string like '14 m2' or '14m²'."""
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    m = re.search(r"(\d+)", str(raw))
    return int(m.group()) if m else None


def normalise_zipcode(raw) -> Optional[str]:
    """
    Return a 4-digit zipcode string from values like '1053', '1053.0', or '1053AB'.

    Airbnb stores zipcodes inconsistently — sometimes as floats, sometimes with
    letter suffixes. We only use the numeric PC4 portion for joining.
    """
    if not raw or (isinstance(raw, float) and raw != raw):  # NaN check
        return None
    s = str(raw).strip().split(".")[0]  # strip float suffix e.g. '1053.0' -> '1053'
    s = re.sub(r"[^0-9]", "", s)  # strip letter suffix e.g. '1053AB' -> '1053'
    return s if len(s) == 4 else None


def flatten_list_field(value) -> Optional[str]:
    """Unwrap single-element list fields that appear in the Kamernet JSON."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def cap_outliers_iqr(value: float, q1: float, q3: float, multiplier: float = 1.5) -> float:
    """Cap a value at the IQR upper fence. Returns the original value if within range."""
    upper_fence = q3 + multiplier * (q3 - q1)
    return min(value, upper_fence)


def airbnb_monthly_revenue(nightly_price: float, occupancy_rate: float = 0.66) -> float:
    """
    Estimate monthly Airbnb revenue from a nightly price.

    Assumes 66% annual occupancy per AirDNA Amsterdam market data.
    Formula: nightly × 365 × occupancy / 12
    """
    return nightly_price * 365 * occupancy_rate / 12
