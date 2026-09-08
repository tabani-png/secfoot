# Known gaps

Checked against the latest 10-K of HPQ, IBM, CAT, GE, WMT, PFE, BA, F, KO,
MSFT, AAPL, PG, LMT.

## Supply chain finance

| filer | discloses? | we return | verdict |
|---|---|---|---|
| HPQ, IBM, CAT, WMT, PFE, BA, F, KO, PG | yes | numbers | correct |
| MSFT, AAPL, LMT | no — no report and no `SupplierFinance*` XBRL tag | `not found` | correct |
| **GE** | **yes** — tags `SupplierFinanceProgramObligationCurrent` in its FY2025 10-K | `not found` | **OPEN GAP** |

GE tags supplier finance inside another footnote and exposes no report whose
ShortName names the program, so report-name matching cannot reach it. A fix
needs report selection by the XBRL tags a report contains, not by its name.

## Pensions

`MSFT` and `AAPL` return nothing. Both run defined-contribution plans only and
file no `DefinedBenefitPlan*` disclosure, so `not found` is correct.

## Route

`--route document` is retained as a fallback but is known to be worse: it
returns nothing for IBM (financial statements are outside the primary
document) and mislabels Caterpillar's segment columns. Prefer `auto`.
