# secfoot, build notes for Claude Code

What this is: treasury figures from ORIGINAL SEC filings with full provenance. Never XBRL
aggregation endpoints for footnote data. Read README.md and SKILL.md first. Harness rules in
`~/builds/CLAUDE.md` apply.

Client context lives in `context/` (symlinks, gitignored, never committed). The person this is
being built for is a treasury consultant who will stress test it and send a failure log.

Done when: the failure log comes back and every wrong case is either fixed with a pinned test or
recorded in KNOWN-GAPS.md with the reason.

Rules that already hold, keep them:
- Deterministic code finds the filing and the passage. The model reads only the extracted
  result and may answer `not found`. It never infers or fills a gap.
- Every number carries filing, report page and row.
- Run offline tests before any claim: `PYTHONPATH=. .venv/bin/python -m pytest -q -m "not live"`
  (205 pass as of 2026-09-12). Live tests need `SEC_USER_AGENT`.

Open work: see `context/client/OPEN-GATES.md`.
