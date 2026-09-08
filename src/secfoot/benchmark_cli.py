"""secfoot-benchmark: one treasury comparison table, every number traceable."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import benchmark
from .http import Fetcher


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="secfoot-benchmark")
    ap.add_argument("--tickers", required=True, help="comma separated, e.g. HPQ,IBM,CAT")
    ap.add_argument("--form", default="10-K")
    ap.add_argument("--route", default="auto", choices=("auto", "reports", "document"))
    ap.add_argument("--metrics",
                    help="comma separated; default is all. Choices: "
                         + ", ".join(benchmark.METRICS))
    ap.add_argument("--format", default="markdown", choices=("markdown", "json"))
    ap.add_argument("--user-agent", required=True)
    ap.add_argument("--cache", default=str(pathlib.Path.home() / ".cache" / "secfoot"))
    args = ap.parse_args(argv)

    fetcher = Fetcher(cache_dir=args.cache, user_agent=args.user_agent)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    metrics = [m.strip() for m in args.metrics.split(",")] if args.metrics else None
    unknown = [m for m in (metrics or []) if m not in benchmark.METRICS]
    if unknown:
        ap.error("unknown metric(s): " + ", ".join(unknown)
                 + "\nknown metrics: " + ", ".join(benchmark.METRICS))
    table = benchmark.run(tickers, fetcher, form=args.form, route=args.route,
                          metrics=metrics)

    if args.format == "json":
        print(json.dumps({c: [r.__dict__ for r in rows] for c, rows in table.items()},
                         indent=2))
    else:
        print(benchmark.render_markdown(table))
    return 0


if __name__ == "__main__":
    sys.exit(main())
