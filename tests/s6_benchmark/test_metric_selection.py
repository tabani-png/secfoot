"""AC11: turn a pile of facts into one defensible number per metric.

A filing states "cash and cash equivalents" in several tables. The benchmark
must pick one deterministically, say which table it came from, carry the prior
period beside it, and flag anything that fails a check rather than shipping it.
"""
import pytest
from secfoot import benchmark
from secfoot.provenance import Fact, Provenance

SOURCE = "https://www.sec.gov/Archives/edgar/data/47217/x/R5.htm"


def fact(value, row, column, title, units="millions"):
    return Fact(value=value, provenance=Provenance(
        source_url=SOURCE, anchor=None, table_title=title, row_label=row,
        column_label=column, period=column, units=units, raw_text=str(value)))


def test_a_four_digit_year_is_read_out_of_a_period_label():
    assert benchmark.period_year("As of October 31, 2025") == 2025
    assert benchmark.period_year("Dec. 31, 2024") == 2024
    assert benchmark.period_year("12 Months Ended, Dec. 31, 2023") == 2023


def test_a_period_label_with_no_year_has_no_year():
    assert benchmark.period_year("As of October 31") is None
    assert benchmark.period_year("") is None


FACTS = [
    fact(3690.0, "Cash and cash equivalents", "As of October 31, 2025",
         "Consolidated Balance Sheets"),
    fact(3238.0, "Cash and cash equivalents", "As of October 31, 2024",
         "Consolidated Balance Sheets"),
    fact(999.0, "Cash and cash equivalents", "As of October 31, 2025",
         "Segment Information"),
    fact(950.0, "Cash and cash equivalents", "As of October 31, 2024",
         "Segment Information"),
]


def test_the_primary_statement_wins_over_a_segment_table():
    row = benchmark.pick(FACTS, "cash_and_equivalents")
    assert row.value == 3690.0
    assert "Balance Sheets" in row.table_title


def test_the_prior_period_is_carried_beside_the_current_one():
    row = benchmark.pick(FACTS, "cash_and_equivalents")
    assert row.period == "As of October 31, 2025"
    assert row.prior_value == 3238.0
    assert row.prior_period == "As of October 31, 2024"


def test_the_source_url_travels_with_the_number():
    assert benchmark.pick(FACTS, "cash_and_equivalents").source_url == SOURCE


def test_thousands_are_normalised_to_millions():
    rows = [fact(3690000.0, "Cash and cash equivalents", "Dec. 31, 2025",
                 "Consolidated Balance Sheets", units="thousands")]
    picked = benchmark.pick(rows, "cash_and_equivalents")
    assert picked.value == 3690.0
    assert picked.units == "millions"


def test_a_metric_that_is_absent_reports_not_found_and_no_value():
    row = benchmark.pick([], "pension_service_cost")
    assert row.status == "not found"
    assert row.value is None
    assert row.source_url is None


def test_an_implausible_year_on_year_move_is_flagged_not_dropped():
    rows = [
        fact(300000.0, "Cash and cash equivalents", "Dec. 31, 2025", "Consolidated Balance Sheets"),
        fact(3000.0, "Cash and cash equivalents", "Dec. 31, 2024", "Consolidated Balance Sheets"),
    ]
    picked = benchmark.pick(rows, "cash_and_equivalents")
    assert picked.value == 300000.0, "the number is reported, not hidden"
    assert "implausible move" in picked.flags


def test_a_normal_move_carries_no_flag():
    assert benchmark.pick(FACTS, "cash_and_equivalents").flags == []


def test_an_unknown_metric_is_rejected():
    with pytest.raises(KeyError):
        benchmark.pick(FACTS, "not_a_metric")


def test_every_metric_declares_the_topic_it_is_extracted_from():
    for name, metric in benchmark.METRICS.items():
        assert metric.topic, f"{name} must name its topic"


# A pension table has one column per plan per year. Picking "the 2025 column"
# is meaningless when there are three of them, and silently returns whichever
# plan happened to come first.
DIMENSIONAL = [
    fact(39.0, "Service cost", "Non-U.S. Defined Benefit Plans, 2025", "Pension (Details)"),
    fact(0.0, "Service cost", "U.S. Defined Benefit Plans, 2025", "Pension (Details)"),
    fact(1.0, "Service cost", "Post-Retirement Benefit Plans, 2025", "Pension (Details)"),
    fact(37.0, "Service cost", "Non-U.S. Defined Benefit Plans, 2024", "Pension (Details)"),
]


def test_several_columns_for_one_year_is_reported_as_ambiguous_not_guessed():
    row = benchmark.pick(DIMENSIONAL, "pension_service_cost")
    assert row.status == "ambiguous"
    assert row.value is None, "one plan's number must not stand in for the whole metric"


def test_an_ambiguous_metric_names_the_columns_it_could_not_choose_between():
    row = benchmark.pick(DIMENSIONAL, "pension_service_cost")
    assert any("U.S. Defined Benefit Plans, 2025" in f for f in row.flags)
    assert any("Post-Retirement" in f for f in row.flags)


def test_an_ambiguous_metric_still_points_at_its_table():
    row = benchmark.pick(DIMENSIONAL, "pension_service_cost")
    assert row.source_url == SOURCE
    assert row.table_title == "Pension (Details)"


TOTALLED = DIMENSIONAL + [
    fact(40.0, "Service cost", "Total, 2025", "Pension (Details)"),
    fact(38.0, "Service cost", "Total, 2024", "Pension (Details)"),
]


def test_a_total_column_resolves_the_ambiguity():
    row = benchmark.pick(TOTALLED, "pension_service_cost")
    assert row.status == "found"
    assert row.value == 40.0
    assert row.prior_value == 38.0


def test_a_single_column_per_year_is_never_called_ambiguous():
    assert benchmark.pick(FACTS, "cash_and_equivalents").status == "found"


def test_an_ambiguous_row_still_carries_every_column_and_its_number():
    row = benchmark.pick(DIMENSIONAL, "pension_service_cost")
    assert row.breakdown == {
        "Non-U.S. Defined Benefit Plans, 2025": 39.0,
        "U.S. Defined Benefit Plans, 2025": 0.0,
        "Post-Retirement Benefit Plans, 2025": 1.0,
    }


def test_a_resolved_row_needs_no_breakdown():
    assert benchmark.pick(FACTS, "cash_and_equivalents").breakdown == {}


def test_the_breakdown_is_normalised_to_millions_like_everything_else():
    rows = [
        fact(39000.0, "Service cost", "Plan A, 2025", "Pension (Details)", units="thousands"),
        fact(1000.0, "Service cost", "Plan B, 2025", "Pension (Details)", units="thousands"),
    ]
    assert benchmark.pick(rows, "pension_service_cost").breakdown == {
        "Plan A, 2025": 39.0, "Plan B, 2025": 1.0}


# Caterpillar's pension report repeats one period header above every plan, so
# three different values arrive under the identical column label.
UNLABELLED_PLANS = [
    fact(0.0, "Service cost", "12 Months Ended, Dec. 31, 2025", "Pension (Details)"),
    fact(49.0, "Service cost", "12 Months Ended, Dec. 31, 2025", "Pension (Details)"),
    fact(63.0, "Service cost", "12 Months Ended, Dec. 31, 2025", "Pension (Details)"),
]


def test_identical_column_labels_with_different_values_are_still_ambiguous():
    assert benchmark.pick(UNLABELLED_PLANS, "pension_service_cost").status == "ambiguous"


def test_every_differing_value_survives_into_the_breakdown():
    breakdown = benchmark.pick(UNLABELLED_PLANS, "pension_service_cost").breakdown
    assert sorted(breakdown.values()) == [0.0, 49.0, 63.0]
    assert len(breakdown) == 3, "identical labels must not collapse onto each other"


def test_the_flag_says_the_source_does_not_name_the_columns_apart():
    row = benchmark.pick(UNLABELLED_PLANS, "pension_service_cost")
    assert "not labelled apart" in row.flags[0]


REPEATED_SAME_VALUE = [
    fact(3690.0, "Cash and cash equivalents", "Dec. 31, 2025", "Consolidated Balance Sheets"),
    fact(3690.0, "Cash and cash equivalents", "Dec. 31, 2025", "Consolidated Balance Sheets"),
    fact(3238.0, "Cash and cash equivalents", "Dec. 31, 2024", "Consolidated Balance Sheets"),
]


def test_the_same_number_repeated_is_not_ambiguous():
    row = benchmark.pick(REPEATED_SAME_VALUE, "cash_and_equivalents")
    assert row.status == "found"
    assert row.value == 3690.0


def dim_fact(value, row, column, title, dimension, units="millions"):
    return Fact(value=value, provenance=Provenance(
        source_url=SOURCE, anchor=None, table_title=title, row_label=row,
        column_label=column, period=column, units=units, raw_text=str(value),
        dimension=dimension))


PLANS = [
    dim_fact(0.0, "Service cost", "Dec. 31, 2025", "Pension (Details)", "U.S. Pension Benefits"),
    dim_fact(49.0, "Service cost", "Dec. 31, 2025", "Pension (Details)", "Non-U.S. Pension Benefits"),
    dim_fact(63.0, "Service cost", "Dec. 31, 2025", "Pension (Details)", "Other Postretirement"),
]


def test_the_breakdown_is_keyed_by_plan_name_when_the_filing_gives_one():
    row = benchmark.pick(PLANS, "pension_service_cost")
    assert row.status == "ambiguous"
    assert row.breakdown == {
        "U.S. Pension Benefits": 0.0,
        "Non-U.S. Pension Benefits": 49.0,
        "Other Postretirement": 63.0,
    }


def test_the_flag_lists_the_plans_by_name():
    row = benchmark.pick(PLANS, "pension_service_cost")
    assert "Non-U.S. Pension Benefits" in row.flags[0]


WITH_TOTAL = PLANS + [
    dim_fact(112.0, "Service cost", "Dec. 31, 2025", "Pension (Details)", None),
    dim_fact(108.0, "Service cost", "Dec. 31, 2024", "Pension (Details)", None),
]


def test_an_undimensioned_figure_is_the_total_and_wins():
    row = benchmark.pick(WITH_TOTAL, "pension_service_cost")
    assert row.status == "found"
    assert row.value == 112.0
    assert row.prior_value == 108.0


def test_the_chosen_total_records_that_it_covers_all_plans():
    assert benchmark.pick(WITH_TOTAL, "pension_service_cost").dimension is None
