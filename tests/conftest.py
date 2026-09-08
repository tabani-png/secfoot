import pathlib
import pytest

USER_AGENT = "Jeanmartin research muhammad.a@jeanmartin.com"
HP_CIK = "0000047217"
CACHE = pathlib.Path(__file__).resolve().parents[1] / ".cache"


@pytest.fixture(scope="session")
def fetcher():
    from secfoot.http import Fetcher
    return Fetcher(cache_dir=CACHE, user_agent=USER_AGENT)


@pytest.fixture(scope="session")
def hp_submissions(fetcher):
    from secfoot import edgar
    return edgar.get_submissions(HP_CIK, fetcher=fetcher)


@pytest.fixture(scope="session")
def hp_10k_html(fetcher, hp_submissions):
    """The most recent HP Inc. 10-K, fetched from the EDGAR archive."""
    from secfoot import edgar
    filing = edgar.list_filings(hp_submissions, forms=("10-K",), limit=1)[0]
    url = edgar.archive_url(HP_CIK, filing.accession_number, filing.primary_document)
    return url, fetcher.get(url)


@pytest.fixture(scope="session")
def latest_10k(fetcher):
    """(url, html) of a ticker's most recent 10-K."""
    from secfoot import edgar

    def _get(ticker):
        cik = edgar.ticker_to_cik(ticker, fetcher=fetcher)
        subs = edgar.get_submissions(cik, fetcher=fetcher)
        filing = edgar.list_filings(subs, forms=("10-K",), limit=1)[0]
        url = edgar.archive_url(cik, filing.accession_number, filing.primary_document)
        return url, fetcher.get(url)

    return _get
