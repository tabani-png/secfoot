"""AC1: turn a company into a CIK, and a filing into a raw archive URL."""
import pytest
from secfoot import edgar
from secfoot.http import build_headers, MissingUserAgentError

from tests.conftest import HP_CIK, USER_AGENT


def test_pad_cik_pads_a_bare_number_to_ten_digits():
    assert edgar.pad_cik("47217") == "0000047217"


def test_pad_cik_accepts_an_integer():
    assert edgar.pad_cik(47217) == "0000047217"


def test_pad_cik_leaves_an_already_padded_cik_unchanged():
    assert edgar.pad_cik("0000047217") == "0000047217"


def test_pad_cik_strips_a_cik_prefix():
    assert edgar.pad_cik("CIK0000047217") == "0000047217"


def test_pad_cik_rejects_a_cik_longer_than_ten_digits():
    with pytest.raises(ValueError):
        edgar.pad_cik("123456789012")


def test_build_headers_refuses_a_blank_user_agent():
    with pytest.raises(MissingUserAgentError):
        build_headers("")


def test_build_headers_refuses_a_user_agent_with_no_contact_email():
    with pytest.raises(MissingUserAgentError):
        build_headers("python-requests/2.31")


def test_build_headers_accepts_a_descriptive_user_agent_with_an_email():
    headers = build_headers(USER_AGENT)
    assert headers["User-Agent"] == USER_AGENT
    assert headers["Accept-Encoding"] == "gzip, deflate"


def test_archive_url_removes_accession_dashes_and_cik_leading_zeros():
    url = edgar.archive_url(HP_CIK, "0000047217-24-000053", "hpq-20241031.htm")
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/47217/"
        "000004721724000053/hpq-20241031.htm"
    )


def test_archive_url_never_points_at_the_xbrl_companyfacts_api():
    url = edgar.archive_url(HP_CIK, "0000047217-24-000053", "hpq-20241031.htm")
    assert "companyfacts" not in url
    assert "data.sec.gov" not in url
    assert url.startswith("https://www.sec.gov/Archives/edgar/data/")
