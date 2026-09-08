# Coverage, checked against real filings

Latest 10-K of HPQ, IBM, CAT, GE, WMT, PFE, BA, F, KO, MSFT, AAPL, PG, LMT.
Cash is cross-checked against the XBRL companyfacts endpoint: 13/13 agree.

## Supply chain finance — resolved

| filer | discloses? | we return | verdict |
|---|---|---|---|
| HPQ IBM CAT WMT PFE BA F KO PG | yes | numbers | correct |
| GE | yes, but inside "ACCOUNTS PAYABLE - Narrative (Details)" | numbers, via the tag route | correct |
| MSFT AAPL LMT | no — no report and no `SupplierFinance*` XBRL tag | `not found` | correct |

GE was the last gap. No GE report name mentions the program, so name matching
could never reach it. `MetaLinks.json` records the XBRL element anchoring each
report, so the report is now found by tag when no name matches.

## Pensions

`MSFT` and `AAPL` return nothing. Both run defined-contribution plans only and
file no `DefinedBenefitPlan*` disclosure, so `not found` is correct.

## Route cost and accuracy

Answering all five topics for all thirteen filers, counting each file once:

| route | read | result |
|---|---|---|
| `reports` | **15.4 MB** | 13/13 cash agree with XBRL |
| `document` | 49.6 MB | IBM returns nothing; CAT mislabels segment columns |

`bytes_read` includes `FilingSummary.xml`, and `MetaLinks.json` when the tag
fallback fires. `MetaLinks.json` is large (1-3 MB), which is why it is only
fetched when name matching finds no report.

Use `--route auto` (the default). `--route document` is kept as a fallback and
is known to be worse.

## Dimension names on report pages — resolved

A report page repeats one period header above every plan, and names the plan in
a marker row instead. Those rows are now captured, so a split line is broken
down by plan name:

    Pension service cost (HPQ)
      Non-U.S., Defined Benefit Plans: 39
      U.S., Defined Benefit Plans: 0
      Post-Retirement Benefit Plans: 1

Three things made this harder than it looks, each pinned by a test:

- A marker row is identified by `<tr class="rh">`, not by its text. HP's
  "Post-Retirement Benefit Plans" carries no pipe and reads exactly like the
  sub-heading "Net benefit (credit) cost" above it.
- Which side of the pipe names the plan is not fixed. Caterpillar writes
  "Pension Plan | U.S. Pension Benefits"; HP writes "U.S. | Defined Benefit
  Plans". Keeping either side alone merged HP's two plans into one name, so
  both sides are kept.
- A figure stated above every marker row is undimensioned, and only then is it
  treated as the company total. Before marker rows were captured, HP's
  post-retirement service cost of 1 was being reported as HP's total.

## Foreign filers (20-F, IFRS)

Checked against the latest 20-F of TM, UL, SAP, NVS, SHEL. All five cash
figures agree with the filing: UL, SAP, NVS and SHEL match the XBRL
`ifrs-full` tag; Toyota's prior year matches it exactly and its current year is
not in companyfacts yet, so it was checked against the filed balance sheet
itself (¥12,659,622 / ¥8,982,404).

**Currency is now carried on every figure.** A foreign filer does not report in
dollars, and a table mixing currencies says so and refuses to imply otherwise.
Convert before benchmarking; the tool will not convert for you.

Open:

- Unilever returns `not found` for every pension line. Its report names and row
  labels differ again from SAP's; not yet investigated.
- No 20-F filer returns a supply chain finance figure. Not yet established
  whether they disclose one.
- 10-Q is untested.
