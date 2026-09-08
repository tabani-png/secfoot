"""AC18: a rollforward must add up, and the check runs by itself.

Opening + every movement = closing. Caterpillar's supplier finance note:
830 + 5,669 - 5,563 = 936. If it does not add, the figure is still reported,
with a flag saying so and showing the arithmetic. A mismatch is reported, never
silently corrected.
"""
import pytest
from secfoot import validate
from secfoot.provenance import Fact, Provenance

SOURCE = "https://www.sec.gov/Archives/edgar/data/18230/x/R28.htm"


def fact(value, row, period="2025", table="Supplier Finance Programs"):
    return Fact(value=value, provenance=Provenance(
        source_url=SOURCE, anchor=None, table_title=table, row_label=row,
        column_label=period, period=period, units="millions",
        raw_text=str(value), currency="USD"))


BALANCES = [
    fact(830.0, "Confirmed obligations outstanding, beginning of period"),
    fact(5669.0, "Invoices confirmed during the period"),
    fact(-5563.0, "Confirmed invoices paid during the period"),
    fact(936.0, "Confirmed obligations outstanding, end of period"),
]


def test_a_rollforward_that_adds_up_reports_no_problem():
    assert validate.check_rollforward(BALANCES, "2025") is None


def test_a_rollforward_that_does_not_add_up_is_reported():
    broken = BALANCES[:-1] + [
        fact(9999.0, "Confirmed obligations outstanding, end of period")]
    problem = validate.check_rollforward(broken, "2025")
    assert problem is not None
    assert "does not balance" in problem


def test_the_report_shows_the_arithmetic_so_it_can_be_checked_by_hand():
    broken = BALANCES[:-1] + [
        fact(9999.0, "Confirmed obligations outstanding, end of period")]
    problem = validate.check_rollforward(broken, "2025")
    assert "936" in problem, "the computed closing must be shown"
    assert "9,999" in problem or "9999" in problem, "the stated closing must be shown"


def test_a_table_with_no_opening_row_is_not_a_rollforward():
    not_a_rollforward = [
        fact(3690.0, "Cash and cash equivalents", table="Balance Sheets"),
        fact(41769.0, "Total assets", table="Balance Sheets"),
    ]
    assert validate.check_rollforward(not_a_rollforward, "2025") is None


def test_a_table_with_no_closing_row_is_not_a_rollforward():
    assert validate.check_rollforward(BALANCES[:2], "2025") is None


def test_a_rounding_difference_is_tolerated():
    close_enough = [
        fact(830.004, "Balance, beginning of year"),
        fact(106.0, "Additions"),
        fact(936.0, "Balance, end of year"),
    ]
    assert validate.check_rollforward(close_enough, "2025") is None


def test_a_movement_that_could_not_be_read_stops_the_check():
    """A missing component makes the sum meaningless, so say nothing."""
    incomplete = [
        fact(830.0, "Balance, beginning of year"),
        fact(None, "Additions"),
        fact(936.0, "Balance, end of year"),
    ]
    assert validate.check_rollforward(incomplete, "2025") is None


def test_only_the_requested_period_is_summed():
    mixed = BALANCES + [
        fact(803.0, "Confirmed obligations outstanding, beginning of period", "2024"),
        fact(830.0, "Confirmed obligations outstanding, end of period", "2024"),
    ]
    assert validate.check_rollforward(mixed, "2025") is None


def test_a_negative_movement_reads_as_a_subtraction():
    broken = BALANCES[:-1] + [
        fact(9999.0, "Confirmed obligations outstanding, end of period")]
    problem = validate.check_rollforward(broken, "2025")
    assert "- 5,563" in problem
    assert "+ -5,563" not in problem, "a deduction must not read as 'plus minus'"
