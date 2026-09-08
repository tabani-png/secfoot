"""AC7 (live): other filers must not produce mislabelled numbers."""
import pytest
from secfoot import extract

pytestmark = pytest.mark.live


def _cash_facts(html, url):
    result = extract.extract_topic(html, "cash_and_equivalents", url)
    return [f for f in result.facts
            if f.provenance.row_label.lower().startswith("cash and cash equivalents")
            and f.value is not None]


def test_caterpillar_consolidated_cash_is_never_attributed_to_a_segment(latest_10k):
    """CAT's supplemental table has ragged header rows.

    Its consolidated cash (which XBRL also reports) must either carry a
    'Consolidated' column label or not be reported at all. Reporting it under
    'Machinery, Power & Energy' is a wrong answer, not a partial one.
    """
    url, html = latest_10k("CAT")
    for fact in _cash_facts(html, url):
        column = fact.provenance.column_label.lower()
        if "machinery" in column or "financial products" in column:
            assert "consolidated" not in column, (
                f"{fact.value} is labelled both consolidated and segment: "
                f"{fact.provenance.column_label}"
            )


def test_a_segment_column_never_carries_the_consolidated_cash_figure(latest_10k, fetcher):
    """The real CAT defect: ragged header rows shifted every segment label.

    XBRL's CashAndCashEquivalentsAtCarryingValue is the CONSOLIDATED figure.
    If a fact labelled with a segment name equals it, the columns are shifted
    and the number is being reported against the wrong entity.
    """
    import json
    from secfoot import edgar
    cik = edgar.ticker_to_cik("CAT", fetcher=fetcher)
    gaap = json.loads(fetcher.get(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"))["facts"]["us-gaap"]
    consolidated = {round(u["val"] / 1e6, 1)
                    for u in gaap["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"]
                    if u.get("form") == "10-K"}
    url, html = latest_10k("CAT")
    for fact in _cash_facts(html, url):
        column = fact.provenance.column_label.lower()
        if fact.provenance.units != "millions":
            continue
        if any(word in column for word in ("machinery", "financial products")):
            assert round(fact.value, 1) not in consolidated, (
                f"{fact.value} is the CONSOLIDATED cash figure but is labelled "
                f"{fact.provenance.column_label!r} - the columns are shifted"
            )


@pytest.mark.parametrize("ticker", ["WMT", "PFE", "KO", "PG", "BA", "F"])
def test_the_cash_row_is_found_for_a_range_of_filers(latest_10k, ticker):
    url, html = latest_10k(ticker)
    assert _cash_facts(html, url), f"{ticker}: no cash and cash equivalents row"
