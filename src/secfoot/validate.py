"""Arithmetic gates. A number that fails these never leaves the pipeline."""
from __future__ import annotations


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
