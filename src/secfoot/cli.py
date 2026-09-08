"""secfoot: find a filing, download the original document, extract a topic."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import edgar, extract
from .provenance import NOT_FOUND


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="secfoot")
    ap.add_argument("--ticker")
    ap.add_argument("--cik")
    ap.add_argument("--form", default="10-K")
    ap.add_argument("--topic", required=True, choices=sorted(extract.TOPICS))
    ap.add_argument("--index", type=int, default=0, help="0 = most recent filing")
    ap.add_argument("--user-agent", required=True, help='e.g. "Name Co name@co.com"')
    ap.add_argument("--cache", default=str(pathlib.Path.home() / ".cache" / "secfoot"))
    ap.add_argument("--max-sections", type=int, default=5)
    args = ap.parse_args(argv)

    from .http import Fetcher
    fetcher = Fetcher(cache_dir=args.cache, user_agent=args.user_agent)

    cik = args.cik or edgar.ticker_to_cik(args.ticker, fetcher=fetcher)
    cik = edgar.pad_cik(cik)
    subs = edgar.get_submissions(cik, fetcher=fetcher)
    filings = edgar.list_filings(subs, forms=(args.form,))
    if not filings:
        print(json.dumps({"status": NOT_FOUND, "reason": f"no {args.form} on file"}))
        return 1
    filing = filings[args.index]
    url = edgar.archive_url(cik, filing.accession_number, filing.primary_document)
    result = extract.extract_topic(fetcher.get(url), args.topic, url)

    print(json.dumps({
        "company": subs.get("name"),
        "cik": cik,
        "form": filing.form,
        "report_date": filing.report_date,
        "filing_date": filing.filing_date,
        "source_url": url,
        "topic": result.topic,
        "status": result.status,
        "sections": [
            {"heading": s.heading, "anchor": s.anchor, "text": s.text[:4000]}
            for s in result.sections[:args.max_sections]
        ],
        "facts": [f.as_dict() for f in result.facts],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
