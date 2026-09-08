"""AC17: an IFRS filer names the same pension lines differently.

US filers write "Service cost" and "Benefit obligation, end of year".
IFRS filers write "Current service cost" and "Present value of the DBO".
Matching only the US wording made every 20-F pension line read `not found`.
"""
import pytest
from secfoot import benchmark
from secfoot.provenance import Fact, Provenance

SOURCE = "https://www.sec.gov/Archives/edgar/data/1000184/x/R120.htm"


def fact(value, row, column="Dec. 31, 2025"):
    return Fact(value=value, provenance=Provenance(
        source_url=SOURCE, anchor=None, table_title="Pension Plans (Details)",
        row_label=row, column_label=column, period=column, units="millions",
        raw_text=str(value), currency="EUR"))


@pytest.mark.parametrize("row_label", [
    "Current service cost",
    "Service cost",
])
def test_both_wordings_of_service_cost_are_recognised(row_label):
    picked = benchmark.pick([fact(105.0, row_label)], "pension_service_cost")
    assert picked.status == "found"
    assert picked.value == 105.0


@pytest.mark.parametrize("row_label", [
    "Present value of the DBO",
    "Present value of the defined benefit obligation",
    "Defined benefit obligation",
    "Benefit obligation, end of the year",
])
def test_both_wordings_of_the_obligation_are_recognised(row_label):
    picked = benchmark.pick([fact(6100.0, row_label)], "pension_benefit_obligation")
    assert picked.status == "found"
    assert picked.value == 6100.0


def test_a_sensitivity_row_is_not_mistaken_for_the_obligation():
    """SAP prints "Present value of the DBO if discount rate was 50 basis
    points higher" directly beneath the real figure."""
    sensitivity = fact(5800.0, "Present value of the DBO if discount rate was "
                               "50 basis points higher")
    assert benchmark.pick([sensitivity], "pension_benefit_obligation").status == "not found"


def test_plan_assets_are_a_metric_of_their_own():
    picked = benchmark.pick([fact(4200.0, "Fair value of the plan assets")],
                            "pension_plan_assets")
    assert picked.status == "found"
    assert picked.value == 4200.0


def test_the_currency_survives_metric_selection():
    assert benchmark.pick([fact(105.0, "Current service cost")],
                          "pension_service_cost").currency == "EUR"
