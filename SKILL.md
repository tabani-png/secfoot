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
`--index` (0 = newest), `--route`, `--user-agent` (required), `--cache`.

### Routes — use `reports` unless you have a reason not to

`--route reports` (the default under `auto`) reads the filing's own
FilingSummary.xml and fetches only the two or three small pre-rendered reports
that answer the topic. `--route document` downloads the whole filed document.

Measured over 13 large filers, answering all five topics and counting each file
once: **15.4 MB read via reports versus 49.6 MB via the document**, with 13/13
cash figures agreeing with XBRL. That figure includes `FilingSummary.xml` and,
on the fallback path, `MetaLinks.json`. The document route got IBM wrong (its
balance sheet is not in the primary document at all) and Caterpillar wrong (a
ragged header shifted every segment label).

A report's ShortName IS the footnote's name, so provenance never depends on
guessing which heading sat above a table.

When no report name matches the topic, `edgar.reports_by_tag` reads
`MetaLinks.json` and finds the report by the XBRL element it anchors. GE files
its supplier finance program under "ACCOUNTS PAYABLE - Narrative (Details)",
which no name match can reach. `MetaLinks.json` is 1-3 MB, so this runs only
when name matching finds nothing.

Do NOT put a headless browser (Cloudflare, Playwright) in front of this. SEC
filings are static HTML with no JavaScript; a browser adds cost and latency for
no gain. Use a browser only to spot-check results by eye.

Topics: `cash_and_equivalents`, `foreign_currency`, `derivatives`,
`supply_chain_finance`, `pensions`.

### Foreign filers

`--form 20-F` works. Verified against TM, UL, SAP, NVS and SHEL. IFRS wording
is handled ("Current service cost", "Present value of the DBO").

**A foreign filer does not report in dollars.** Every figure carries its
currency, and a table mixing currencies says its figures are not comparable.
The tool never converts; do not convert on its behalf without saying so.

Output is JSON: company, cik, form, report_date, filing_date, source_url,
topic, status, sections, facts. Every fact carries a `provenance` block.

## The deliverable: a benchmark table

```bash
cd /Users/tabani/builds/sec-footnote-extractor
.venv/bin/python -m secfoot.benchmark_cli \
  --tickers HPQ,CAT,BA,PG,KO \
  --user-agent "Jeanmartin research muhammad.a@jeanmartin.com"
```

One row per metric, one column per company, every number footnoted to its
report URL, table name and row label. `--format json` for the raw rows.

Three outcomes per cell, and only three:

- a number, in its own currency, with the prior year in brackets
- `not found` - the filing does not disclose it. Never substitute anything.
- `ambiguous` - the filing splits that line across plans or segments with no
  total. The value is withheld and every plan is listed with its number under
  Sources. Reporting one plan's number as the company's figure is the failure
  this prevents, and it is the failure that keeps recurring.

A `⚠` on a number means the year-on-year move exceeds 10x. Check it.

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
`period` · `units` · `raw_text` · `dimension` · `currency`

`dimension` is the plan or segment the number belongs to, read from the marker
rows a report page uses (`<tr class="rh">`). `dimension is None` means the
figure is undimensioned, i.e. the company total; only such a figure may stand
for a metric.

A table whose columns are not reporting periods is discarded — that is what
stops a table of contents being read as pension data. A row whose values cannot
be aligned to the columns is skipped and counted, never guessed.

## Guardrails — keep these few and non-conflicting

Too many overlapping gates cause validation loops. There are four, all
automatic, and all of them flag rather than withhold — except the first:

1. **Not found beats a guess.** `status == "not found"` means report nothing.
   Do not substitute an XBRL value, a prior year, or a peer company.
   `ambiguous` means the same: withhold the number, show the split.
2. **Comparatives must be plausible.** A year-on-year move over 10x is flagged.
3. **A rollforward must add up.** `validate.check_rollforward` finds the
   opening and closing rows in the table the number came from, sums every
   movement between them, and flags a mismatch showing the arithmetic:
   `830 + 5,669 - 5,563 = 936, but the filing states 9,999`. The filing's own
   figure is still reported. It returns nothing when the table is not a
   rollforward or when a component could not be read, so it does not fire
   spuriously. Verified silent across HPQ, CAT, KO, PG, WMT, PFE, BA and IBM.
4. **A number must state its currency.** A figure whose page names no currency
   is flagged rather than assumed to be dollars.

A `⚠` on a cell means one of 2-4 fired. The reason is written out in full under
Sources; the legend never says which, because it varies.

`validate.validate_subtotal(components, total)` is still available for a check
you construct by hand.

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

264 tests, 59 of them live against SEC. Tests are the contract: if you change
extraction behaviour, add a failing test first, pinned to the real filing that
exposed the problem.
`tests/s4_guard/test_no_xbrl_anywhere.py` fails the build if any source file
reaches for an XBRL aggregation endpoint.

`KNOWN-GAPS.md` in the repo lists what is verified and what is still open. Read
it before promising coverage.

**Every bug found so far has been the same shape: a label getting lost, so a
right number lands under a wrong heading — segment, plan, year, currency. Never
the arithmetic.** Suspect labels first.
