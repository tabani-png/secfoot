"""AC2: fetching is polite to SEC and cheap on repeat runs."""
import time
import pytest
from secfoot.http import Fetcher, MissingUserAgentError

from tests.conftest import USER_AGENT

pytestmark = pytest.mark.live

TICKERS = "https://www.sec.gov/files/company_tickers.json"


def test_fetcher_refuses_to_be_built_without_a_descriptive_user_agent(tmp_path):
    with pytest.raises(MissingUserAgentError):
        Fetcher(cache_dir=tmp_path, user_agent="")


def test_first_get_writes_the_body_into_the_cache_directory(tmp_path):
    f = Fetcher(cache_dir=tmp_path, user_agent=USER_AGENT)
    body = f.get(TICKERS)
    assert body.strip().startswith("{")
    assert list(tmp_path.glob("*")), "the response must be cached on disk"


def test_second_get_is_served_from_cache_without_a_network_call(tmp_path):
    f = Fetcher(cache_dir=tmp_path, user_agent=USER_AGENT)
    first = f.get(TICKERS)
    calls_before = f.network_calls
    second = f.get(TICKERS)
    assert second == first
    assert f.network_calls == calls_before, "a cached URL must not be re-fetched"


def test_the_cache_survives_a_new_fetcher_over_the_same_directory(tmp_path):
    Fetcher(cache_dir=tmp_path, user_agent=USER_AGENT).get(TICKERS)
    fresh = Fetcher(cache_dir=tmp_path, user_agent=USER_AGENT)
    fresh.get(TICKERS)
    assert fresh.network_calls == 0


def test_consecutive_network_calls_are_spaced_to_stay_under_ten_per_second(tmp_path):
    f = Fetcher(cache_dir=tmp_path, user_agent=USER_AGENT, min_interval=0.11)
    urls = [f"{TICKERS}?cachebust={i}" for i in range(3)]
    start = time.monotonic()
    for u in urls:
        f.get(u)
    elapsed = time.monotonic() - start
    assert f.network_calls == 3
    assert elapsed >= 0.22, "three requests must take at least two gaps of 0.11s"


def test_a_404_raises_rather_than_caching_an_error_page(tmp_path):
    f = Fetcher(cache_dir=tmp_path, user_agent=USER_AGENT)
    with pytest.raises(Exception):
        f.get("https://www.sec.gov/Archives/edgar/data/47217/does-not-exist-xyz.htm")
    assert not list(tmp_path.glob("*")), "failed responses must never be cached"
