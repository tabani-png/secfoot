"""AC8: use the filing's own pre-rendered reports instead of the whole document.

Every inline-XBRL filing ships a FilingSummary.xml listing one small, clean
HTML table per statement and per footnote. Fetching the two reports that
matter beats parsing a six-megabyte document, and it reaches statements that
are not in the primary document at all.
"""
import pytest
from secfoot import edgar

SUMMARY = """<?xml version="1.0" encoding="utf-8"?>
<FilingSummary>
  <MyReports>
    <Report instance="cat-20251231.htm">
      <ShortName>CONSOLIDATED BALANCE SHEET</ShortName>
      <HtmlFileName>R5.htm</HtmlFileName>
    </Report>
    <Report instance="cat-20251231.htm">
      <ShortName>Supplier Finance Programs</ShortName>
      <HtmlFileName>R28.htm</HtmlFileName>
    </Report>
    <Report instance="cat-20251231.htm">
      <ShortName>Supplier Finance Programs (Tables)</ShortName>
      <HtmlFileName>R55.htm</HtmlFileName>
    </Report>
    <Report instance="cat-20251231.htm">
      <ShortName>Supplier Finance Programs (Policies)</ShortName>
      <HtmlFileName>R44.htm</HtmlFileName>
    </Report>
    <Report instance="cat-20251231.htm">
      <ShortName>Supplier Finance Programs - Rollforward (Details)</ShortName>
      <HtmlFileName>R80.htm</HtmlFileName>
    </Report>
    <Report>
      <ShortName>Cover Page</ShortName>
    </Report>
  </MyReports>
</FilingSummary>
"""

BASE = "https://www.sec.gov/Archives/edgar/data/18230/000001823026000012"


def test_parsing_the_summary_yields_one_report_per_named_table():
    reports = edgar.parse_filing_summary(SUMMARY, BASE)
    assert [r.short_name for r in reports] == [
        "CONSOLIDATED BALANCE SHEET",
        "Supplier Finance Programs",
        "Supplier Finance Programs (Tables)",
        "Supplier Finance Programs (Policies)",
        "Supplier Finance Programs - Rollforward (Details)",
    ]


def test_a_report_without_an_html_file_is_dropped():
    assert all(r.url for r in edgar.parse_filing_summary(SUMMARY, BASE))


def test_each_report_carries_a_full_archive_url():
    reports = edgar.parse_filing_summary(SUMMARY, BASE)
    assert reports[0].url == f"{BASE}/R5.htm"


def test_reports_are_matched_to_a_topic_by_their_own_name():
    reports = edgar.parse_filing_summary(SUMMARY, BASE)
    names = [r.short_name for r in edgar.reports_for_topic(reports, "supply_chain_finance")]
    assert "Supplier Finance Programs" in names
    assert "CONSOLIDATED BALANCE SHEET" not in names


def test_policy_and_table_stubs_are_skipped_as_duplicates():
    reports = edgar.parse_filing_summary(SUMMARY, BASE)
    names = [r.short_name for r in edgar.reports_for_topic(reports, "supply_chain_finance")]
    assert not any("(Tables)" in n or "(Policies)" in n for n in names)


def test_the_details_report_is_ranked_first_because_it_holds_the_numbers():
    reports = edgar.parse_filing_summary(SUMMARY, BASE)
    ranked = edgar.reports_for_topic(reports, "supply_chain_finance")
    assert "(Details)" in ranked[0].short_name


def test_the_balance_sheet_is_always_offered_for_the_cash_topic():
    reports = edgar.parse_filing_summary(SUMMARY, BASE)
    names = [r.short_name for r in edgar.reports_for_topic(reports, "cash_and_equivalents")]
    assert "CONSOLIDATED BALANCE SHEET" in names


def test_an_unknown_topic_is_rejected():
    reports = edgar.parse_filing_summary(SUMMARY, BASE)
    with pytest.raises(KeyError):
        edgar.reports_for_topic(reports, "not_a_topic")


# Report short names use a different vocabulary from the footnote prose.
# Filers file hedging under "FINANCIAL INSTRUMENTS", never "foreign currency".
REAL_NAMES = """<?xml version="1.0"?><FilingSummary><MyReports>
  <Report><ShortName>FINANCIAL INSTRUMENTS - Cash Flow Hedges and Net Investment Hedges (Details)</ShortName><HtmlFileName>R70.htm</HtmlFileName></Report>
  <Report><ShortName>Financial Instruments - Schedule of Pre-Tax Effect of Derivative Instruments (Details)</ShortName><HtmlFileName>R71.htm</HtmlFileName></Report>
  <Report><ShortName>STATEMENT OF FINANCIAL POSITION</ShortName><HtmlFileName>R4.htm</HtmlFileName></Report>
  <Report><ShortName>Consolidated Balance Sheets</ShortName><HtmlFileName>R5.htm</HtmlFileName></Report>
  <Report><ShortName>POSTRETIREMENT BENEFIT PLANS - Funding Status (Details)</ShortName><HtmlFileName>R90.htm</HtmlFileName></Report>
  <Report><ShortName>Goodwill - Changes in Goodwill Balances (Details)</ShortName><HtmlFileName>R60.htm</HtmlFileName></Report>
</MyReports></FilingSummary>"""


def _names(topic):
    reports = edgar.parse_filing_summary(REAL_NAMES, BASE)
    return [r.short_name for r in edgar.reports_for_topic(reports, topic)]


def test_hedging_reports_are_matched_to_foreign_currency():
    names = _names("foreign_currency")
    assert any("FINANCIAL INSTRUMENTS" in n for n in names), \
        "filers file FX hedging under 'Financial Instruments', not 'foreign currency'"


def test_a_statement_of_financial_position_counts_as_a_balance_sheet():
    assert "STATEMENT OF FINANCIAL POSITION" in _names("cash_and_equivalents")


def test_postretirement_reports_are_matched_to_pensions():
    assert any("POSTRETIREMENT" in n for n in _names("pensions"))


def test_a_goodwill_report_is_never_pulled_into_a_treasury_topic():
    for topic in ("cash_and_equivalents", "foreign_currency", "pensions",
                  "derivatives", "supply_chain_finance"):
        assert not any("Goodwill" in n for n in _names(topic))
