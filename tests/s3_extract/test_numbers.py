"""AC3a: filing numbers are parsed the way accountants write them."""
import pytest
from secfoot.extract import parse_number


@pytest.mark.parametrize("text,expected", [
    ("1,234", 1234.0),
    ("$ 1,234", 1234.0),
    ("$1,234.56", 1234.56),
    ("(56)", -56.0),
    ("$ (1,234)", -1234.0),
    ("12.5%", 12.5),
    ("  789  ", 789.0),
    ("-", None),
    ("—", None),
    ("", None),
    ("N/A", None),
    ("Cash and cash equivalents", None),
])
def test_parse_number_reads_filing_style_numbers(text, expected):
    assert parse_number(text) == expected


def test_parentheses_always_mean_negative_not_a_footnote_marker():
    assert parse_number("(1,234)") == -1234.0
