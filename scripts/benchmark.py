"""Run the extractor over many filers and cross-check it against XBRL.

Cash and cash equivalents is one of the few treasury figures XBRL tags
reliably, so it works as an independent ground truth for the parser.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from secfoot import edgar, extract           # noqa: E402
from secfoot.http import Fetcher             # noqa: E402

UA = "Jeanmartin research muhammad.a@jeanmartin.com"
CACHE = pathlib.Path(__file__).resolve().parents[1] / ".cache"
TOPICS = ["cash_and_equivalents", "foreign_currency", "derivatives",
          "supply_chain_finance", "pensions"]
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]


def xbrl_cash(cik: str, fetcher: Fetcher) -> dict:
    """{period_end: value_in_millions} straight from companyfacts."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        gaap = json.loads(fetcher.get(url))["facts"]["us-gaap"]
    except Exception:
        return {}
    out = {}
    for tag in CASH_TAGS:
        for unit in gaap.get(tag, {}).get("units", {}).get("USD", []):
            if unit.get("form") in ("10-K", "20-F"):
                out.setdefault(unit["end"], unit["val"] / 1e6)
    return out


def scale(value, units):
    return {"millions": 1.0, "thousands": 1e-3, "billions": 1e3}.get(units, None)


def run(tickers):
    fetcher = Fetcher(cache_dir=CACHE, user_agent=UA)
    rows = []
    for ticker in tickers:
        try:
            cik = edgar.ticker_to_cik(ticker, fetcher=fetcher)
            subs = edgar.get_submissions(cik, fetcher=fetcher)
            filings = (edgar.list_filings(subs, forms=("10-K",), limit=1)
                       or edgar.list_filings(subs, forms=("20-F",), limit=1))
            if not filings:
                rows.append((ticker, "NO 10-K/20-F", {}, None)); continue
            filing = filings[0]
            url = edgar.archive_url(cik, filing.accession_number, filing.primary_document)
            html = fetcher.get(url)
            counts, cash_facts = {}, []
            for topic in TOPICS:
                result = extract.extract_topic(html, topic, url)
                counts[topic] = len([f for f in result.facts if f.value is not None])
                if topic == "cash_and_equivalents":
                    cash_facts = result.facts
            truth = xbrl_cash(cik, fetcher)
            check = cross_check(cash_facts, truth)
            rows.append((f"{ticker} {filing.form} {filing.report_date}",
                         subs["name"][:26], counts, check))
        except Exception as exc:
            rows.append((ticker, f"ERROR {type(exc).__name__}: {exc}"[:60], {}, None))
    return rows


def cross_check(cash_facts, truth):
    """Does any extracted cash number equal an XBRL cash number?"""
    if not truth:
        return "no xbrl"
    wanted = {round(v, 1) for v in truth.values()}
    got = set()
    for fact in cash_facts:
        label = (fact.provenance.row_label or "").lower()
        if "cash and cash equivalents" not in label or fact.value is None:
            continue
        factor = scale(fact.value, fact.provenance.units)
        if factor is None:
            continue
        got.add(round(fact.value * factor, 1))
    if not got:
        return "no cash row"
    hits = got & wanted
    return f"MATCH {sorted(hits)[:2]}" if hits else f"MISS got={sorted(got)[:3]}"


if __name__ == "__main__":
    print(f"{'filer':34s} {'company':27s} {'cash':>5s} {'fx':>4s} {'derv':>5s} "
          f"{'scf':>4s} {'pens':>5s}  xbrl cross-check")
    print("-" * 118)
    for name, company, counts, check in run(sys.argv[1:]):
        if not counts:
            print(f"{name:34s} {company}")
            continue
        c = counts
        print(f"{name:34s} {company:27s} {c['cash_and_equivalents']:5d} "
              f"{c['foreign_currency']:4d} {c['derivatives']:5d} "
              f"{c['supply_chain_finance']:4d} {c['pensions']:5d}  {check}")
