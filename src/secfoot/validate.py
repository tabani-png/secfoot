"""Arithmetic gates. A number that fails these never leaves the pipeline."""
from __future__ import annotations

import re
from typing import Optional

OPENING = re.compile(r"\b(beginning|opening|start) of\b|^balance,? (at )?beginning", re.I)
CLOSING = re.compile(r"\b(end|close|closing) of\b|^balance,? (at )?end", re.I)


class SubtotalMismatch(Exception):
    pass


def validate_subtotal(components, reported_total, tolerance: float = 0.01) -> bool:
    missing = [i for i, c in enumerate(components) if c is None]
    if missing:
        raise SubtotalMismatch(
            f"cannot check a subtotal with missing components at positions {missing}"
        )
    if reported_total is None:
        raise SubtotalMismatch("cannot check a subtotal against a missing total")
    difference = abs(sum(components) - reported_total)
    if difference > tolerance:
        raise SubtotalMismatch(
            f"components sum to {sum(components)}, filing reports {reported_total} "
            f"(off by {difference})"
        )
    return True


def validate_comparative(current, prior, max_ratio: float = 10.0) -> bool:
    if prior in (None, 0) or current is None:
        return True
    return abs(current / prior) <= max_ratio


def check_rollforward(facts, period: str, tolerance: float = 1.0) -> Optional[str]:
    """Does opening + every movement equal the stated closing?

    Returns None when the table is not a rollforward, when a component could
    not be read, or when it balances. Otherwise returns a sentence showing the
    arithmetic, so a reader can check it by hand. The figure itself is never
    changed or withheld on the strength of this check.
    """
    rows = [f for f in facts if (f.provenance.period or "").strip() == period.strip()]
    if not rows:
        return None

    opening = [f for f in rows if OPENING.search(f.provenance.row_label or "")]
    closing = [f for f in rows if CLOSING.search(f.provenance.row_label or "")]
    if len(opening) != 1 or len(closing) != 1:
        return None

    movements = [f for f in rows if f not in opening and f not in closing]
    if not movements:
        return None
    if any(f.value is None for f in opening + closing + movements):
        # A missing component makes the sum meaningless, so say nothing.
        return None

    computed = opening[0].value + sum(f.value for f in movements)
    stated = closing[0].value
    if abs(computed - stated) <= tolerance:
        return None
    parts = f"{opening[0].value:,.0f}"
    for movement in movements:
        sign = "-" if movement.value < 0 else "+"
        parts += f" {sign} {abs(movement.value):,.0f}"
    return (f"rollforward does not balance: {parts} = {computed:,.0f}, "
            f"but the filing states {stated:,.0f}")
