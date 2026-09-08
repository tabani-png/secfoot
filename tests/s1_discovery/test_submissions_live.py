"""AC1 (live): the submissions endpoint gives us filing metadata, not XBRL values."""
import pytest
from secfoot import edgar

from tests.conftest import HP_CIK

pytestmark = pytest.mark.live


def test_ticker_to_cik_resolves_hpq_to_hp_incs_padded_cik(fetcher):
    assert edgar.ticker_to_cik("HPQ", fetcher=fetcher) == HP_CIK


def test_ticker_to_cik_is_case_insensitive(fetcher):
    assert edgar.ticker_to_cik("hpq", fetcher=fetcher) == HP_CIK


def test_ticker_to_cik_raises_for_an_unknown_ticker(fetcher):
    with pytest.raises(LookupError):
        edgar.ticker_to_cik("ZZZZNOTATICKER", fetcher=fetcher)


def test_get_submissions_returns_hp_inc_with_a_recent_filings_block(hp_submissions):
    assert "HP" in hp_submissions["name"].upper()
    assert "recent" in hp_submissions["filings"]
    assert len(hp_submissions["filings"]["recent"]["accessionNumber"]) > 0


def test_list_filings_returns_only_the_requested_form_type(hp_submissions):
    filings = edgar.list_filings(hp_submissions, forms=("10-K",))
    assert filings, "HP Inc. must have at least one 10-K on file"
    assert {f.form for f in filings} == {"10-K"}


def test_list_filings_can_return_several_form_types_at_once(hp_submissions):
    filings = edgar.list_filings(hp_submissions, forms=("10-K", "10-Q"))
    assert {f.form for f in filings} == {"10-K", "10-Q"}


def test_list_filings_honours_the_limit(hp_submissions):
    assert len(edgar.list_filings(hp_submissions, forms=("10-K",), limit=1)) == 1


def test_each_filing_carries_the_four_fields_needed_to_build_an_archive_url(hp_submissions):
    filing = edgar.list_filings(hp_submissions, forms=("10-K",), limit=1)[0]
    assert filing.accession_number.count("-") == 2
    assert filing.primary_document.endswith((".htm", ".html", ".txt"))
    assert len(filing.report_date) == 10
    assert len(filing.filing_date) == 10


def test_list_filings_returns_newest_filing_first(hp_submissions):
    filings = edgar.list_filings(hp_submissions, forms=("10-K",))
    dates = [f.filing_date for f in filings]
    assert dates == sorted(dates, reverse=True)


def test_the_built_archive_url_actually_serves_the_original_filing_html(fetcher, hp_10k_html):
    url, html = hp_10k_html
    assert url.startswith("https://www.sec.gov/Archives/edgar/data/47217/")
    assert len(html) > 100_000, "a 10-K document should be substantial"
    assert "10-K" in html
