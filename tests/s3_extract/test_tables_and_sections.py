"""AC3b: every number carries full provenance back to its spot in the filing."""
import pytest
from secfoot import extract
from secfoot.provenance import Fact

SOURCE = "https://www.sec.gov/Archives/edgar/data/47217/000004721724000053/hpq-20241031.htm"

SAMPLE = """
<html><body>
<p><a name="cash_note"></a><b>Note 5: Cash and Cash Equivalents</b></p>
<p>The following table summarizes cash and cash equivalents (in millions):</p>
<table>
  <tr><td></td><td>October 31, 2024</td><td>October 31, 2023</td></tr>
  <tr><td>Cash</td><td>$ 1,200</td><td>$ 1,000</td></tr>
  <tr><td>Money market funds</td><td>2,300</td><td>2,000</td></tr>
  <tr><td>Total cash and cash equivalents</td><td>$ 3,500</td><td>$ 3,000</td></tr>
</table>
<p><b>Foreign Currency Exchange Rate Risk</b></p>
<p>The Company uses forward contracts to hedge foreign currency exposure.</p>
</body></html>
"""


def test_extract_tables_finds_the_table_in_the_document():
    tables = extract.extract_tables(SAMPLE, SOURCE)
    assert len(tables) == 1


def test_the_table_title_comes_from_the_nearest_heading_above_it():
    table = extract.extract_tables(SAMPLE, SOURCE)[0]
    assert "Cash and Cash Equivalents" in table.title


def test_the_table_units_are_read_from_the_in_millions_lead_in():
    table = extract.extract_tables(SAMPLE, SOURCE)[0]
    assert table.units == "millions"


def test_the_column_labels_are_the_reporting_periods():
    table = extract.extract_tables(SAMPLE, SOURCE)[0]
    assert table.column_labels == ["October 31, 2024", "October 31, 2023"]


def test_every_cell_becomes_a_fact_with_its_row_and_column_label():
    table = extract.extract_tables(SAMPLE, SOURCE)[0]
    facts = table.facts
    assert all(isinstance(f, Fact) for f in facts)
    money = {
        (f.provenance.row_label, f.provenance.column_label): f.value for f in facts
    }
    assert money[("Cash", "October 31, 2024")] == 1200.0
    assert money[("Money market funds", "October 31, 2023")] == 2000.0
    assert money[("Total cash and cash equivalents", "October 31, 2024")] == 3500.0


def test_every_fact_records_the_exact_source_url_and_raw_text():
    table = extract.extract_tables(SAMPLE, SOURCE)[0]
    fact = next(f for f in table.facts if f.provenance.row_label == "Cash")
    p = fact.provenance
    assert p.source_url == SOURCE
    assert p.raw_text == "$ 1,200"
    assert p.units == "millions"
    assert p.period == "October 31, 2024"
    assert "Cash and Cash Equivalents" in p.table_title


def test_a_fact_records_the_nearest_html_anchor_so_a_human_can_jump_to_it():
    table = extract.extract_tables(SAMPLE, SOURCE)[0]
    fact = table.facts[0]
    assert fact.provenance.anchor == "cash_note"


def test_no_provenance_field_needed_for_traceability_is_ever_left_empty():
    table = extract.extract_tables(SAMPLE, SOURCE)[0]
    for fact in table.facts:
        p = fact.provenance
        for field in ("source_url", "table_title", "row_label", "column_label",
                      "period", "units", "raw_text"):
            assert getattr(p, field), f"{field} must be populated for traceability"


def test_find_sections_locates_the_foreign_currency_narrative():
    sections = extract.find_sections(SAMPLE, "foreign_currency", SOURCE)
    assert sections, "the Foreign Currency heading must be found by rule, not by AI"
    assert "forward contracts" in sections[0].text


def test_find_sections_locates_the_cash_note_by_rule():
    sections = extract.find_sections(SAMPLE, "cash_and_equivalents", SOURCE)
    assert any("Cash and Cash Equivalents" in s.heading for s in sections)


def test_find_sections_returns_empty_for_a_topic_that_is_not_in_the_filing():
    assert extract.find_sections(SAMPLE, "pensions", SOURCE) == []


def test_find_sections_rejects_an_unknown_topic_name():
    with pytest.raises(KeyError):
        extract.find_sections(SAMPLE, "made_up_topic", SOURCE)


YEAR_HEADERS = """
<html><body>
<p><b>Note 9: Pension and Post-Retirement Benefit Plans</b></p>
<p>Net periodic benefit cost (in millions):</p>
<table>
  <tr><td></td><td>2025</td><td>2024</td><td>2023</td></tr>
  <tr><td>Service cost</td><td>$ 40</td><td>$ 38</td><td>$ 35</td></tr>
  <tr><td>Interest cost</td><td>120</td><td>110</td><td>105</td></tr>
</table>
</body></html>
"""


def test_bare_year_column_headers_are_read_as_periods_not_as_values():
    table = extract.extract_tables(YEAR_HEADERS, SOURCE)[0]
    assert table.column_labels == ["2025", "2024", "2023"]


def test_rows_under_bare_year_headers_still_produce_facts():
    table = extract.extract_tables(YEAR_HEADERS, SOURCE)[0]
    money = {
        (f.provenance.row_label, f.provenance.period): f.value for f in table.facts
    }
    assert money[("Service cost", "2025")] == 40.0
    assert money[("Interest cost", "2023")] == 105.0
