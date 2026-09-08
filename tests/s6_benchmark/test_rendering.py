"""AC12: the deliverable is a table a treasurer can read and check."""
from secfoot import benchmark
from secfoot.benchmark import Row


def _rows():
    return {
        "HPQ": [
            Row(metric="cash_and_equivalents", label="Cash and cash equivalents",
                value=3690.0, units="millions", period="Oct 31 2025",
                prior_value=3238.0, prior_period="Oct 31 2024",
                row_label="Cash and cash equivalents", table_title="Balance Sheets",
                source_url="https://www.sec.gov/x/R5.htm", status="found", flags=[]),
            Row(metric="pension_service_cost", label="Pension service cost",
                value=None, units=None, period=None, prior_value=None,
                prior_period=None, row_label=None, table_title=None,
                source_url=None, status="not found", flags=[]),
        ],
    }


def test_the_table_has_one_row_per_metric_and_one_column_per_company():
    text = benchmark.render_markdown(_rows())
    assert "| Metric | HPQ |" in text
    assert "Cash and cash equivalents" in text


def test_a_found_number_is_shown_with_its_units():
    assert "3,690" in benchmark.render_markdown(_rows())


def test_a_missing_metric_reads_not_found_and_never_blank():
    text = benchmark.render_markdown(_rows())
    assert "not found" in text
    assert "| Pension service cost |  |" not in text


def test_every_reported_number_is_footnoted_to_its_source():
    text = benchmark.render_markdown(_rows())
    assert "https://www.sec.gov/x/R5.htm" in text
    assert "Balance Sheets" in text


def _ambiguous():
    return {"BA": [Row(
        metric="pension_service_cost", label="Pension service cost", value=None,
        units=None, period=None, prior_value=None, prior_period=None,
        row_label="Service cost", table_title="Pension (Details)",
        source_url="https://www.sec.gov/x/R90.htm", status="ambiguous",
        flags=["2 columns for 2025, no total: Other Postretirement, 2025; Pension, 2025"],
        breakdown={"Pension, 2025": 9.0, "Other Postretirement, 2025": 1.0})]}


def test_an_ambiguous_row_prints_each_column_with_its_number():
    text = benchmark.render_markdown(_ambiguous())
    assert "Pension, 2025" in text and "9" in text
    assert "Other Postretirement, 2025" in text and "1" in text


def test_an_ambiguous_row_still_shows_its_source_url():
    assert "https://www.sec.gov/x/R90.htm" in benchmark.render_markdown(_ambiguous())


def _mixed():
    def row(metric, value, currency):
        return Row(metric=metric, label=benchmark.METRICS[metric].label, value=value,
                   units="millions", period="Dec 31 2025", prior_value=None,
                   prior_period=None, row_label="Cash and cash equivalents",
                   table_title="Balance sheet", source_url="https://www.sec.gov/x/R8.htm",
                   status="found", flags=[], currency=currency)
    return {"HPQ": [row("cash_and_equivalents", 3705.0, "USD")],
            "UL": [row("cash_and_equivalents", 3941.0, "EUR")]}


def test_a_euro_filer_is_never_printed_as_dollars():
    text = benchmark.render_markdown(_mixed())
    assert "€3,941" in text or "3,941 EUR" in text


def test_the_footer_never_claims_one_currency_for_a_mixed_table():
    text = benchmark.render_markdown(_mixed())
    assert "All figures in $ millions" not in text


def test_a_mixed_currency_table_warns_that_figures_are_not_comparable():
    text = benchmark.render_markdown(_mixed())
    assert "not directly comparable" in text.lower()


def test_a_single_currency_table_states_that_currency_plainly():
    only_usd = {"HPQ": _mixed()["HPQ"]}
    assert "USD millions" in benchmark.render_markdown(only_usd)
