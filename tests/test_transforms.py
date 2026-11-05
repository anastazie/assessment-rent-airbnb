"""Unit tests for amsterdam_rental.transforms.

Pure-function tests — no Spark dependency required.
Run with: pytest tests/
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from amsterdam_rental.transforms import (
    parse_eur,
    parse_sqm,
    normalise_zipcode,
    flatten_list_field,
    airbnb_monthly_revenue,
)


class TestParseEur:
    def test_plain_number(self):
        assert parse_eur("750") == 750.0

    def test_euro_symbol_with_whitespace(self):
        assert parse_eur("\n                            € 50\n                    ") == 50.0

    def test_list_wrapped(self):
        assert parse_eur(["\n€ 500\n"]) == 500.0

    def test_empty_string(self):
        assert parse_eur("") is None

    def test_empty_list(self):
        assert parse_eur([]) is None

    def test_none(self):
        assert parse_eur(None) is None

    def test_decimal_value(self):
        assert parse_eur("€ 1250.50") == 1250.50


class TestParseSqm:
    def test_standard_format(self):
        assert parse_sqm("14 m2") == 14

    def test_unicode_superscript(self):
        assert parse_sqm("32m²") == 32

    def test_list_wrapped(self):
        assert parse_sqm(["85 m2"]) == 85

    def test_empty(self):
        assert parse_sqm("") is None

    def test_none(self):
        assert parse_sqm(None) is None


class TestNormaliseZipcode:
    def test_clean_string(self):
        assert normalise_zipcode("1053") == "1053"

    def test_float_string(self):
        assert normalise_zipcode("1053.0") == "1053"

    def test_with_letters(self):
        assert normalise_zipcode("1053AB") == "1053"

    def test_too_short(self):
        assert normalise_zipcode("105") is None

    def test_empty_string(self):
        assert normalise_zipcode("") is None

    def test_none(self):
        assert normalise_zipcode(None) is None

    def test_nan_float(self):
        assert normalise_zipcode(float("nan")) is None


class TestFlattenListField:
    def test_single_element_list(self):
        assert flatten_list_field(["5d2b113a"]) == "5d2b113a"

    def test_empty_list(self):
        assert flatten_list_field([]) is None

    def test_plain_string_passthrough(self):
        assert flatten_list_field("hello") == "hello"

    def test_none_passthrough(self):
        assert flatten_list_field(None) is None


class TestAirbnbMonthlyRevenue:
    def test_default_occupancy(self):
        result = airbnb_monthly_revenue(100.0)
        expected = 100.0 * 365 * 0.65 / 12
        assert abs(result - expected) < 0.01

    def test_custom_occupancy(self):
        result = airbnb_monthly_revenue(200.0, occupancy_rate=1.0)
        expected = 200.0 * 365 / 12
        assert abs(result - expected) < 0.01

    def test_zero_price(self):
        assert airbnb_monthly_revenue(0.0) == 0.0
