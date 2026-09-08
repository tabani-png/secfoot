"""AC10: find a report by the XBRL tags it contains, not by its name.

GE discloses its supplier finance program inside "ACCOUNTS PAYABLE -
Narrative (Details)". No report name mentions the program, so name matching
cannot reach it. Every inline-XBRL filing ships MetaLinks.json, which records
the XBRL element anchoring each report.
"""
import json
import pytest
from secfoot import edgar

BASE = "https://www.sec.gov/Archives/edgar/data/40545/000004054526000008"

META = json.dumps({
    "instance": {
        "ge-20251231.htm": {
            "report": {
                "R4": {
                    "shortName": "STATEMENT OF FINANCIAL POSITION",
                    "firstAnchor": {"name": "us-gaap:CashAndCashEquivalentsAtCarryingValue"},
                    "uniqueAnchor": {"name": "us-gaap:AssetsCurrent"},
                },
                "R93": {
                    "shortName": "ACCOUNTS PAYABLE - Narrative (Details)",
                    "firstAnchor": {"name": "us-gaap:AccountsPayableCurrent"},
                    "uniqueAnchor": {"name": "us-gaap:SupplierFinanceProgramObligationCurrent"},
                },
                "R60": {
                    "shortName": "GOODWILL - Changes (Details)",
                    "firstAnchor": {"name": "us-gaap:Goodwill"},
                    "uniqueAnchor": {"name": "us-gaap:GoodwillImpairmentLoss"},
                },
            }
        }
    }
})


def _match(topic):
    return edgar.parse_metalinks(META, BASE, topic)


def test_a_report_is_found_by_the_xbrl_tag_it_anchors():
    reports = _match("supply_chain_finance")
    assert [r.short_name for r in reports] == ["ACCOUNTS PAYABLE - Narrative (Details)"]


def test_the_matched_report_gets_the_right_archive_url():
    assert _match("supply_chain_finance")[0].url == f"{BASE}/R93.htm"


def test_a_first_anchor_tag_also_counts_as_a_match():
    assert [r.short_name for r in _match("cash_and_equivalents")] == [
        "STATEMENT OF FINANCIAL POSITION"]


def test_an_unrelated_report_is_never_matched():
    for topic in ("supply_chain_finance", "pensions", "derivatives"):
        assert not any("GOODWILL" in r.short_name for r in _match(topic))


def test_a_topic_with_no_matching_tag_returns_nothing():
    assert _match("pensions") == []


def test_an_unknown_topic_is_rejected():
    with pytest.raises(KeyError):
        _match("not_a_topic")


def test_malformed_metalinks_returns_nothing_rather_than_raising():
    assert edgar.parse_metalinks("{}", BASE, "pensions") == []
    assert edgar.parse_metalinks("not json", BASE, "pensions") == []
