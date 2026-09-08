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

BOILERPLATE = re.compile(
    r"^(table of contents"
    r"|notes to (the )?consolidated financial statements.*"
    r"|index( to financial statements)?"
    r"|\d{1,3})$",
    re.I,
)
TITLE_SEARCH_LIMIT = 60
SECTION_TABLE_WINDOW = 15

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
    skipped_rows: int = 0


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
    """The nearest real heading above a table, ignoring running page headers."""
    previous_blocks = node.find_all_previous(BLOCK_TAGS, limit=TITLE_SEARCH_LIMIT)
    for previous in previous_blocks:
        text = _text(previous)
        if not text or len(text) > HEADING_MAX_CHARS:
            continue
        if BOILERPLATE.match(text):
            continue
        if _is_heading(previous):
            return text
    for previous in previous_blocks:
        text = _text(previous)
        if text and not BOILERPLATE.match(text):
            return text[:HEADING_MAX_CHARS]
    return "(untitled table)"


YEAR = re.compile(r"^(19|20)\d{2}$")
MONTHS = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I)
PERIOD_WORDS = re.compile(r"\b(fiscal|year|quarter|month|q[1-4]|as of|ended)\b", re.I)
SPACERS = {"", "$", "%", "(", ")"}


def looks_like_period(text: str) -> bool:
    """Column headers such as '2025' or 'As of October 31' are periods, not values."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    return bool(
        YEAR.match(cleaned) or MONTHS.search(cleaned) or PERIOD_WORDS.search(cleaned)
    )


def _row_cells(row: Tag) -> list[tuple[str, int]]:
    """Cell text with its colspan, so stacked headers can be lined up."""
    cells = []
    for cell in row.find_all(["td", "th"], recursive=False):
        try:
            span = max(1, int(cell.get("colspan", 1)))
        except (TypeError, ValueError):
            span = 1
        cells.append((_text(cell), span))
    return cells


def _expand(cells: list[tuple[str, int]]) -> list[str]:
    out = []
    for text, span in cells:
        out.extend([text] * span)
    return out


def _is_header_row(cells: list[tuple[str, int]]) -> bool:
    tail = [c for c, _ in cells[1:] if c and c not in SPACERS]
    if not tail:
        return False
    return all(parse_number(c) is None or looks_like_period(c) for c in tail)


def _collapse(labels: list[str]) -> list[str]:
    """Merge adjacent identical labels created by colspan padding."""
    out: list[str] = []
    for label in labels:
        if not out or out[-1] != label:
            out.append(label)
    return out


def _units_of(text: str) -> Optional[str]:
    for pattern, label in UNITS:
        if pattern.search(text):
            return label
    return None


def _build_column_labels(header_rows: list[list[tuple[str, int]]]):
    """Turn stacked header rows into one label per real data column.

    Returns (labels, units). A tier that only states the units ("In millions")
    is stripped out and reported separately. Columns that are blank in a tier
    which most columns fill are spacer columns, and are dropped.
    """
    tiers = [_expand(row[1:]) for row in header_rows]
    tiers = [tier for tier in tiers if tier]
    if not tiers:
        return [], None

    units = None
    kept_tiers = []
    for tier in tiers:
        texts = [c for c in tier if c]
        found = next((_units_of(c) for c in texts if _units_of(c)), None)
        if found and not any(looks_like_period(c) for c in texts):
            units = units or found
            continue
        kept_tiers.append(tier)
    if not kept_tiers:
        return [], units

    width = max(len(tier) for tier in kept_tiers)
    padded = [tier + [""] * (width - len(tier)) for tier in kept_tiers]

    keep = [True] * width
    for tier in padded:
        filled = sum(1 for c in tier if c and c not in SPACERS)
        if filled * 2 <= width:      # a sparse tier is decoration, not structure
            continue
        for index, cell in enumerate(tier):
            if not cell or cell in SPACERS:
                keep[index] = False

    composites = []
    for index in range(width):
        if not keep[index]:
            continue
        parts = []
        for tier in padded:
            piece = tier[index]
            if piece and piece not in SPACERS and piece not in parts:
                parts.append(piece)
        if parts:
            composites.append(", ".join(parts))
    return _collapse(composites), units


def _data_values(cells: list[tuple[str, int]]) -> list[str]:
    """Drop currency and spacing cells but KEEP dashes: they hold a column."""
    return [c for c, _ in cells[1:] if c not in SPACERS]


def _split_header(rows: list[list[tuple[str, int]]]):
    """Consume every stacked header row, then return the data rows below."""
    header_rows: list[list[tuple[str, int]]] = []
    for index, cells in enumerate(rows):
        if _is_header_row(cells):
            header_rows.append(cells)
            continue
        if header_rows:
            labels, units = _build_column_labels(header_rows)
            return labels, units, rows[index:]
    return [], None, []


def _table_from_node(node: Tag, source_url: str) -> Optional[Table]:
        rows = [_row_cells(r) for r in node.find_all("tr")]
        rows = [r for r in rows if any(c for c, _ in r)]
        if not rows:
            return None
        column_labels, header_units, body = _split_header(rows)
        if not column_labels or not body:
            return None
        title = _title_near(node)
        units = header_units or _units_near(node)
        anchor = _nearest_anchor(node)
        facts: list[Fact] = []
        skipped = 0
        for cells in body:
            if not cells:
                continue
            row_label = cells[0][0]
            if not row_label:
                continue
            values = _data_values(cells)
            if not values:
                continue
            if len(values) != len(column_labels):
                # A number placed under the wrong period is worse than no
                # number at all, so an unalignable row is dropped and counted.
                skipped += 1
                continue
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
            return None
        return Table(
            title=title,
            units=units,
            column_labels=column_labels,
            facts=facts,
            source_url=source_url,
            anchor=anchor,
            skipped_rows=skipped,
        )


def extract_tables(html: str, source_url: str) -> list[Table]:
    return [
        table
        for table in (
            _table_from_node(node, source_url)
            for node in _soup(html).find_all("table")
        )
        if table is not None
    ]


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


def _tables_under_matched_headings(soup, patterns, source_url) -> list[Table]:
    """Tables that sit between a heading naming the topic and the next heading.

    A rollforward table often names the topic nowhere inside itself; the only
    thing identifying it is the footnote heading above it.
    """
    ordered = []
    for node in soup.find_all(BLOCK_TAGS + ("table",)):
        if node.name == "table":
            ordered.append(("table", node))
            continue
        if node.find(BLOCK_TAGS) is not None or not _text(node):
            continue
        ordered.append(("heading" if _is_heading(node) else "block", node))

    starts = [
        index for index, (kind, node) in enumerate(ordered)
        if kind != "table"
        and len(_text(node)) <= HEADING_MAX_CHARS
        and not BOILERPLATE.match(_text(node))
        and any(pattern.search(_text(node)) for pattern in patterns)
    ]
    styled = [i for i in starts if ordered[i][0] == "heading"]
    # Many filers style footnote headings with a CSS class the parser cannot
    # see, so fall back to any short block naming the topic.
    starts = styled or starts

    tables: list[Table] = []
    seen_nodes: set[int] = set()
    for start in starts:
        for index in range(start + 1, min(start + 1 + SECTION_TABLE_WINDOW, len(ordered))):
            kind, node = ordered[index]
            if kind == "heading":
                break
            if kind != "table":
                continue
            if id(node) in seen_nodes:
                continue
            seen_nodes.add(id(node))
            table = _table_from_node(node, source_url)
            if table is not None:
                tables.append(table)
    return tables


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

    soup = _soup(html)
    tables = [
        table
        for table in (
            _table_from_node(node, source_url) for node in soup.find_all("table")
        )
        if table is not None and table_matches(table)
    ]
    seen = {(t.title, t.column_labels and t.column_labels[0],
             t.facts[0].provenance.row_label) for t in tables}
    for table in _tables_under_matched_headings(soup, patterns, source_url):
        key = (table.title, table.column_labels and table.column_labels[0],
               table.facts[0].provenance.row_label)
        if key not in seen and any(looks_like_period(c) for c in table.column_labels):
            seen.add(key)
            tables.append(table)
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
