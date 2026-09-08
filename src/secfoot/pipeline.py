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
        # A list of value-less facts is still truthy, so ask for a real number
        # before deciding the reports route answered the question.
        answered = result is not None and (
            any(f.value is not None for f in result[0]) or result[1]
        )
        if result is not None and (route == "reports" or answered):
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
    base = edgar.filing_base_url(cik, filing.accession_number)
    # bytes_read counts the index files too, so the cost of routing is honest.
    read = 0
    index_urls = []
    try:
        summary_url = f"{base}/FilingSummary.xml"
        read += len(fetcher.get(summary_url))
        index_urls.append(summary_url)
        reports = edgar.list_reports(cik, filing.accession_number, fetcher=fetcher)
    except Exception:
        return None
    chosen = edgar.reports_for_topic(reports, topic)[:MAX_REPORTS]
    if not chosen:
        # Some filers put a treasury item in a footnote named for something
        # else, so fall back to matching on the XBRL tags a report anchors.
        try:
            meta_url = f"{base}/MetaLinks.json"
            read += len(fetcher.get(meta_url))
            index_urls.append(meta_url)
        except Exception:
            pass
        chosen = edgar.reports_by_tag(cik, filing.accession_number, topic,
                                      fetcher=fetcher)[:MAX_REPORTS]
    facts, sections, urls = [], [], list(index_urls)
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
