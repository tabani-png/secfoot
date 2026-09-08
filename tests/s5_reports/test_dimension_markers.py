"""AC14: a report page names its plans in marker rows, not in column headers.

Copied from Caterpillar's net periodic benefit cost page. A marker row carries
a label like "Pension Plan | U.S. Pension Benefits" and no values; every data
row beneath it belongs to that plan until the next marker. Rows above the first
marker are the undimensioned totals.
"""
from secfoot import extract

SOURCE = "https://www.sec.gov/Archives/edgar/data/18230/x/R101.htm"

PENSION_PAGE = """
<html><body>
<table class="report">
  <tr><th class="tl">Postemployment benefit plans (Details) - USD ($) $ in Millions</th>
      <th colspan="3">12 Months Ended</th></tr>
  <tr><th>Dec. 31, 2025</th><th>Dec. 31, 2024</th><th>Dec. 31, 2023</th></tr>
  <tr><td class="pl">Net periodic benefit cost</td>
      <td class="nump">$ 185</td><td class="nump">$ 67</td><td class="num">$ (65)</td></tr>
  <tr><td class="pl">Pension Plan | U.S. Pension Benefits</td>
      <td class="text"></td><td class="text"></td><td class="text"></td></tr>
  <tr><td class="pl">Service cost</td>
      <td class="nump">0</td><td class="nump">0</td><td class="nump">0</td></tr>
  <tr><td class="pl">Interest cost</td>
      <td class="nump">612</td><td class="nump">625</td><td class="nump">656</td></tr>
  <tr><td class="pl">Pension Plan | Non-U.S. Pension Benefits</td>
      <td class="text"></td><td class="text"></td><td class="text"></td></tr>
  <tr><td class="pl">Service cost</td>
      <td class="nump">49</td><td class="nump">47</td><td class="nump">45</td></tr>
</table>
</body></html>
"""


def _facts():
    return extract.extract_tables(PENSION_PAGE, SOURCE)[0].facts


def _by(row, dimension, period="Dec. 31, 2025"):
    return next(f.value for f in _facts()
                if f.provenance.row_label == row
                and f.provenance.dimension == dimension
                and period in f.provenance.period)


def test_a_row_above_the_first_marker_has_no_dimension():
    assert _by("Net periodic benefit cost", None) == 185.0


def test_a_row_under_a_marker_takes_that_markers_plan_name():
    assert _by("Service cost", "Pension Plan, U.S. Pension Benefits") == 0.0
    assert _by("Interest cost", "Pension Plan, U.S. Pension Benefits") == 612.0


def test_the_next_marker_switches_the_plan():
    assert _by("Service cost", "Pension Plan, Non-U.S. Pension Benefits") == 49.0


def test_the_marker_row_itself_produces_no_facts():
    labels = {f.provenance.row_label for f in _facts()}
    assert not any("|" in label for label in labels)


def test_the_dimension_name_covers_the_whole_marker_without_the_pipe():
    dimensions = {f.provenance.dimension for f in _facts()}
    assert any("U.S. Pension Benefits" in d for d in dimensions if d)
    assert all("|" not in d for d in dimensions if d)


def test_a_table_with_no_markers_leaves_every_dimension_empty():
    plain = """<html><body><table class="report">
      <tr><th class="tl">Balance Sheet $ in Millions</th><th>Dec. 31, 2025</th></tr>
      <tr><td class="pl">Cash and cash equivalents</td><td class="nump">$ 100</td></tr>
    </table></body></html>"""
    facts = extract.extract_tables(plain, SOURCE)[0].facts
    assert all(f.provenance.dimension is None for f in facts)


# HP's marker row carries no pipe at all: "Post-Retirement Benefit Plans".
# It is indistinguishable from a sub-heading by text, but the renderer marks
# every dimension row with <tr class="rh">, and sub-headings with ro/re.
HP_PAGE = """
<html><body>
<table class="report">
  <tr><th class="tl">Retirement Benefit Plans (Details) $ in Millions</th>
      <th colspan="2">12 Months Ended</th></tr>
  <tr><th>Oct. 31, 2025</th><th>Oct. 31, 2024</th></tr>
  <tr class="rh"><td class="pl">Post-Retirement Benefit Plans</td>
      <td class="text"></td><td class="text"></td></tr>
  <tr class="ro"><td class="pl">Net benefit (credit) cost</td>
      <td class="text"></td><td class="text"></td></tr>
  <tr class="re"><td class="pl">Service cost</td>
      <td class="nump">$ 1</td><td class="nump">$ 1</td></tr>
  <tr class="ro"><td class="pl">Interest cost</td>
      <td class="nump">14</td><td class="nump">15</td></tr>
  <tr class="rh"><td class="pl">U.S. | Defined Benefit Plans</td>
      <td class="text"></td><td class="text"></td></tr>
  <tr class="re"><td class="pl">Service cost</td>
      <td class="nump">0</td><td class="nump">0</td></tr>
  <tr class="ro"><td class="pl">Interest cost</td>
      <td class="nump">214</td><td class="nump">228</td></tr>
</table>
</body></html>
"""


def _hp(row, dimension):
    facts = extract.extract_tables(HP_PAGE, SOURCE)[0].facts
    return next(f.value for f in facts
                if f.provenance.row_label == row
                and f.provenance.dimension == dimension
                and "2025" in f.provenance.period)


def test_a_marker_row_with_no_pipe_is_found_by_its_row_class():
    assert _hp("Service cost", "Post-Retirement Benefit Plans") == 1.0
    assert _hp("Interest cost", "Post-Retirement Benefit Plans") == 14.0


def test_a_pipe_marker_row_keeps_both_sides_of_the_name():
    assert _hp("Service cost", "U.S., Defined Benefit Plans") == 0.0
    assert _hp("Interest cost", "U.S., Defined Benefit Plans") == 214.0


def test_a_plain_sub_heading_never_becomes_a_dimension():
    dimensions = {f.provenance.dimension
                  for f in extract.extract_tables(HP_PAGE, SOURCE)[0].facts}
    assert "Net benefit (credit) cost" not in dimensions


def test_no_figure_on_this_page_is_left_undimensioned():
    """Every number here belongs to a named plan, so none is a company total."""
    facts = extract.extract_tables(HP_PAGE, SOURCE)[0].facts
    assert all(f.provenance.dimension for f in facts)


# Which side of the pipe names the plan is not fixed. Caterpillar writes
# "Pension Plan | U.S. Pension Benefits" (member on the right); HP writes
# "U.S. | Defined Benefit Plans" and "Non-U.S. | Defined Benefit Plans"
# (member on the left). Keeping one side collapses HP's two plans into one.
TWO_SIDED = """
<html><body>
<table class="report">
  <tr><th class="tl">Benefit Plans (Details) $ in Millions</th>
      <th>Oct. 31, 2025</th></tr>
  <tr class="rh"><td class="pl">U.S. | Defined Benefit Plans</td><td class="text"></td></tr>
  <tr class="re"><td class="pl">Service cost</td><td class="nump">0</td></tr>
  <tr class="rh"><td class="pl">Non-U.S. | Defined Benefit Plans</td><td class="text"></td></tr>
  <tr class="re"><td class="pl">Service cost</td><td class="nump">39</td></tr>
</table>
</body></html>
"""


def test_two_plans_sharing_a_pipe_side_stay_distinct():
    facts = extract.extract_tables(TWO_SIDED, SOURCE)[0].facts
    values = {f.provenance.dimension: f.value for f in facts}
    assert len(values) == 2, f"the two plans collapsed into {sorted(values)}"
    assert sorted(values.values()) == [0.0, 39.0]


def test_both_sides_of_a_marker_appear_in_the_dimension_name():
    facts = extract.extract_tables(TWO_SIDED, SOURCE)[0].facts
    names = {f.provenance.dimension for f in facts}
    assert any("Non-U.S." in n and "Defined Benefit" in n for n in names)


def test_a_dimension_name_never_keeps_the_raw_pipe():
    facts = extract.extract_tables(TWO_SIDED, SOURCE)[0].facts
    assert all("|" not in f.provenance.dimension for f in facts)
