"""secfoot: find a filing, read the smallest source that answers the topic."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import extract, pipeline
from .http import Fetcher


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="secfoot")
    ap.add_argument("--ticker")
    ap.add_argument("--cik")
    ap.add_argument("--form", default="10-K")
    ap.add_argument("--topic", required=True, choices=sorted(extract.TOPICS))
    ap.add_argument("--index", type=int, default=0, help="0 = most recent filing")
    ap.add_argument("--route", default="auto", choices=("auto", "reports", "document"),
                    help="auto tries the filing's own reports first, then the document")
    ap.add_argument("--user-agent", required=True, help='e.g. "Name Co name@co.com"')
    ap.add_argument("--cache", default=str(pathlib.Path.home() / ".cache" / "secfoot"))
    ap.add_argument("--max-sections", type=int, default=5)
    args = ap.parse_args(argv)

    fetcher = Fetcher(cache_dir=args.cache, user_agent=args.user_agent)
    result = pipeline.answer(args.cik or args.ticker, args.topic, fetcher,
                             form=args.form, index=args.index, route=args.route)

    print(json.dumps({
        "company": result.company,
        "cik": result.cik,
        "form": result.form,
        "report_date": result.report_date,
        "filing_date": result.filing_date,
        "filing_url": result.filing_url,
        "topic": result.topic,
        "route": result.route,
        "status": result.status,
        "bytes_read": result.bytes_read,
        "sources": result.sources,
        "sections": [
            {"heading": s.heading, "anchor": s.anchor, "text": s.text[:4000]}
            for s in result.sections[:args.max_sections]
        ],
        "facts": [f.as_dict() for f in result.facts],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
