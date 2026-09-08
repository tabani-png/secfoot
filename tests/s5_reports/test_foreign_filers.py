"""AC16: a 20-F filer writes its numbers in its own currency, and hangs
footnote markers off its row labels.

Both shapes are copied from real pages: SAP's statement of financial position
puts a "[1]" cell between the label and the values; Toyota writes its figures
with a yen sign.
"""
import pytest
from secfoot import extract
from secfoot.extract import parse_number

SOURCE = "https://www.sec.gov/Archives/edgar/data/1000184/x/R4.htm"


@pytest.mark.parametrize("text,expected", [
    ("€ 8,220", 8220.0),
    ("€8,220", 8220.0),
    ("¥ 8,982,910", 8982910.0),
    ("£ 1,234", 1234.0),
    ("£ (1,234)", -1234.0),
    ("€ (498)", -498.0),
    ("CHF 1,200", 1200.0),
])
def test_a_foreign_currency_figure_still_parses(text, expected):
    assert parse_number(text) == expected


@pytest.mark.parametrize("text", ["[1]", "[2]", "[a]", "[10]"])
def test_a_footnote_marker_is_not_a_number(text):
    assert parse_number(text) is None


SAP_PAGE = """
<html><body><table class="report">
  <tr><th class="tl">Consolidated Statements of Financial Position - EUR (€) € in Millions</th>
      <th>Dec. 31, 2025</th><th>Dec. 31, 2024</th></tr>
  <tr class="re"><td class="pl">Cash and cash equivalents</td><td class="fn">[1]</td>
      <td class="nump">€ 8,220</td><td class="nump">€ 9,609</td></tr>
  <tr class="ro"><td class="pl">Trade and other receivables</td><td class="fn"></td>
      <td class="nump">6,675</td><td class="nump">6,774</td></tr>
</table></body></html>
"""


def _values():
    table = extract.extract_tables(SAP_PAGE, SOURCE)[0]
    return {(f.provenance.row_label, f.provenance.column_label): f.value
            for f in table.facts}


def test_a_footnote_marker_cell_does_not_break_the_column_alignment():
    values = _values()
    assert values[("Cash and cash equivalents", "Dec. 31, 2025")] == 8220.0
    assert values[("Cash and cash equivalents", "Dec. 31, 2024")] == 9609.0


def test_a_row_without_a_marker_still_lines_up():
    values = _values()
    assert values[("Trade and other receivables", "Dec. 31, 2024")] == 6774.0


def test_no_row_on_the_page_is_skipped_for_misalignment():
    assert extract.extract_tables(SAP_PAGE, SOURCE)[0].skipped_rows == 0


def test_the_euro_figures_are_recorded_as_euros():
    table = extract.extract_tables(SAP_PAGE, SOURCE)[0]
    assert table.currency == "EUR"
    assert all(f.provenance.currency == "EUR" for f in table.facts)
