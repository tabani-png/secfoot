# secfoot

Treasury figures from **original SEC filing documents**, with provenance.

XBRL aggregation endpoints (`companyfacts`, `companyconcept`, `xbrl/frames`) are
never used: they do not tag footnotes. The submissions endpoint is used only to
discover which document to download.

```bash
python3 -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/python -m secfoot.cli --ticker HPQ --topic pensions \
  --user-agent "Your Name Co you@co.com"
.venv/bin/python -m pytest -q
```

Topics: cash_and_equivalents, foreign_currency, derivatives,
supply_chain_finance, pensions.

Skill: `~/.claude/skills/sec-footnote-extract/SKILL.md`
