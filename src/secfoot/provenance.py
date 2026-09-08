from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional

NOT_FOUND = "not found"


@dataclass(frozen=True)
class Provenance:
    source_url: str
    anchor: Optional[str]
    table_title: Optional[str]
    row_label: Optional[str]
    column_label: Optional[str]
    period: Optional[str]
    units: Optional[str]
    raw_text: str
    # the plan or segment a report page names in a marker row above the number;
    # None means the figure is undimensioned, i.e. the total
    dimension: Optional[str] = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Fact:
    """One extracted number, always tied to where it came from."""
    value: Optional[float]
    provenance: Provenance

    def as_dict(self) -> dict:
        return {"value": self.value, "provenance": self.provenance.as_dict()}
