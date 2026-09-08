"""AC6: a table belongs to the footnote it sits under, not to the words in it.

HP's supplier finance rollforward names neither "supply chain finance" in its
title nor in any row label. It is only identifiable by the heading above it.
"""
import pytest
from secfoot import extract

SOURCE = "https://www.sec.gov/Archives/edgar/data/47217/000004721725000071/hpq-20251031.htm"

SUPPLIER = """
<html><body>
<p>Notes to Consolidated Financial Statements (Continued)</p>
<p><b>Supplier Finance Program</b></p>
<p>HP facilitates voluntary supplier finance programs for certain suppliers.</p>
<p>The following table is a rollforward of the obligations confirmed under the program:</p>
<table>
  <tr><td></td><td>2025</td></tr>
  <tr><td></td><td>In millions</td></tr>
  <tr><td>Confirmed obligations outstanding at the beginning of the year</td>
      <td>$</td><td>7,808</td></tr>
  <tr><td>Invoices confirmed during the year</td><td>44,022</td></tr>
  <tr><td>Confirmed invoices paid during the year</td><td>( 42,921 )</td></tr>
</table>
<p><b>Government Assistance</b></p>
<p>HP receives assistance under agreements with governments.</p>
<table>
  <tr><td></td><td>2025</td></tr>
  <tr><td>Grants received</td><td>$</td><td>500</td></tr>
</table>
</body></html>
"""


def _values(result):
    return {f.provenance.row_label: f.value for f in result.facts}


def test_a_table_under_a_matched_heading_is_attached_even_with_no_keyword_in_it():
    result = extract.extract_topic(SUPPLIER, "supply_chain_finance", SOURCE)
    assert result.status == "found"
    values = _values(result)
    assert values["Confirmed obligations outstanding at the beginning of the year"] == 7808.0
    assert values["Invoices confirmed during the year"] == 44022.0


def test_bracketed_outflows_in_a_rollforward_stay_negative():
    values = _values(extract.extract_topic(SUPPLIER, "supply_chain_finance", SOURCE))
    assert values["Confirmed invoices paid during the year"] == -42921.0


def test_a_table_under_the_next_unrelated_heading_is_not_swept_in():
    values = _values(extract.extract_topic(SUPPLIER, "supply_chain_finance", SOURCE))
    assert "Grants received" not in values


def test_a_running_page_header_is_never_used_as_a_table_title():
    for table in extract.extract_tables(SUPPLIER, SOURCE):
        assert "Notes to Consolidated Financial Statements" not in table.title


TWO_HEADINGS = """
<html><body>
<p><b>Supplier Finance Program</b></p>
<p>HP facilitates voluntary supplier finance programs.</p>
<p><b>Supplier finance program obligations</b></p>
<table>
  <tr><td></td><td>2025</td></tr>
  <tr><td>Confirmed obligations outstanding at the end of the year</td><td>$</td><td>8,913</td></tr>
</table>
</body></html>
"""


def test_two_headings_naming_the_same_topic_do_not_duplicate_one_table():
    result = extract.extract_topic(TWO_HEADINGS, "supply_chain_finance", SOURCE)
    values = [f.value for f in result.facts
              if f.provenance.row_label.startswith("Confirmed obligations")]
    assert values == [8913.0], f"the table must appear once, got {values}"
