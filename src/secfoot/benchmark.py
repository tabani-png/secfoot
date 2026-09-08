"""Turn extracted facts into one defensible number per metric, per company."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import validate
from .provenance import NOT_FOUND, Fact

YEAR_IN_LABEL = re.compile(r"\b(19|20)\d{2}\b")
SCALE = {"millions": 1.0, "thousands": 1e-3, "billions": 1e3}
# A number taken from the primary statement beats the same line repeated in a
# segment or supplementary table.
PREFERRED_TABLES = ("balance sheet", "financial position", "statement of cash flows")
# A footnote table carries one column per plan or segment per year. When a
# year has several columns, only an explicit total can stand for the metric.
TOTAL_COLUMN = re.compile(r"\b(total|consolidated|all plans)\b", re.I)
AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Metric:
    label: str
    topic: str
    row_patterns: tuple[str, ...]


METRICS: dict[str, Metric] = {
    "cash_and_equivalents": Metric(
        "Cash and cash equivalents", "cash_and_equivalents",
        (r"^cash and cash equivalents$", r"^cash, cash equivalents and restricted cash$")),
    "restricted_cash": Metric(
        "Restricted cash", "cash_and_equivalents", (r"^restricted cash$",)),
    "supplier_finance_obligation": Metric(
        "Supplier finance obligation", "supply_chain_finance",
        (r"confirmed obligations outstanding.*end", r"^supplier finance program,? obligation$")),
    "supplier_finance_confirmed": Metric(
        "Invoices confirmed in year", "supply_chain_finance",
        (r"invoices confirmed",)),
    "pension_service_cost": Metric(
        "Pension service cost", "pensions", (r"^service cost$",)),
    "pension_interest_cost": Metric(
        "Pension interest cost", "pensions", (r"^interest cost$",)),
    "pension_benefit_obligation": Metric(
        "Benefit obligation, end of year", "pensions",
        (r"benefit obligation.*end of (the )?year", r"^benefit obligation$")),
    "derivative_notional": Metric(
        "Derivative notional amount", "derivatives",
        (r"^notional amount", r"total notional")),
}


@dataclass
class Row:
    metric: str
    label: str
    value: Optional[float]
    units: Optional[str]
    period: Optional[str]
    prior_value: Optional[float]
    prior_period: Optional[str]
    row_label: Optional[str]
    table_title: Optional[str]
    source_url: Optional[str]
    status: str
    flags: list[str] = field(default_factory=list)
    # when a line is split across plans or segments, every column and its value
    breakdown: dict[str, float] = field(default_factory=dict)
    # the plan or segment this number covers; None means it is the total
    dimension: Optional[str] = None


def period_year(label: str) -> Optional[int]:
    match = YEAR_IN_LABEL.search(label or "")
    return int(match.group(0)) if match else None


def _table_rank(title: str) -> int:
    lowered = (title or "").lower()
    return 0 if any(p in lowered for p in PREFERRED_TABLES) else 1


def _missing(metric_name: str) -> Row:
    metric = METRICS[metric_name]
    return Row(metric=metric_name, label=metric.label, value=None, units=None,
               period=None, prior_value=None, prior_period=None, row_label=None,
               table_title=None, source_url=None, status=NOT_FOUND)


def pick(facts: list[Fact], metric_name: str) -> Row:
    """The one number for this metric, with its prior period and its source."""
    if metric_name not in METRICS:
        raise KeyError(f"unknown metric {metric_name!r}; known: {sorted(METRICS)}")
    metric = METRICS[metric_name]
    patterns = [re.compile(p, re.I) for p in metric.row_patterns]

    candidates = [
        f for f in facts
        if f.value is not None
        and f.provenance.units in SCALE
        and any(p.search((f.provenance.row_label or "").strip()) for p in patterns)
        and period_year(f.provenance.period) is not None
    ]
    if not candidates:
        return _missing(metric_name)

    # One table supplies the whole row, so the comparison is like for like.
    def table_key(f: Fact):
        return (_table_rank(f.provenance.table_title), f.provenance.table_title or "")

    best_table = min(table_key(f) for f in candidates)
    same_table = [f for f in candidates if table_key(f) == best_table]

    by_year: dict[int, list[Fact]] = {}
    for f in same_table:
        by_year.setdefault(period_year(f.provenance.period), []).append(f)
    years = sorted(by_year, reverse=True)

    def one_of(candidates_for_year: list[Fact]) -> Optional[Fact]:
        distinct = {round(f.value * SCALE[f.provenance.units], 4)
                    for f in candidates_for_year}
        if len(distinct) == 1:
            return candidates_for_year[0]
        # A figure the filing states without naming a plan or segment is the
        # total, so it stands for the metric.
        totals = [f for f in candidates_for_year if f.provenance.dimension is None]
        if len({round(f.value * SCALE[f.provenance.units], 4) for f in totals}) == 1:
            return totals[0]
        totals = [f for f in candidates_for_year
                  if TOTAL_COLUMN.search(f.provenance.column_label or "")]
        return totals[0] if len(totals) == 1 else None

    current = one_of(by_year[years[0]])
    if current is None:
        sample = by_year[years[0]][0].provenance
        # A report page often repeats one period header above every plan, so
        # identical labels must not collapse onto each other.
        breakdown: dict[str, float] = {}
        for f in by_year[years[0]]:
            key = f.provenance.dimension or f.provenance.column_label
            if key in breakdown:
                key = f"{key} [{len([k for k in breakdown if k.startswith(key)]) + 1}]"
            breakdown[key] = f.value * SCALE[f.provenance.units]
        columns = sorted(breakdown)
        named = any(f.provenance.dimension for f in by_year[years[0]])
        reason = ("no total" if named
                  else "columns not labelled apart in the filing")
        return Row(
            metric=metric_name, label=metric.label, value=None, units=None,
            period=None, prior_value=None, prior_period=None,
            row_label=sample.row_label, table_title=sample.table_title,
            source_url=sample.source_url, status=AMBIGUOUS,
            flags=[f"{len(columns)} columns for {years[0]}, {reason}: "
                   + "; ".join(columns)],
            breakdown=breakdown)
    prior = one_of(by_year[years[1]]) if len(years) > 1 else None

    scale = SCALE[current.provenance.units]
    value = current.value * scale
    prior_value = (prior.value * SCALE[prior.provenance.units]) if prior else None

    flags = []
    if not validate.validate_comparative(value, prior_value):
        flags.append("implausible move")

    return Row(
        metric=metric_name, label=metric.label, value=value, units="millions",
        period=current.provenance.period, prior_value=prior_value,
        prior_period=prior.provenance.period if prior else None,
        row_label=current.provenance.row_label,
        table_title=current.provenance.table_title,
        source_url=current.provenance.source_url, status="found", flags=flags,
        dimension=current.provenance.dimension)


def _cell(row: Row) -> str:
    if row.status == AMBIGUOUS:
        return "ambiguous ⚠"
    if row.status != "found" or row.value is None:
        return NOT_FOUND
    text = f"{row.value:,.0f}"
    if row.prior_value is not None:
        text += f" ({row.prior_value:,.0f})"
    if row.flags:
        text += " ⚠"
    return text


def render_markdown(by_company: dict[str, list[Row]]) -> str:
    companies = list(by_company)
    order = [m for m in METRICS if any(
        r.metric == m for rows in by_company.values() for r in rows)]

    lines = [
        "| Metric | " + " | ".join(companies) + " |",
        "|---" * (len(companies) + 1) + "|",
    ]
    for metric_name in order:
        cells = []
        for company in companies:
            row = next((r for r in by_company[company] if r.metric == metric_name), None)
            cells.append(_cell(row) if row else NOT_FOUND)
        label = METRICS[metric_name].label
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += ["", "All figures in $ millions. Current year, prior year in brackets.",
              "⚠ on a number marks a year-on-year move over 10x: check it before using it.",
              "\"ambiguous\" means the filing splits that line across plans or segments "
              "with no total; the columns are listed under Sources.", "",
              "## Sources", ""]
    for company in companies:
        lines.append(f"**{company}**")
        for row in by_company[company]:
            if row.status == AMBIGUOUS:
                lines.append(f"- {row.label}: split across columns in "
                             f"*{row.table_title}* - {row.source_url}")
                for column, value in sorted(row.breakdown.items()):
                    lines.append(f"    - {column}: {value:,.0f}")
                continue
            if row.status != "found":
                continue
            lines.append(f"- {row.label}: \"{row.row_label}\" in *{row.table_title}* "
                         f"- {row.source_url}")
        lines.append("")
    return "\n".join(lines)


def run(tickers, fetcher, form: str = "10-K", route: str = "auto",
        metrics=None) -> dict[str, list[Row]]:
    """Extract every metric for every company, one filing per company."""
    from . import pipeline

    wanted = list(metrics or METRICS)
    out: dict[str, list[Row]] = {}
    for ticker in tickers:
        by_topic: dict[str, list[Fact]] = {}
        rows = []
        for metric_name in wanted:
            topic = METRICS[metric_name].topic
            if topic not in by_topic:
                try:
                    by_topic[topic] = pipeline.answer(
                        ticker, topic, fetcher, form=form, route=route).facts
                except Exception:
                    by_topic[topic] = []
            rows.append(pick(by_topic[topic], metric_name))
        out[ticker] = rows
    return out
