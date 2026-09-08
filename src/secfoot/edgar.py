from __future__ import annotations

import json
import re
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


# --- the filing's own pre-rendered reports ---------------------------------
#
# Every inline-XBRL filing ships FilingSummary.xml: one small, clean HTML
# table per statement and per footnote. Fetching the two that matter is far
# cheaper than parsing the whole document, and it reaches statements that some
# filers (IBM, GE) keep out of the primary document entirely.

REPORT_RE = re.compile(r"<Report\b[^>]*>(.*?)</Report>", re.S | re.I)
SHORT_NAME_RE = re.compile(r"<ShortName>(.*?)</ShortName>", re.S | re.I)
HTML_FILE_RE = re.compile(r"<HtmlFileName>(.*?)</HtmlFileName>", re.S | re.I)
DUPLICATE_STUBS = ("(tables)", "(policies)", "(parenthetical)")
# Report short names use a different vocabulary from the footnote prose:
# filers file FX hedging under "Financial Instruments", never "foreign currency".
PRIMARY_STATEMENTS = ("balance sheet", "financial position",
                      "statement of cash flows", "statements of cash flows")
REPORT_HINTS = {
    "cash_and_equivalents": ("balance sheet", "financial position",
                             "statement of cash flows", "cash and cash equivalents",
                             "supplementary financial information"),
    "foreign_currency": ("financial instrument", "hedg", "currency"),
    "derivatives": ("financial instrument", "derivative", "hedg"),
    "supply_chain_finance": ("supplier finance", "supply chain financ",
                             "payables financ", "reverse factoring"),
    "pensions": ("pension", "postretirement", "post-retirement", "retirement",
                 "benefit plan"),
}


@dataclass(frozen=True)
class Report:
    short_name: str
    file_name: str
    url: str


def filing_base_url(cik, accession_number: str) -> str:
    return f"{ARCHIVE_ROOT}/{int(pad_cik(cik))}/{accession_number.replace('-', '')}"


def parse_filing_summary(xml: str, base_url: str) -> list[Report]:
    reports = []
    for block in REPORT_RE.findall(xml):
        name = SHORT_NAME_RE.search(block)
        file_name = HTML_FILE_RE.search(block)
        if not name or not file_name:
            continue
        short_name = name.group(1).strip()
        html_file = file_name.group(1).strip()
        if not short_name or not html_file:
            continue
        reports.append(Report(short_name, html_file, f"{base_url.rstrip('/')}/{html_file}"))
    return reports


def list_reports(cik, accession_number: str, fetcher=None) -> list[Report]:
    if fetcher is None:
        raise ValueError("a Fetcher is required")
    base = filing_base_url(cik, accession_number)
    return parse_filing_summary(fetcher.get(f"{base}/FilingSummary.xml"), base)


def reports_for_topic(reports: list[Report], topic: str) -> list[Report]:
    from .extract import TOPICS

    if topic not in TOPICS:
        raise KeyError(f"unknown topic {topic!r}; known topics: {sorted(TOPICS)}")
    patterns = [re.compile(p, re.I) for p in TOPICS[topic]]
    hints = REPORT_HINTS.get(topic, ())

    matched = []
    for report in reports:
        name = report.short_name
        lowered = name.lower()
        if any(stub in lowered for stub in DUPLICATE_STUBS):
            continue
        if any(p.search(name) for p in patterns) or any(h in lowered for h in hints):
            matched.append(report)

    def rank(report: Report) -> int:
        name = report.short_name.lower()
        if any(h in name for h in PRIMARY_STATEMENTS):
            return 0                       # the primary statement is authoritative
        if "(details)" in name:
            return 1                       # then the reports holding tagged numbers
        return 2

    matched.sort(key=rank)
    return matched


# --- finding a report by the XBRL tags it contains -------------------------
#
# Some filers disclose a treasury item inside a footnote named for something
# else. GE reports its supplier finance program under "ACCOUNTS PAYABLE -
# Narrative (Details)", which no name match can reach. MetaLinks.json ships
# with every inline-XBRL filing and records the XBRL element anchoring each
# report, so the report can be found by tag instead.

TAG_HINTS = {
    "cash_and_equivalents": ("CashAndCashEquivalents", "CashCashEquivalents",
                             "RestrictedCash"),
    "foreign_currency": ("ForeignCurrency", "ForeignExchange",
                         "NotionalAmountOfForeignCurrency"),
    "derivatives": ("Derivative", "Hedg", "NotionalAmount"),
    "supply_chain_finance": ("SupplierFinanceProgram", "SupplyChainFinanc",
                             "ReverseFactoring"),
    "pensions": ("DefinedBenefitPlan", "PensionAndOtherPostretirement",
                 "PensionPlan", "PostretirementBenefit"),
}
ANCHOR_KEYS = ("firstAnchor", "uniqueAnchor")


def parse_metalinks(text: str, base_url: str, topic: str) -> list[Report]:
    if topic not in TAG_HINTS:
        raise KeyError(f"unknown topic {topic!r}; known topics: {sorted(TAG_HINTS)}")
    hints = TAG_HINTS[topic]
    try:
        instances = json.loads(text)["instance"]
    except Exception:
        return []

    matched: dict[str, Report] = {}
    for instance in instances.values():
        for report_id, report in (instance.get("report") or {}).items():
            if not report_id.startswith("R"):
                continue
            names = []
            for key in ANCHOR_KEYS:
                anchor = report.get(key) or {}
                if isinstance(anchor, dict) and anchor.get("name"):
                    names.append(anchor["name"])
            if not any(h.lower() in n.lower() for n in names for h in hints):
                continue
            short_name = (report.get("shortName") or report_id).strip()
            file_name = f"{report_id}.htm"
            matched.setdefault(report_id, Report(
                short_name, file_name, f"{base_url.rstrip('/')}/{file_name}"))
    return list(matched.values())


def reports_by_tag(cik, accession_number: str, topic: str, fetcher=None) -> list[Report]:
    if fetcher is None:
        raise ValueError("a Fetcher is required")
    base = filing_base_url(cik, accession_number)
    try:
        text = fetcher.get(f"{base}/MetaLinks.json")
    except Exception:
        return []
    return parse_metalinks(text, base, topic)
