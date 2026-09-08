"""The supplier-finance rollforward is on the filing's own report page, and we
still return no number for it.

Each case below pins a real filing whose FilingSummary.xml carries a
"Supplier Finance Program (Details)" report, and whose companyfacts endpoint
carries the matching us-gaap SupplierFinanceProgram* tag. The number is printed
in plain text on the report page. The shipped default route (`auto`) returns
zero facts with a value for all three, so these tests fail today.

Failure shape: `extract.extract_tables` yields either no table at all or only
value=None facts for these R*.htm pages, and because a list of value-less facts
is still truthy, `pipeline._from_reports` short-circuits the fallback to the
document route.
"""
import json
import pytest
from secfoot import edgar, extract, pipeline

pytestmark = pytest.mark.live

# ticker, accession pinned at the FY2025 10-K, the SCF (Details) report,
# and the obligation the filer tagged for the balance-sheet date, in $m.
CASES = [
    ("IBM", "0000051143-26-000010",
     "Significant Accounting Policies - Supplier Financing (Details)", 123.0),
    ("BA", "0001628280-26-004357",
     "Liabilities, Commitments and Contingencies - Schedule of Supplier Finance Program (Details)",
     1994.0),
    ("PFE", "0000078003-26-000026",
     "Other Financial Information - Supplier Finance Program Obligation (Details)", 574.0),
]


def _pinned_filing(ticker, accession, fetcher):
    cik = edgar.ticker_to_cik(ticker, fetcher=fetcher)
    subs = edgar.get_submissions(cik, fetcher=fetcher)
    for filing in edgar.list_filings(subs, forms=("10-K",)):
        if filing.accession_number == accession:
            return cik, filing
    pytest.skip(f"{ticker} {accession} has aged out of the recent-filings window")


def _xbrl_obligation(cik, fetcher):
    """Every SupplierFinanceProgram* obligation value the filer has tagged, in $m."""
    facts = json.loads(fetcher.get(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"))["facts"]
    values = set()
    for taxonomy in facts.values():
        for tag, body in taxonomy.items():
            if not tag.startswith("SupplierFinanceProgramObligation"):
                continue
            for units in body["units"].values():
                values |= {round(u["val"] / 1e6, 1) for u in units}
    return values


@pytest.mark.parametrize("ticker,accession,short_name,expected", CASES)
def test_the_filing_really_does_disclose_a_supplier_finance_program(
        ticker, accession, short_name, expected, fetcher):
    """Premise check: the disclosure is there, in the reports and in XBRL."""
    cik, filing = _pinned_filing(ticker, accession, fetcher)
    reports = edgar.list_reports(cik, filing.accession_number, fetcher=fetcher)
    assert any(r.short_name == short_name for r in reports), \
        f"{ticker} must expose {short_name!r}"
    assert expected in _xbrl_obligation(cik, fetcher), \
        f"{ticker} must tag a SupplierFinanceProgramObligation of ${expected}m"


@pytest.mark.parametrize("ticker,accession,short_name,expected", CASES)
def test_the_scf_report_page_yields_the_tagged_obligation(
        ticker, accession, short_name, expected, fetcher):
    """The report page prints the number; extract_tables must return it."""
    cik, filing = _pinned_filing(ticker, accession, fetcher)
    report = next(r for r in edgar.list_reports(cik, filing.accession_number, fetcher=fetcher)
                  if r.short_name == short_name)
    html = fetcher.get(report.url)
    assert str(int(expected)) in html or f"{int(expected):,}" in html, \
        "premise check: the figure is printed on the page"
    values = {round(f.value, 1)
              for table in extract.extract_tables(html, report.url)
              for f in table.facts if f.value is not None}
    assert expected in values, \
        f"{ticker}: extract_tables gave {sorted(values)[:6]}, wanted {expected}"


@pytest.mark.parametrize("ticker,accession,short_name,expected", CASES)
def test_the_default_route_answers_supply_chain_finance_with_a_number(
        ticker, accession, short_name, expected, fetcher):
    """End to end, through the shipped default route."""
    _pinned_filing(ticker, accession, fetcher)   # skip if the filing aged out
    answer = pipeline.answer(ticker, "supply_chain_finance", fetcher=fetcher)
    assert answer.status == "found"
    values = {round(f.value, 1) for f in answer.facts if f.value is not None}
    assert values, f"{ticker}: answer carried {len(answer.facts)} facts, none with a value"
    assert expected in values, \
        f"{ticker}: got {sorted(values)[:6]}, wanted the ${expected}m obligation"
