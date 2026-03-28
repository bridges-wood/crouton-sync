"""Tests for quantity mapping."""

from crouton_sync.quantity import (
    format_amount,
    parse_amount,
    to_crouton_type,
    to_display,
)


class TestToDisplay:
    def test_known_types(self):
        assert to_display("TABLESPOON") == "tbsp"
        assert to_display("TEASPOON") == "tsp"
        assert to_display("CUP") == "cup"
        assert to_display("POUND") == "lb"
        assert to_display("OUNCE") == "oz"
        assert to_display("GRAMS") == "g"
        assert to_display("ITEM") == ""

    def test_unknown_type(self):
        assert to_display("UNKNOWN") == "unknown"


class TestToCroutonType:
    def test_abbreviations(self):
        assert to_crouton_type("tbsp") == "TABLESPOON"
        assert to_crouton_type("tsp") == "TEASPOON"
        assert to_crouton_type("cup") == "CUP"
        assert to_crouton_type("lb") == "POUND"
        assert to_crouton_type("oz") == "OUNCE"
        assert to_crouton_type("g") == "GRAMS"

    def test_full_names(self):
        assert to_crouton_type("tablespoon") == "TABLESPOON"
        assert to_crouton_type("teaspoon") == "TEASPOON"
        assert to_crouton_type("pound") == "POUND"

    def test_plurals(self):
        assert to_crouton_type("cups") == "CUP"
        assert to_crouton_type("tablespoons") == "TABLESPOON"
        assert to_crouton_type("pounds") == "POUND"

    def test_unknown(self):
        assert to_crouton_type("scoops") is None


class TestFormatAmount:
    def test_whole_numbers(self):
        assert format_amount(2.0) == "2"
        assert format_amount(1.0) == "1"

    def test_fractions(self):
        assert format_amount(0.5) == "½"
        assert format_amount(0.25) == "¼"
        assert format_amount(0.75) == "¾"
        assert format_amount(1 / 3) == "⅓"

    def test_mixed(self):
        assert format_amount(1.5) == "1 ½"
        assert format_amount(2.25) == "2 ¼"

    def test_none_and_zero(self):
        assert format_amount(None) == ""
        assert format_amount(0) == ""


class TestParseAmount:
    def test_whole(self):
        assert parse_amount("2") == 2.0
        assert parse_amount("10") == 10.0

    def test_fraction_slash(self):
        assert parse_amount("1/3") is not None
        assert abs(parse_amount("1/3") - 1 / 3) < 0.01

    def test_unicode_fractions(self):
        assert parse_amount("½") == 0.5
        assert parse_amount("¼") == 0.25

    def test_mixed(self):
        assert parse_amount("1 ½") == 1.5
        assert parse_amount("2 ¼") == 2.25

    def test_empty(self):
        assert parse_amount("") is None
        assert parse_amount("  ") is None
