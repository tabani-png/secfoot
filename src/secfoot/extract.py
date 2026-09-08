"""Deterministic, rule-based extraction. No model is consulted here.

Rules find the tables and footnote passages. A model may read the small
extracted result afterwards, never the whole filing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .provenance import NOT_FOUND, Fact, Provenance

TOPICS: dict[str, list[str]] = {
    "cash_and_equivalents": [
        r"cash and cash equivalents", r"cash, cash equivalents",
        r"cash and equivalents", r"restricted cash",
    ],
    "foreign_currency": [
        r"foreign currency", r"foreign exchange", r"currency translation",
    ],
    "derivatives": [
        r"derivative", r"hedg", r"forward contract", r"interest rate swap",
    ],
    "supply_chain_finance": [
        r"supply chain financ", r"supplier financ", r"reverse factoring",
        r"payables financ", r"trade payables program",
    ],
    "pensions": [
        r"pension", r"defined benefit", r"post[- ]?retirement benefit",
        r"other post[- ]?employment",
    ],
}

BLOCK_TAGS = ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li")
HEADING_TAGS = ("b", "strong", "h1", "h2", "h3", "h4", "h5", "h6")
BOLD_STYLE = re.compile(r"font-weight\s*:\s*(bold|[6-9]00)", re.I)
UNITS = [
    (re.compile(r"in\s+billions", re.I), "billions"),
    (re.compile(r"in\s+millions", re.I), "millions"),
    (re.compile(r"in\s+thousands", re.I), "thousands"),
]
BLANKS = {"", "-", "--", "—", "–", "n/a", "na", "nm", "*", "$", "%"}

MAX_SECTION_BLOCKS = 20
MAX_SECTION_CHARS = 6000
HEADING_MAX_CHARS = 250


@dataclass(frozen=True)
class Section:
    heading: str
    text: str
    source_url: str
    anchor: Optional[str] = None


@dataclass(frozen=True)
class Table:
    title: str
    units: str
    column_labels: list[str]
    facts: list[Fact]
    source_url: str
    anchor: Optional[str] = None


@dataclass(frozen=True)
class TopicResult:
    topic: str
    source_url: str
    status: str
    sections: list[Section] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)


def parse_number(text: str):
    """Read a number the way it appears in a filing. Anything else is None."""
    if text is None:
        return None
    cleaned = str(text).strip()
    if cleaned.lower() in BLANKS:
        return None
    # Strip currency and spacing first, so "$ (1,234)" still reads as negative.
    cleaned = cleaned.replace("$", "").replace(",", "").replace("%", "")
    cleaned = cleaned.replace(" ", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    if cleaned.lower() in BLANKS:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _is_heading(node: Tag) -> bool:
    if node.name in HEADING_TAGS:
        return True
    if node.find(HEADING_TAGS) is not None:
        return True
    for descendant in [node, *node.find_all(True, limit=12)]:
        style = descendant.get("style") or ""
        if BOLD_STYLE.search(style) and _text(descendant):
            return True
    return False


def _nearest_anchor(node: Tag) -> Optional[str]:
    current = node
    while current is not None:
        for previous in current.find_all_previous(["a", "div", "span", "p"], limit=40):
            name = previous.get("name") or previous.get("id")
            if name:
                return name
        current = current.parent
        if current is None or current.name in ("body", "[document]", "html"):
            break
    return None


def _units_near(node: Tag) -> str:
    for previous in node.find_all_previous(BLOCK_TAGS, limit=15):
        text = _text(previous)
        for pattern, label in UNITS:
            if pattern.search(text):
                return label
    return "unspecified"


def _title_near(node: Tag) -> str:
    for previous in node.find_all_previous(BLOCK_TAGS, limit=15):
        text = _text(previous)
        if text and len(text) <= HEADING_MAX_CHARS and _is_heading(previous):
            return text
    for previous in node.find_all_previous(BLOCK_TAGS, limit=15):
        text = _text(previous)
        if text:
            return text[:HEADING_MAX_CHARS]
    return "(untitled table)"


def _row_cells(row: Tag) -> list[str]:
    return [_text(cell) for cell in row.find_all(["td", "th"], recursive=False)]


YEAR = re.compile(r"^(19|20)\d{2}$")
MONTHS = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I
)
PERIOD_WORDS = re.compile(r"\b(fiscal|year|quarter|month|q[1-4]|as of|ended)\b", re.I)


def looks_like_period(text: str) -> bool:
    """Column headers such as '2025' are periods, not values."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    return bool(YEAR.match(cleaned) or MONTHS.search(cleaned) or PERIOD_WORDS.search(cleaned))


def _split_header(rows: list[list[str]]):
    """Find the row that names the periods, and return the data rows below it."""
    for index, cells in enumerate(rows):
        tail = [c for c in cells[1:] if c and c not in BLANKS]
        if not tail:
            continue
        if all(parse_number(c) is None or looks_like_period(c) for c in tail):
            return tail, rows[index + 1:]
    return [], rows


def extract_tables(html: str, source_url: str) -> list[Table]:
    tables: list[Table] = []
    for node in _soup(html).find_all("table"):
        rows = [_row_cells(r) for r in node.find_all("tr")]
        rows = [r for r in rows if any(c for c in r)]
        if not rows:
            continue
        column_labels, body = _split_header(rows)
        if not column_labels or not body:
            continue
        title = _title_near(node)
        units = _units_near(node)
        anchor = _nearest_anchor(node)
        facts: list[Fact] = []
        for cells in body:
            if not cells:
                continue
            row_label = cells[0]
            if not row_label:
                continue
            values = [
                c for c in cells[1:]
                if c and c not in BLANKS and parse_number(c) is not None
            ]
            for column_label, raw in zip(column_labels, values):
                facts.append(
                    Fact(
                        value=parse_number(raw),
                        provenance=Provenance(
                            source_url=source_url,
                            anchor=anchor,
                            table_title=title,
                            row_label=row_label,
                            column_label=column_label,
                            period=column_label,
                            units=units,
                            raw_text=raw,
                        ),
                    )
                )
        if not facts:
            continue
        tables.append(
            Table(
                title=title,
                units=units,
                column_labels=column_labels,
                facts=facts,
                source_url=source_url,
                anchor=anchor,
            )
        )
    return tables


def _patterns(topic: str) -> list[re.Pattern]:
    if topic not in TOPICS:
        raise KeyError(f"unknown topic {topic!r}; known topics: {sorted(TOPICS)}")
    return [re.compile(p, re.I) for p in TOPICS[topic]]


def _blocks(soup: BeautifulSoup) -> list[Tag]:
    blocks = []
    for node in soup.find_all(BLOCK_TAGS):
        if node.find(BLOCK_TAGS) is not None:
            continue
        if _text(node):
            blocks.append(node)
    return blocks


def find_sections(html: str, topic: str, source_url: str = "") -> list[Section]:
    patterns = _patterns(topic)
    soup = _soup(html)
    blocks = _blocks(soup)
    headings = [i for i, b in enumerate(blocks) if _is_heading(b)]
    heading_set = set(headings)

    def matches(text: str) -> bool:
        return any(p.search(text) for p in patterns)

    hits = [
        i for i in headings
        if len(_text(blocks[i])) <= HEADING_MAX_CHARS and matches(_text(blocks[i]))
    ]
    if not hits:
        hits = [
            i for i, b in enumerate(blocks)
            if len(_text(b)) <= HEADING_MAX_CHARS and matches(_text(b))
        ]

    sections: list[Section] = []
    for index in hits:
        body_parts: list[str] = []
        for offset in range(index + 1, min(index + 1 + MAX_SECTION_BLOCKS, len(blocks))):
            if offset in heading_set and body_parts:
                break
            body_parts.append(_text(blocks[offset]))
            if sum(len(p) for p in body_parts) > MAX_SECTION_CHARS:
                break
        sections.append(
            Section(
                heading=_text(blocks[index]),
                text=" ".join(body_parts).strip(),
                source_url=source_url,
                anchor=_nearest_anchor(blocks[index]),
            )
        )
    return sections


def extract_topic(html: str, topic: str, source_url: str) -> TopicResult:
    patterns = _patterns(topic)
    sections = find_sections(html, topic, source_url)
    def table_matches(table: Table) -> bool:
        # A treasury number is meaningless without a reporting period, so a
        # table whose columns are not periods (an index, a page list) is dropped.
        if not any(looks_like_period(c) for c in table.column_labels):
            return False
        # A filing often titles a table blandly ("the following table"), so
        # match on the row labels too, not the title alone.
        if any(p.search(table.title) for p in patterns):
            return True
        labels = {f.provenance.row_label or "" for f in table.facts}
        return any(p.search(label) for label in labels for p in patterns)

    tables = [t for t in extract_tables(html, source_url) if table_matches(t)]
    facts = [f for t in tables for f in t.facts]
    status = "found" if (sections or tables) else NOT_FOUND
    return TopicResult(
        topic=topic,
        source_url=source_url,
        status=status,
        sections=sections,
        tables=tables,
        facts=facts,
    )
