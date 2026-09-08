# secfoot — treasury figures from SEC filings, with sources

Pulls cash composition, FX hedges, derivatives, supply chain finance and
pension figures out of the **original filed documents**, and shows where every
number came from.

It is built to be used through **Claude Code**. Install it, then just ask.

---

## Why not the XBRL API

`companyfacts` and the other XBRL endpoints are aggregation APIs. They do not
tag footnotes. Checked against HP Inc.'s FY2025 10-K: of 690 tags HP files,
**not one** is a pension benefit-cost tag. The pension footnote simply is not
there, because those figures are split by plan and the API drops that split.

This tool reads the filing instead.

---

## Install

Needs Python 3.11 or newer. Nothing else.

```bash
./install.sh
```

That creates a virtual environment, installs the package, registers the skill
with Claude Code, and runs the offline tests to prove it works.

Then set your contact address. SEC requires one on every request and rejects
requests without it:

```bash
export SEC_USER_AGENT="Your Name, Your Company you@example.com"
```

Put that line in `~/.zshrc` so it sticks.

---

## Use it

**Through Claude Code (the intended way).** Open Claude Code anywhere and ask:

> Get me HP, Caterpillar and Boeing's supply chain finance and pension figures
> from their latest 10-Ks.

Claude picks up the skill and runs it.

**Directly, if you prefer:**

```bash
.venv/bin/python -m secfoot.benchmark_cli \
  --tickers HPQ,CAT,BA,PG,KO \
  --user-agent "$SEC_USER_AGENT"
```

```
| Metric                      | HPQ             | CAT             |
|-----------------------------|-----------------|-----------------|
| Cash and cash equivalents   | $3,705 ($3,253) | $9,980 ($6,889) |
| Supplier finance obligation | not found       | 936 (830) ⚠     |
| Pension service cost        | ambiguous ⚠     | ambiguous ⚠     |
```

Under the table, every number is footnoted to its source URL, the table it came
from and the row label. Anything marked `⚠` says why, in words.

Foreign filers work too: `--form 20-F`.

---

## What it refuses to do

This matters more than what it does.

**`not found`** — the filing does not disclose it. Nothing is substituted. Not
an XBRL value, not last year's number, not a peer's.

**`ambiguous`** — the filing splits that line across plans or segments and
gives no total. The number is **withheld** and every plan is listed with its
own figure, so you choose. Reporting one plan's number as the company's figure
is the mistake this exists to prevent.

**Currencies are never converted.** A foreign filer reports in its own
currency, the table says so, and it warns that the figures are not comparable.

### Four checks run automatically

| check | what happens |
|---|---|
| Not found / ambiguous | the number is withheld |
| Year-on-year move over 10x | flagged |
| A rollforward must add up | flagged, showing the arithmetic |
| The currency must be stated | flagged |

A flagged number is still shown. A mismatch is reported, never corrected.

---

## Every number is traceable

Ten fields travel with each figure, or it is not reported:

`source_url` · `anchor` · `table_title` · `row_label` · `column_label` ·
`period` · `units` · `raw_text` · `dimension` · `currency`

`dimension` is the plan or segment. `dimension` empty means the figure is a
company total.

---

## Tests

```bash
.venv/bin/python -m pytest -q -m "not live"   # offline, no network
.venv/bin/python -m pytest -q                 # everything, calls SEC
```

264 tests. 53 of them call SEC and are skipped until you set `SEC_USER_AGENT`.

Every test is pinned to a real filing that exposed a real bug. If you change
extraction behaviour, write the failing test first.

---

## Verified, and not

Read **`KNOWN-GAPS.md`**. It records what was actually checked and what was
not. Do not promise coverage beyond it.

Briefly: 13 US filers and 5 foreign filers verified, every cash figure agreeing
with the filing. 10-Q is untested.
