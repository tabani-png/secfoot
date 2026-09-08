"""Reports route vs whole-document route: coverage and bytes read."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from secfoot import edgar, pipeline
from secfoot.http import Fetcher

UA = "Jeanmartin research muhammad.a@jeanmartin.com"
CACHE = pathlib.Path(__file__).resolve().parents[1] / ".cache"
TOPICS = ["cash_and_equivalents", "foreign_currency", "derivatives",
          "supply_chain_finance", "pensions"]


CASH_TAGS = ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]


def xbrl_cash(cik, fetcher):
    """Recent cash figures from every cash tag the filer actually uses.

    Some filers (GE) stopped using CashAndCashEquivalentsAtCarryingValue years
    ago, so taking the first tag alone returns stale values.
    """
    try:
        gaap = json.loads(fetcher.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"))["facts"]["us-gaap"]
    except Exception:
        return set()
    seen = {}
    for tag in CASH_TAGS:
        for u in gaap.get(tag, {}).get("units", {}).get("USD", []):
            if u.get("form") == "10-K":
                seen.setdefault(u["end"], set()).add(round(u["val"] / 1e6, 1))
    recent = sorted(seen)[-3:]
    return {v for end in recent for v in seen[end]}


def cash_check(facts, truth):
    if not truth:
        return "no xbrl"
    scale = {"millions": 1.0, "thousands": 1e-3, "billions": 1e3}
    got = {round(f.value * scale[f.provenance.units], 1) for f in facts
           if f.value is not None and f.provenance.units in scale
           and f.provenance.row_label.lower().startswith("cash")}
    if not got:
        return "no cash row"
    return "MATCH" if got & truth else f"MISS {sorted(got)[:2]}"


def main(tickers):
    fetcher = Fetcher(cache_dir=CACHE, user_agent=UA)
    print(f"{'ticker':7s} {'route':9s} {'MB read':>8s} {'cash':>5s} {'fx':>4s} "
          f"{'derv':>5s} {'scf':>4s} {'pens':>5s}  cash vs XBRL")
    print("-" * 84)
    totals = {"reports": 0, "document": 0}
    for ticker in tickers:
        for route in ("reports", "document"):
            try:
                counts, cash_facts, fetched = {}, [], set()
                for topic in TOPICS:
                    a = pipeline.answer(ticker, topic, fetcher, route=route)
                    counts[topic] = len([f for f in a.facts if f.value is not None])
                    fetched |= set(a.sources)
                    if topic == "cash_and_equivalents":
                        cash_facts = a.facts
                        cik = a.cik
                # count each file once: answering five topics reuses the index
                read = sum(len(fetcher.get(u)) for u in fetched)
                totals[route] += read
                c = counts
                print(f"{ticker:7s} {route:9s} {read/1e6:8.2f} {c['cash_and_equivalents']:5d} "
                      f"{c['foreign_currency']:4d} {c['derivatives']:5d} "
                      f"{c['supply_chain_finance']:4d} {c['pensions']:5d}  "
                      f"{cash_check(cash_facts, xbrl_cash(cik, fetcher))}")
            except Exception as exc:
                print(f"{ticker:7s} {route:9s} ERROR {type(exc).__name__}: {exc}"[:80])
        print()
    print(f"TOTAL bytes read  reports={totals['reports']/1e6:.1f}MB  "
          f"document={totals['document']/1e6:.1f}MB")


if __name__ == "__main__":
    main(sys.argv[1:])
