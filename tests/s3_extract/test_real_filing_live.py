"""AC3c (live): the rules survive a real HP Inc. 10-K, not just a toy fixture."""
import pytest
from secfoot import extract

pytestmark = pytest.mark.live


def test_a_real_10k_yields_many_tables(hp_10k_html):
    url, html = hp_10k_html
    assert len(extract.extract_tables(html, url)) > 20


def test_every_fact_in_a_real_10k_still_carries_its_source_url(hp_10k_html):
    url, html = hp_10k_html
    tables = extract.extract_tables(html, url)
    facts = [f for t in tables for f in t.facts]
    assert facts
    assert all(f.provenance.source_url == url for f in facts)


def test_the_cash_and_equivalents_note_is_found_by_rule_in_a_real_10k(hp_10k_html):
    url, html = hp_10k_html
    assert extract.find_sections(html, "cash_and_equivalents", url)


def test_the_derivatives_note_is_found_by_rule_in_a_real_10k(hp_10k_html):
    url, html = hp_10k_html
    assert extract.find_sections(html, "derivatives", url)


def test_extract_topic_returns_sections_and_tables_together(hp_10k_html):
    url, html = hp_10k_html
    result = extract.extract_topic(html, "derivatives", url)
    assert result.topic == "derivatives"
    assert result.sections
    assert result.source_url == url


def test_extract_topic_returns_real_numbers_for_cash_in_a_real_10k(hp_10k_html):
    url, html = hp_10k_html
    result = extract.extract_topic(html, "cash_and_equivalents", url)
    assert result.status == "found"
    assert result.facts, "the cash note in a real 10-K must yield numbers"
    assert any(f.value is not None for f in result.facts)


def test_every_real_fact_is_fully_traceable(hp_10k_html):
    url, html = hp_10k_html
    result = extract.extract_topic(html, "cash_and_equivalents", url)
    for fact in result.facts:
        p = fact.provenance
        assert p.source_url == url
        assert p.row_label and p.column_label and p.raw_text and p.table_title


def test_the_real_balance_sheet_cash_row_keeps_both_reporting_years(hp_10k_html):
    url, html = hp_10k_html
    result = extract.extract_topic(html, "cash_and_equivalents", url)
    per_table = {}
    for fact in result.facts:
        if fact.provenance.row_label.lower() == "cash and cash equivalents":
            per_table.setdefault(fact.provenance.table_title, []).append(fact.value)
    assert per_table, "the cash row must be found"
    assert any(len(v) >= 2 for v in per_table.values()), \
        "at least one cash table must report the current AND the prior year"


def test_a_real_multi_period_table_exposes_more_than_one_column(hp_10k_html):
    url, html = hp_10k_html
    tables = extract.extract_tables(html, url)
    assert any(len(t.column_labels) >= 2 for t in tables)


def test_the_real_supplier_finance_rollforward_is_found(hp_10k_html):
    url, html = hp_10k_html
    result = extract.extract_topic(html, "supply_chain_finance", url)
    assert result.status == "found"
    assert result.facts, "HP discloses a supplier finance rollforward; it must be extracted"


def test_no_real_table_is_titled_with_a_running_page_header(hp_10k_html):
    url, html = hp_10k_html
    bad = [t.title for t in extract.extract_tables(html, url)
           if "Notes to Consolidated Financial Statements" in t.title]
    assert bad == [], f"{len(bad)} tables titled with the running page header"
