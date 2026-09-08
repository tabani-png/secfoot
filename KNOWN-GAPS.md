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
