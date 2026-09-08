"""AC10 (live): the tag route must reach GE's supplier finance disclosure."""
import pytest
from secfoot import edgar, extract, pipeline

pytestmark = pytest.mark.live


def _ge(fetcher):
    cik = edgar.ticker_to_cik("GE", fetcher=fetcher)
    subs = edgar.get_submissions(cik, fetcher=fetcher)
    return cik, edgar.list_filings(subs, forms=("10-K",), limit=1)[0]


def test_no_ge_report_name_mentions_supplier_finance(fetcher):
    """The premise: name matching genuinely cannot find it."""
    cik, filing = _ge(fetcher)
    named = edgar.reports_for_topic(
        edgar.list_reports(cik, filing.accession_number, fetcher=fetcher),
        "supply_chain_finance")
    assert named == [], "if GE renamed its report, this fixture needs updating"


def test_the_tag_route_finds_ges_supplier_finance_report(fetcher):
    cik, filing = _ge(fetcher)
    reports = edgar.reports_by_tag(cik, filing.accession_number,
                                   "supply_chain_finance", fetcher=fetcher)
    assert reports, "MetaLinks.json must locate the report anchoring the tag"


def test_the_reports_route_now_answers_supply_chain_finance_for_ge(fetcher):
    result = pipeline.answer("GE", "supply_chain_finance", fetcher, route="reports")
    assert [f for f in result.facts if f.value is not None], \
        "GE tags SupplierFinanceProgramObligationCurrent in its FY2025 10-K"


def test_the_tag_route_reads_less_than_the_whole_document(fetcher):
    cik, filing = _ge(fetcher)
    doc = edgar.archive_url(cik, filing.accession_number, filing.primary_document)
    whole = len(fetcher.get(doc))
    routed = pipeline.answer("GE", "supply_chain_finance", fetcher, route="reports")
    assert routed.bytes_read < whole
