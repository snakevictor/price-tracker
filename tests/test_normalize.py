import pytest

from price_tracker.scrapers.base import clean_title, parse_brl


@pytest.mark.parametrize(
    "text,cents",
    [
        ("R$ 1.234,56", 123456),
        ("R$ 99,90", 9990),
        ("1.234", 123400),
        ("99", 9900),
        ("R$ 12.345,00 em 10x", 1234500),
        ("", None),
        (None, None),
        ("grátis", None),
    ],
)
def test_parse_brl(text, cents):
    assert parse_brl(text) == cents


def test_clean_title_collapses_whitespace():
    assert clean_title("  Echo   Dot \n5 ") == "Echo Dot 5"


def test_clean_title_handles_none():
    assert clean_title(None) == ""
