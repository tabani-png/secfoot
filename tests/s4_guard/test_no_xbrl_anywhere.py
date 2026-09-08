"""AC4b: the whole point. This package must never reach for XBRL aggregates."""
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "secfoot"
BANNED = ["companyfacts", "companyconcept", "xbrl/frames", "api/xbrl"]


def test_no_source_file_references_an_xbrl_aggregation_endpoint():
    offenders = []
    for path in SRC.rglob("*.py"):
        body = path.read_text().lower()
        for banned in BANNED:
            if banned in body:
                offenders.append(f"{path.name}: {banned}")
    assert offenders == [], f"XBRL aggregation endpoints are forbidden: {offenders}"
