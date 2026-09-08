"""AC13 (live): the table must hold real, traceable, cross-checkable numbers."""
import json
import pytest
from secfoot import benchmark, edgar

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def table(fetcher):
    return benchmark.run(["HPQ", "CAT", "BA"], fetcher)


def test_every_company_gets_a_row_for_every_metric(table):
    for ticker, rows in table.items():
        assert [r.metric for r in rows] == list(benchmark.METRICS), ticker


def test_hp_cash_matches_the_xbrl_figure(table, fetcher):
    cik = edgar.ticker_to_cik("HPQ", fetcher=fetcher)
    gaap = json.loads(fetcher.get(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"))["facts"]["us-gaap"]
    truth = {round(u["val"] / 1e6, 1) for tag in
             ("CashAndCashEquivalentsAtCarryingValue",
              "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents")
             for u in gaap.get(tag, {}).get("units", {}).get("USD", [])
             if u.get("form") == "10-K"}
    row = next(r for r in table["HPQ"] if r.metric == "cash_and_equivalents")
    assert row.status == "found"
    assert round(row.value, 1) in truth


def test_a_split_pension_line_is_answered_or_declared_ambiguous_never_guessed(table):
    """Boeing splits service cost across pension and other postretirement plans.

    Either the filing gives a total and we report it, or we say the line is
    ambiguous and name the columns. Reporting one plan's number as the
    company's pension service cost is the failure this guards against.
    """
    row = next(r for r in table["BA"] if r.metric == "pension_service_cost")
    assert row.status in ("found", "ambiguous")
    if row.status == "ambiguous":
        assert row.value is None
        assert row.flags
        assert any(r in row.flags[0] for r in ("no total", "not labelled apart"))
        assert len(row.breakdown) > 1, "an ambiguous row must show what it could not choose between"
        assert row.source_url, "an ambiguous row must still point at its table"
    else:
        assert row.value is not None


def test_every_found_number_carries_a_source_url_and_a_table_name(table):
    for ticker, rows in table.items():
        for row in rows:
            if row.status == "found":
                assert row.source_url.startswith("https://www.sec.gov/Archives/")
                assert row.table_title and row.row_label
                assert row.units == "millions"


def test_no_found_number_is_left_without_a_period(table):
    for rows in table.values():
        for row in rows:
            if row.status == "found":
                assert benchmark.period_year(row.period) is not None


def test_the_rendered_table_names_every_company_and_metric(table):
    text = benchmark.render_markdown(table)
    for ticker in table:
        assert ticker in text
    for metric in benchmark.METRICS.values():
        assert metric.label in text
