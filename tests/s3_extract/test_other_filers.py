"""AC7: layouts from filers other than HP.

Each fixture copies the exact header shape of a real 10-K that the extractor
got wrong, so the regression is pinned to a named filer.
"""
from secfoot import extract

SOURCE = "https://www.sec.gov/Archives/edgar/data/104169/x/wmt-20260131.htm"


def _table(html):
    return extract.extract_tables(html, SOURCE)[0]


def _lookup(table):
    return {(f.provenance.row_label, f.provenance.column_label): f.value
            for f in table.facts}


# Walmart: the units sit in the header stub cell, and the year tier is
# exactly half filled because of the spacer columns between the years.
WALMART = """
<html><body><p><b>Consolidated Balance Sheets</b></p>
<table>
  <tr><td colspan="3"></td><td colspan="3"></td><td colspan="9">As of January 31,</td></tr>
  <tr><td colspan="3">(Amounts in millions)</td><td colspan="3"></td>
      <td colspan="3">2026</td><td colspan="3"></td><td colspan="3">2025</td></tr>
  <tr><td colspan="3">Cash and cash equivalents</td><td colspan="3"></td>
      <td>$</td><td>9,037</td><td></td><td colspan="3"></td>
      <td>$</td><td>9,037</td><td></td></tr>
</table></body></html>
"""


def test_a_half_filled_year_tier_still_drops_the_spacer_columns():
    assert _table(WALMART).column_labels == [
        "As of January 31, 2026",
        "As of January 31, 2025",
    ]


def test_a_trailing_comma_on_a_header_tier_is_not_doubled_up():
    for label in _table(WALMART).column_labels:
        assert ",," not in label


def test_units_stated_in_the_header_stub_cell_are_picked_up():
    assert _table(WALMART).units == "millions"


def test_the_walmart_cash_row_maps_to_both_years():
    values = _lookup(_table(WALMART))
    assert values[("Cash and cash equivalents", "As of January 31, 2026")] == 9037.0
    assert values[("Cash and cash equivalents", "As of January 31, 2025")] == 9037.0


# Caterpillar: three reporting segments, each with its own pair of years.
CATERPILLAR = """
<html><body><p><b>Supplemental consolidating data</b></p>
<p>(Millions of dollars)</p>
<table>
  <tr><td></td><td colspan="2">Consolidated</td>
      <td colspan="2">Machinery, Power &amp; Energy</td>
      <td colspan="2">Financial Products</td></tr>
  <tr><td></td><td>2025</td><td>2024</td><td>2025</td><td>2024</td>
      <td>2025</td><td>2024</td></tr>
  <tr><td>Cash and cash equivalents</td>
      <td>$</td><td>6,890</td><td>$</td><td>6,890</td>
      <td>$</td><td>2,000</td><td>$</td><td>2,100</td>
      <td>$</td><td>4,890</td><td>$</td><td>4,790</td></tr>
</table></body></html>
"""


def test_segment_columns_each_keep_their_own_year():
    table = _table(CATERPILLAR)
    assert table.column_labels == [
        "Consolidated, 2025", "Consolidated, 2024",
        "Machinery, Power & Energy, 2025", "Machinery, Power & Energy, 2024",
        "Financial Products, 2025", "Financial Products, 2024",
    ]


def test_a_segment_table_maps_every_cash_figure_to_the_right_segment():
    values = _lookup(_table(CATERPILLAR))
    assert values[("Cash and cash equivalents", "Consolidated, 2025")] == 6890.0
    assert values[("Cash and cash equivalents", "Financial Products, 2024")] == 4790.0


def test_millions_of_dollars_is_recognised_as_a_units_statement():
    assert _table(CATERPILLAR).units == "millions"


# Caterpillar's supplemental consolidating table: the header rows do not agree
# on how many columns exist, which silently dropped the "Consolidated" group
# and reported consolidated cash under the Machinery segment.
CAT_RAGGED = """
<html><body><p><b>Supplemental consolidating data</b></p>
<table>
  <tr><td colspan="3">At December 31,</td><td colspan="15"></td>
      <td colspan="33">Supplemental consolidating data</td></tr>
  <tr><td colspan="3"></td><td colspan="3"></td>
      <td colspan="9">Consolidated</td><td colspan="3"></td>
      <td colspan="9">Machinery, Power &amp; Energy</td><td colspan="3"></td>
      <td colspan="9">Financial Products</td></tr>
  <tr><td colspan="3">(Millions of dollars)</td><td colspan="3"></td>
      <td colspan="3">2025</td><td colspan="3"></td><td colspan="3">2024</td></tr>
  <tr><td colspan="3">Cash and cash equivalents</td>
      <td>9,980</td><td>6,889</td><td>9,333</td><td>6,165</td><td>647</td><td>724</td></tr>
</table></body></html>
"""


def test_a_table_whose_header_rows_disagree_on_width_reports_nothing():
    tables = extract.extract_tables(CAT_RAGGED, SOURCE)
    labels = {f.provenance.row_label for t in tables for f in t.facts}
    assert "Cash and cash equivalents" not in labels, (
        "a ragged header cannot be trusted; reporting a number under the wrong "
        "segment is worse than reporting nothing"
    )


def test_a_well_formed_segment_table_is_still_reported():
    values = _lookup(_table(CATERPILLAR))
    assert values[("Cash and cash equivalents", "Consolidated, 2025")] == 6890.0
