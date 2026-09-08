"""Route a topic to the cheapest source that still answers it."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import edgar, extract
from .provenance import NOT_FOUND, Fact

MAX_REPORTS = 4


@dataclass
class Answer:
    company: str
    cik: str
    form: str
    report_date: str
    filing_date: str
    filing_url: str
    topic: str
    route: str
    status: str
    bytes_read: int = 0
    sources: list[str] = field(default_factory=list)
    sections: list = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)


def answer(ticker_or_cik, topic: str, fetcher, form: str = "10-K",
           index: int = 0, route: str = "auto") -> Answer:
    cik = (ticker_or_cik if str(ticker_or_cik).strip().isdigit()
           else edgar.ticker_to_cik(ticker_or_cik, fetcher=fetcher))
    cik = edgar.pad_cik(cik)
    subs = edgar.get_submissions(cik, fetcher=fetcher)
    filings = edgar.list_filings(subs, forms=(form,))
    if not filings:
        raise LookupError(f"no {form} on file for CIK {cik}")
    filing = filings[index]
    filing_url = edgar.archive_url(cik, filing.accession_number, filing.primary_document)

    base = dict(company=subs.get("name", ""), cik=cik, form=filing.form,
                report_date=filing.report_date, filing_date=filing.filing_date,
                filing_url=filing_url, topic=topic)

    if route in ("auto", "reports"):
        result = _from_reports(cik, filing, topic, fetcher)
        if result is not None and (route == "reports" or result[0]):
            facts, sections, read, urls = result
            return Answer(**base, route="reports",
                          status="found" if (facts or sections) else NOT_FOUND,
                          bytes_read=read, sources=urls, sections=sections, facts=facts)

    html = fetcher.get(filing_url)
    topic_result = extract.extract_topic(html, topic, filing_url)
    return Answer(**base, route="document", status=topic_result.status,
                  bytes_read=len(html), sources=[filing_url],
                  sections=topic_result.sections, facts=topic_result.facts)


def _from_reports(cik, filing, topic, fetcher):
    try:
        reports = edgar.list_reports(cik, filing.accession_number, fetcher=fetcher)
    except Exception:
        return None
    chosen = edgar.reports_for_topic(reports, topic)[:MAX_REPORTS]
    facts, sections, read, urls = [], [], 0, []
    for report in chosen:
        try:
            html = fetcher.get(report.url)
        except Exception:
            continue
        read += len(html)
        urls.append(report.url)
        # The report's own name IS the footnote's name, so the title never
        # has to be guessed from nearby headings.
        tables = extract.extract_tables(html, report.url)
        for table in tables:
            facts += [_retitle(f, report.short_name) for f in table.facts]
        sections += extract.find_sections(html, topic, report.url)
    return facts, sections, read, urls


def _retitle(fact: Fact, report_name: str) -> Fact:
    return replace(fact, provenance=replace(fact.provenance, table_title=report_name))
