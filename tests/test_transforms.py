"""Unit tests for amsterdam_rental.transforms.

Pure-function tests — no Spark dependency required.
Run with: pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from amsterdam_rental.transforms import (
    airbnb_monthly_revenue,
    flatten_list_field,
    normalise_zipcode,
    parse_eur,
    parse_sqm,
)


class TestParseEur:
    def test_plain_number(self):
        """Plain numeric string parses to float — e.g. '750' → 750.0."""
        assert parse_eur("750") == 750.0

    def test_euro_symbol_with_whitespace(self):
        """Raw Kamernet rent string with euro symbol and surrounding whitespace → numeric value."""
        assert parse_eur("\n                            € 50\n                    ") == 50.0

    def test_list_wrapped(self):
        """Single-element list (as stored in Kamernet JSON) is unwrapped before parsing → 500.0."""
        assert parse_eur(["\n€ 500\n"]) == 500.0

    def test_empty_string(self):
        """Empty string has no numeric content → None."""
        assert parse_eur("") is None

    def test_empty_list(self):
        """Empty list has no value to unwrap → None."""
        assert parse_eur([]) is None

    def test_none(self):
        """None input returns None without raising."""
        assert parse_eur(None) is None

    def test_decimal_value(self):
        """Decimal euro amount is preserved — e.g. '€ 1250.50' → 1250.5."""
        assert parse_eur("€ 1250.50") == 1250.50


class TestParseSqm:
    def test_standard_format(self):
        """Standard '14 m2' format returns integer area 14."""
        assert parse_sqm("14 m2") == 14

    def test_unicode_superscript(self):
        """Unicode superscript '32m²' is handled and returns 32."""
        assert parse_sqm("32m²") == 32

    def test_list_wrapped(self):
        """Single-element list is unwrapped before parsing → 85."""
        assert parse_sqm(["85 m2"]) == 85

    def test_empty(self):
        """Empty string contains no digits → None."""
        assert parse_sqm("") is None

    def test_none(self):
        """None input returns None without raising."""
        assert parse_sqm(None) is None


class TestNormaliseZipcode:
    def test_clean_string(self):
        """Already-clean 4-digit string passes through unchanged → '1053'."""
        assert normalise_zipcode("1053") == "1053"

    def test_float_string(self):
        """Float-formatted zipcode from CSV parsing is stripped → '1053.0' → '1053'."""
        assert normalise_zipcode("1053.0") == "1053"

    def test_with_letters(self):
        """Full Dutch postcode with letter suffix is trimmed to PC4 → '1053AB' → '1053'."""
        assert normalise_zipcode("1053AB") == "1053"

    def test_too_short(self):
        """3-digit value is not a valid PC4 → None."""
        assert normalise_zipcode("105") is None

    def test_empty_string(self):
        """Empty string is not a valid zipcode → None."""
        assert normalise_zipcode("") is None

    def test_none(self):
        """None input returns None without raising."""
        assert normalise_zipcode(None) is None

    def test_nan_float(self):
        """Float NaN (missing value from pandas/CSV) returns None without raising."""
        assert normalise_zipcode(float("nan")) is None


class TestFlattenListField:
    def test_single_element_list(self):
        """Single-element list is unwrapped to its scalar value → '5d2b113a'."""
        assert flatten_list_field(["5d2b113a"]) == "5d2b113a"

    def test_empty_list(self):
        """Empty list has no value to return → None."""
        assert flatten_list_field([]) is None

    def test_plain_string_passthrough(self):
        """Non-list value passes through unchanged — no double-unwrapping."""
        assert flatten_list_field("hello") == "hello"

    def test_none_passthrough(self):
        """None passes through unchanged — safe to call on any field."""
        assert flatten_list_field(None) is None


class TestAirbnbMonthlyRevenue:
    def test_default_occupancy(self):
        """€100/night at default 66% occupancy equals 100 × 365 × 0.66 / 12 monthly."""
        result = airbnb_monthly_revenue(100.0)
        expected = 100.0 * 365 * 0.66 / 12
        assert abs(result - expected) < 0.01

    def test_custom_occupancy(self):
        """100% occupancy produces the theoretical maximum — 365 nights / 12 months."""
        result = airbnb_monthly_revenue(200.0, occupancy_rate=1.0)
        expected = 200.0 * 365 / 12
        assert abs(result - expected) < 0.01

    def test_zero_price(self):
        """Zero nightly price always yields zero monthly revenue regardless of occupancy."""
        assert airbnb_monthly_revenue(0.0) == 0.0
