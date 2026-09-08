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
