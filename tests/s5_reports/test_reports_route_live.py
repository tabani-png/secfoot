"""AC8 (live): the reports route must be cheaper AND reach more filers."""
import json
import pytest
from secfoot import edgar, extract

pytestmark = pytest.mark.live


def _latest(ticker, fetcher):
    cik = edgar.ticker_to_cik(ticker, fetcher=fetcher)
    subs = edgar.get_submissions(cik, fetcher=fetcher)
    filing = edgar.list_filings(subs, forms=("10-K",), limit=1)[0]
    return cik, filing


def _xbrl_cash(cik, fetcher):
    gaap = json.loads(fetcher.get(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"))["facts"]["us-gaap"]
    return {round(u["val"] / 1e6, 1)
            for u in gaap["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"]
            if u.get("form") == "10-K"}


def test_ibm_cash_is_reachable_through_reports_but_not_the_primary_document(fetcher):
    """IBM keeps its balance sheet out of the primary 10-K document."""
    cik, filing = _latest("IBM", fetcher)
    doc_url = edgar.archive_url(cik, filing.accession_number, filing.primary_document)
    from_document = extract.extract_topic(fetcher.get(doc_url), "cash_and_equivalents", doc_url)
    assert not from_document.facts, "if this now works, the fixture premise changed"

    reports = edgar.reports_for_topic(
        edgar.list_reports(cik, filing.accession_number, fetcher=fetcher),
        "cash_and_equivalents")
    assert reports, "IBM must expose a balance sheet report"
    truth = _xbrl_cash(cik, fetcher)
    found = []
    for report in reports[:4]:
        result = extract.extract_topic(fetcher.get(report.url), "cash_and_equivalents", report.url)
        found += [f.value for f in result.facts
                  if f.provenance.row_label.lower().startswith("cash and cash equivalents")
                  and f.value is not None]
    assert found, "the balance sheet report must yield a cash figure"
    assert truth & {round(v, 1) for v in found}, \
        f"none of {sorted(set(found))[:5]} match XBRL {sorted(truth)[:5]}"


def test_the_reports_route_reads_far_fewer_bytes_than_the_whole_document(fetcher):
    cik, filing = _latest("CAT", fetcher)
    doc_url = edgar.archive_url(cik, filing.accession_number, filing.primary_document)
    whole = len(fetcher.get(doc_url))
    reports = edgar.reports_for_topic(
        edgar.list_reports(cik, filing.accession_number, fetcher=fetcher),
        "supply_chain_finance")
    routed = sum(len(fetcher.get(r.url)) for r in reports[:2])
    assert routed * 10 < whole, f"routed {routed:,}b vs whole document {whole:,}b"


def test_the_caterpillar_supplier_rollforward_balances_through_the_reports_route(fetcher):
    cik, filing = _latest("CAT", fetcher)
    reports = edgar.reports_for_topic(
        edgar.list_reports(cik, filing.accession_number, fetcher=fetcher),
        "supply_chain_finance")
    rows = {}
    for report in reports[:3]:
        result = extract.extract_topic(fetcher.get(report.url), "supply_chain_finance", report.url)
        for fact in result.facts:
            label = fact.provenance.row_label.lower()
            if fact.value is not None and fact.provenance.period.strip() == "2025":
                rows.setdefault(label, fact.value)
    opening = next(v for k, v in rows.items() if "beginning" in k)
    confirmed = next(v for k, v in rows.items() if "invoices confirmed" in k)
    paid = next(v for k, v in rows.items() if "paid" in k)
    closing = next(v for k, v in rows.items() if "end of period" in k)
    from secfoot import validate
    assert validate.validate_subtotal([opening, confirmed, paid], closing, tolerance=1.0)


def test_a_fact_from_a_report_is_titled_with_that_reports_own_name(fetcher):
    """The report name IS the footnote name, so provenance needs no guessing."""
    from secfoot import pipeline
    result = pipeline.answer("HPQ", "cash_and_equivalents", fetcher, route="reports")
    assert result.facts
    titles = {f.provenance.table_title for f in result.facts}
    assert "(untitled table)" not in titles
    assert any("Balance Sheet" in t for t in titles)


def test_foreign_currency_is_answerable_through_the_reports_route(fetcher):
    from secfoot import pipeline
    result = pipeline.answer("HPQ", "foreign_currency", fetcher, route="reports")
    assert result.facts, "HP hedges FX; the reports route must reach those tables"
