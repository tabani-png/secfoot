"""AC5: real filings stack their headers and pad rows. Columns must still line up.

These fixtures copy the exact shape of HP Inc.'s inline-XBRL tables: a spanning
top tier ("As of October 31"), a year tier below it, "$" in its own cell, and
em-dashes for nil values.
"""
import pytest
from secfoot import extract

SOURCE = "https://www.sec.gov/Archives/edgar/data/47217/000004721725000071/hpq-20251031.htm"

BALANCE_SHEET = """
<html><body>
<p><b>Consolidated Balance Sheets</b></p>
<p>(In millions)</p>
<table>
  <tr><td></td><td colspan="4">As of October 31</td></tr>
  <tr><td></td><td colspan="2">2025</td><td colspan="2">2024</td></tr>
  <tr><td>Cash and cash equivalents</td><td>$</td><td>3,690</td><td>$</td><td>3,238</td></tr>
  <tr><td>Total assets</td><td>$</td><td>41,769</td><td>$</td><td>39,909</td></tr>
</table>
</body></html>
"""

PENSION = """
<html><body>
<p><b>Note 4: Retirement and Post-Retirement Benefit Plans</b></p>
<p>(In millions)</p>
<table>
  <tr><td></td><td colspan="3">U.S. Defined Benefit Plans</td>
      <td colspan="3">Non-U.S. Defined Benefit Plans</td>
      <td colspan="3">Post-Retirement Benefit Plans</td></tr>
  <tr><td></td><td>2025</td><td>2024</td><td>2023</td>
      <td>2025</td><td>2024</td><td>2023</td>
      <td>2025</td><td>2024</td><td>2023</td></tr>
  <tr><td>Service cost</td>
      <td>$</td><td>&#8212;</td><td>$</td><td>&#8212;</td><td>$</td><td>&#8212;</td>
      <td>$</td><td>39</td><td>$</td><td>37</td><td>$</td><td>39</td>
      <td>$</td><td>1</td><td>$</td><td>1</td><td>$</td><td>1</td></tr>
  <tr><td>Interest cost</td>
      <td>214</td><td>228</td><td>217</td>
      <td>43</td><td>46</td><td>41</td>
      <td>14</td><td>15</td><td>15</td></tr>
</table>
</body></html>
"""


def _table(html):
    return extract.extract_tables(html, SOURCE)[0]


def _lookup(table):
    return {
        (f.provenance.row_label, f.provenance.column_label): f.value
        for f in table.facts
    }


def test_a_spanning_top_tier_is_joined_onto_the_year_tier():
    assert _table(BALANCE_SHEET).column_labels == [
        "As of October 31, 2025",
        "As of October 31, 2024",
    ]


def test_the_comparative_prior_year_column_is_never_dropped():
    values = _lookup(_table(BALANCE_SHEET))
    assert values[("Cash and cash equivalents", "As of October 31, 2025")] == 3690.0
    assert values[("Cash and cash equivalents", "As of October 31, 2024")] == 3238.0
    assert values[("Total assets", "As of October 31, 2024")] == 39909.0


def test_a_dollar_sign_in_its_own_cell_does_not_shift_the_columns():
    table = _table(BALANCE_SHEET)
    row = [f for f in table.facts if f.provenance.row_label == "Total assets"]
    assert [f.value for f in row] == [41769.0, 39909.0]


def test_a_nine_column_pension_table_keeps_all_nine_periods():
    table = _table(PENSION)
    assert len(table.column_labels) == 9
    assert table.column_labels[0] == "U.S. Defined Benefit Plans, 2025"
    assert table.column_labels[3] == "Non-U.S. Defined Benefit Plans, 2025"


def test_em_dash_cells_hold_their_place_so_later_numbers_stay_in_the_right_column():
    values = _lookup(_table(PENSION))
    assert values[("Service cost", "U.S. Defined Benefit Plans, 2025")] is None
    assert values[("Service cost", "Non-U.S. Defined Benefit Plans, 2025")] == 39.0
    assert values[("Service cost", "Non-U.S. Defined Benefit Plans, 2024")] == 37.0
    assert values[("Service cost", "Post-Retirement Benefit Plans, 2023")] == 1.0


def test_a_row_without_padding_cells_still_maps_to_all_nine_periods():
    values = _lookup(_table(PENSION))
    assert values[("Interest cost", "U.S. Defined Benefit Plans, 2025")] == 214.0
    assert values[("Interest cost", "Non-U.S. Defined Benefit Plans, 2024")] == 46.0
    assert values[("Interest cost", "Post-Retirement Benefit Plans, 2023")] == 15.0


MISALIGNED = """
<html><body><p><b>Broken table</b></p><p>(In millions)</p>
<table>
  <tr><td></td><td>2025</td><td>2024</td></tr>
  <tr><td>Three values under two columns</td><td>1</td><td>2</td><td>3</td></tr>
  <tr><td>Cash and cash equivalents</td><td>10</td><td>20</td></tr>
</table></body></html>
"""


def test_a_row_that_cannot_be_aligned_is_skipped_rather_than_guessed():
    table = _table(MISALIGNED)
    labels = {f.provenance.row_label for f in table.facts}
    assert "Three values under two columns" not in labels
    assert "Cash and cash equivalents" in labels


def test_skipped_rows_are_counted_so_the_gap_is_visible():
    assert _table(MISALIGNED).skipped_rows == 1


HP_EXACT = """
<html><body><p><b>Note 7: Supplementary Financial Information</b></p>
<table>
  <tr><td colspan="3"></td><td colspan="9">As of October 31</td></tr>
  <tr><td colspan="3"></td><td colspan="3">2025</td><td colspan="3"></td><td colspan="3">2024</td></tr>
  <tr><td colspan="3"></td><td colspan="9">In millions</td></tr>
  <tr><td colspan="3">Cash and cash equivalents</td>
      <td>$</td><td>3,690</td><td></td><td colspan="3"></td><td>$</td><td>3,238</td><td></td></tr>
  <tr><td colspan="3">Restricted cash</td>
      <td>$</td><td>15</td><td></td><td colspan="3"></td><td>$</td><td>15</td><td></td></tr>
</table></body></html>
"""


def test_a_units_only_header_tier_is_not_treated_as_a_period():
    table = _table(HP_EXACT)
    assert all("In millions" not in label for label in table.column_labels)


def test_a_units_only_header_tier_sets_the_table_units():
    assert _table(HP_EXACT).units == "millions"


def test_empty_spacer_columns_between_year_groups_are_dropped():
    assert _table(HP_EXACT).column_labels == [
        "As of October 31, 2025",
        "As of October 31, 2024",
    ]


def test_the_real_hp_layout_yields_both_years_for_the_cash_row():
    values = _lookup(_table(HP_EXACT))
    assert values[("Cash and cash equivalents", "As of October 31, 2025")] == 3690.0
    assert values[("Cash and cash equivalents", "As of October 31, 2024")] == 3238.0
    assert values[("Restricted cash", "As of October 31, 2024")] == 15.0
