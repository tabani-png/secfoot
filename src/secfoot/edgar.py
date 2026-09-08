from __future__ import annotations

import json
from dataclasses import dataclass

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_ROOT = "https://www.sec.gov/Archives/edgar/data"


@dataclass(frozen=True)
class Filing:
    form: str
    accession_number: str
    primary_document: str
    report_date: str
    filing_date: str
    cik: str


def pad_cik(cik) -> str:
    raw = str(cik).strip().upper()
    if raw.startswith("CIK"):
        raw = raw[3:]
    raw = raw.lstrip().rstrip()
    if not raw.isdigit():
        raise ValueError(f"CIK must be digits, got {cik!r}")
    if len(raw.lstrip("0")) > 10 or len(raw) > 10:
        raise ValueError(f"CIK is longer than 10 digits: {cik!r}")
    return raw.zfill(10)


def ticker_to_cik(ticker: str, fetcher=None) -> str:
    if fetcher is None:
        raise ValueError("a Fetcher is required")
    wanted = ticker.strip().upper()
    for entry in json.loads(fetcher.get(TICKER_MAP_URL)).values():
        if entry["ticker"].upper() == wanted:
            return pad_cik(entry["cik_str"])
    raise LookupError(f"no CIK found for ticker {ticker!r}")


def get_submissions(cik, fetcher=None) -> dict:
    if fetcher is None:
        raise ValueError("a Fetcher is required")
    return json.loads(fetcher.get(SUBMISSIONS_URL.format(cik=pad_cik(cik))))


def list_filings(submissions: dict, forms=("10-K",), limit=None):
    wanted = {f.upper() for f in forms}
    recent = submissions["filings"]["recent"]
    cik = pad_cik(submissions["cik"])
    rows = zip(
        recent["form"],
        recent["accessionNumber"],
        recent["primaryDocument"],
        recent["reportDate"],
        recent["filingDate"],
    )
    filings = [
        Filing(form, accession, document, report_date, filing_date, cik)
        for form, accession, document, report_date, filing_date in rows
        if form.upper() in wanted
    ]
    filings.sort(key=lambda f: f.filing_date, reverse=True)
    return filings[:limit] if limit else filings


def archive_url(cik, accession_number: str, primary_document: str) -> str:
    trimmed_cik = int(pad_cik(cik))
    accession = accession_number.replace("-", "")
    return f"{ARCHIVE_ROOT}/{trimmed_cik}/{accession}/{primary_document}"
