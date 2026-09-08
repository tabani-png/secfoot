---
name: sec-footnote-extract
description: Pull treasury numbers (cash composition, FX hedges, derivatives, supply chain finance, pensions) out of ORIGINAL SEC filing documents with full source provenance. Use when asked for footnote-level figures from a 10-K, 10-Q, 8-K, 20-F or 6-K, for treasury benchmarking, or when XBRL/companyfacts values are wrong or missing. Never use XBRL aggregation endpoints for footnote data.
---

# SEC footnote extraction

## The law

**XBRL does not tag footnotes.** `companyfacts`, `companyconcept` and `xbrl/frames`
are aggregation APIs for broad standardised metrics. Using them for cash
composition, FX hedges, supply chain finance or pension detail produces a high
error rate. They are **forbidden** in this workflow.

The submissions endpoint is used for **discovery only** — to learn which
document to download. The numbers always come from the filed document.

**Order matters. Rules first, model second.**
1. Deterministic code finds the filing, the tables and the footnote passages.
2. Only the small extracted result is read by a model.
3. The model returns `not found`. It never infers, estimates or fills a gap.

## Tool

`/Users/tabani/builds/sec-footnote-extractor` — installed package `secfoot`.

```bash
cd /Users/tabani/builds/sec-footnote-extractor
.venv/bin/python -m secfoot.cli \
  --ticker HPQ \
  --topic cash_and_equivalents \
  --form 10-K \
  --user-agent "Jeanmartin research muhammad.a@jeanmartin.com"
```

Flags: `--ticker` or `--cik`, `--topic`, `--form` (default `10-K`),
`--index` (0 = newest), `--user-agent` (required), `--cache`.

Topics: `cash_and_equivalents`, `foreign_currency`, `derivatives`,
`supply_chain_finance`, `pensions`.

Output is JSON: company, cik, form, report_date, filing_date, source_url,
topic, status, sections, facts. Every fact carries a `provenance` block.

## The pipeline

1. **CIK** — `edgar.ticker_to_cik` via `company_tickers.json`, padded to 10 digits.
2. **Submissions** — `https://data.sec.gov/submissions/CIK{cik}.json`.
   Metadata only: form, filing date, accession number, primary document.
3. **Filter** — `edgar.list_filings(subs, forms=("10-K",))`, newest first.
4. **Archive URL** — accession dashes removed, CIK leading zeros stripped:
   `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{primaryDocument}`
5. **Download and cache** — `Fetcher` caches every body to disk, throttles to
   under 10 requests/second, and requires a User-Agent containing a contact email.
   SEC rejects requests without one.
6. **Extract by rule** — headings, tables, row and column labels, units, anchors.
7. **Model reads only the extracted passages.** Never the whole filing.

## Provenance contract

Every number carries all of these, or it is not reported:

`source_url` · `anchor` · `table_title` · `row_label` · `column_label` ·
`period` · `units` · `raw_text`

A table whose columns are not reporting periods is discarded — that is what
stops a table of contents being read as pension data.

## Guardrails — keep these few and non-conflicting

Too many overlapping gates cause validation loops. There are exactly three:

1. **Not found beats a guess.** `status == "not found"` means report nothing.
   Do not substitute an XBRL value, a prior year, or a peer company.
2. **Subtotals must add.** `validate.validate_subtotal(components, total)`
   raises `SubtotalMismatch`. A mismatch is reported, not silently corrected.
3. **Comparatives must be plausible.** `validate.validate_comparative(current, prior)`
   returns False on a move over 10x. Flag it; do not drop it.

If a gate fails, **stop and report the failure with its provenance.** Do not
retry with a different prompt. Retrying is what causes the loop.

## Reporting to the user

Give a table: metric, value, units, period, and the source URL with anchor.
State plainly which metrics came back `not found`. A short honest list beats a
complete-looking one.

## Tests

```bash
cd /Users/tabani/builds/sec-footnote-extractor
.venv/bin/python -m pytest -q              # all, includes live SEC calls
.venv/bin/python -m pytest -q -m "not live"  # offline only
```

Tests are the contract. If you change extraction behaviour, add a failing test
first. `tests/s4_guard/test_no_xbrl_anywhere.py` fails the build if any source
file reaches for an XBRL aggregation endpoint.
