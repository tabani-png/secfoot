"""AC9: an R*.htm report page marks its header rows with <th> and omits the
stub cell on the period row.

Copied from Pfizer's "Supplier Finance Program Obligation (Details)" page.
Slicing off cells[0] of every header row swallowed the current-year column.
"""
from secfoot import extract

SOURCE = "https://www.sec.gov/Archives/edgar/data/78003/x/R100.htm"

REPORT_PAGE = """
<html><body>
<table class="report">
  <tr><th class="tl" colspan="1">Other Financial Information - Supplier Finance
      Program Obligation (Details) - USD ($) $ in Millions</th>
      <th colspan="2">12 Months Ended</th></tr>
  <tr><th>Dec. 31, 2025</th><th>Dec. 31, 2024</th></tr>
  <tr><td class="pl">Supplier Finance Program [Line Items]</td>
      <td class="text"></td><td class="text"></td></tr>
  <tr><td class="pl">Supplier Finance Program, Obligation, Current, Statement of
      Financial Position</td>
      <td class="text">Trade accounts payable</td>
      <td class="text">Trade accounts payable</td></tr>
  <tr><td class="pl">Confirmed obligations outstanding, beginning of period</td>
      <td class="nump">$ 688</td><td class="nump">$ 791</td></tr>
  <tr><td class="pl">Confirmed obligations outstanding, end of period</td>
      <td class="nump">574</td><td class="nump">688</td></tr>
</table>
</body></html>
"""


def _table():
    return extract.extract_tables(REPORT_PAGE, SOURCE)[0]


def _lookup(table):
    return {(f.provenance.row_label, f.provenance.column_label): f.value
            for f in table.facts}


def test_both_period_columns_survive_the_missing_stub_cell():
    assert _table().column_labels == [
        "12 Months Ended, Dec. 31, 2025",
        "12 Months Ended, Dec. 31, 2024",
    ]


def test_the_current_year_obligation_is_reported():
    values = _lookup(_table())
    assert values[("Confirmed obligations outstanding, end of period",
                   "12 Months Ended, Dec. 31, 2025")] == 574.0


def test_the_prior_year_obligation_is_reported():
    values = _lookup(_table())
    assert values[("Confirmed obligations outstanding, beginning of period",
                   "12 Months Ended, Dec. 31, 2024")] == 791.0


def test_units_are_read_from_the_dollars_in_millions_banner():
    assert _table().units == "millions"


def test_a_text_valued_row_is_not_mistaken_for_a_header_row():
    labels = {f.provenance.row_label for f in _table().facts}
    assert "Confirmed obligations outstanding, end of period" in labels
