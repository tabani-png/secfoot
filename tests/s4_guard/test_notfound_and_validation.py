"""AC4: the pipeline says 'not found' instead of guessing, and checks its own maths."""
import pytest
from secfoot import extract, validate
from secfoot.provenance import NOT_FOUND

SOURCE = "https://www.sec.gov/Archives/edgar/data/47217/000004721724000053/hpq-20241031.htm"

NO_PENSION = "<html><body><p>Note 1: Basis of Presentation</p></body></html>"


def test_extract_topic_returns_not_found_when_the_topic_is_absent():
    result = extract.extract_topic(NO_PENSION, "pensions", SOURCE)
    assert result.status == NOT_FOUND
    assert result.sections == []
    assert result.tables == []


def test_a_not_found_result_carries_no_numeric_value_at_all():
    result = extract.extract_topic(NO_PENSION, "supply_chain_finance", SOURCE)
    assert result.facts == []


def test_a_found_result_is_not_labelled_not_found():
    html = "<html><body><p><b>Pension and Post-Retirement Benefit Plans</b></p>" \
           "<p>The Company sponsors defined benefit plans.</p></body></html>"
    result = extract.extract_topic(html, "pensions", SOURCE)
    assert result.status == "found"
    assert result.sections


def test_validate_subtotal_accepts_components_that_add_to_the_reported_total():
    assert validate.validate_subtotal([1200.0, 2300.0], 3500.0) is True


def test_validate_subtotal_rejects_components_that_do_not_add_up():
    with pytest.raises(validate.SubtotalMismatch):
        validate.validate_subtotal([1200.0, 2300.0], 9999.0)


def test_validate_subtotal_allows_a_small_rounding_difference():
    assert validate.validate_subtotal([1200.004, 2300.0], 3500.0, tolerance=0.01) is True


def test_validate_subtotal_ignores_components_that_were_not_found():
    with pytest.raises(validate.SubtotalMismatch):
        validate.validate_subtotal([1200.0, None], 3500.0)


def test_validate_comparative_accepts_a_normal_year_on_year_move():
    assert validate.validate_comparative(3500.0, 3000.0) is True


def test_validate_comparative_flags_an_implausible_hundredfold_jump():
    assert validate.validate_comparative(300000.0, 3000.0) is False


def test_validate_comparative_returns_true_when_there_is_no_prior_period():
    assert validate.validate_comparative(3500.0, None) is True


ROW_MATCH_ONLY = """
<html><body>
<p>The following table summarizes the balances (in millions):</p>
<table>
  <tr><td></td><td>2025</td></tr>
  <tr><td>Cash and cash equivalents</td><td>$ 3,500</td></tr>
</table>
</body></html>
"""


def test_a_table_is_matched_to_a_topic_by_its_row_labels_not_only_its_title():
    result = extract.extract_topic(ROW_MATCH_ONLY, "cash_and_equivalents", SOURCE)
    assert result.tables, "a table whose ROW label names the topic must be attached"
    assert result.facts[0].value == 3500.0


def test_row_label_matching_does_not_attach_an_unrelated_topic():
    result = extract.extract_topic(ROW_MATCH_ONLY, "pensions", SOURCE)
    assert result.tables == []


TABLE_OF_CONTENTS = """
<html><body>
<p><b>Index</b></p>
<table>
  <tr><td></td><td>Page</td></tr>
  <tr><td>Pension and Post-Retirement Benefit Plans</td><td>47</td></tr>
</table>
</body></html>
"""


def test_a_table_of_contents_is_not_mistaken_for_a_treasury_table():
    result = extract.extract_topic(TABLE_OF_CONTENTS, "pensions", SOURCE)
    assert result.tables == [], "a 'Page' column is not a reporting period"
    assert result.facts == []


def test_every_topic_fact_is_tied_to_a_real_reporting_period():
    from secfoot.extract import looks_like_period
    result = extract.extract_topic(ROW_MATCH_ONLY, "cash_and_equivalents", SOURCE)
    assert result.facts
    assert all(looks_like_period(f.provenance.period) for f in result.facts)
