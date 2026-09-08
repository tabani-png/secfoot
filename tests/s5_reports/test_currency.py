"""AC15: a foreign filer reports in its own currency, and saying otherwise is
a wrong number.

Unilever's balance sheet header reads "EUR (€) € in Millions"; HP's reads
"USD ($) $ in Millions". Printing €3,941m under a "$ millions" heading is the
most dangerous failure available: the figure looks right and is not.
"""
from secfoot import extract

SOURCE = "https://www.sec.gov/Archives/edgar/data/217410/x/R8.htm"


def page(header, value="3,941"):
    return f"""
    <html><body><table class="report">
      <tr><th class="tl">{header}</th><th colspan="2">Dec. 31, 2025</th></tr>
      <tr><th>Dec. 31, 2025</th><th>Dec. 31, 2024</th></tr>
      <tr class="re"><td class="pl">Cash and cash equivalents</td>
          <td class="nump">{value}</td><td class="nump">6,136</td></tr>
    </table></body></html>"""


def _table(header):
    return extract.extract_tables(page(header), SOURCE)[0]


def test_a_euro_filing_is_recorded_as_euros():
    assert _table("Consolidated balance sheet - EUR (€) € in Millions").currency == "EUR"


def test_a_dollar_filing_is_recorded_as_dollars():
    assert _table("Consolidated Balance Sheets - USD ($) $ in Millions").currency == "USD"


def test_a_yen_filing_is_recorded_as_yen():
    assert _table("Consolidated balance sheet - JPY (¥) ¥ in Millions").currency == "JPY"


def test_a_sterling_filing_is_recorded_as_sterling():
    assert _table("Balance sheet - GBP (£) £ in Millions").currency == "GBP"


def test_a_header_stating_no_currency_leaves_it_unknown():
    assert _table("Consolidated balance sheet").currency is None


def test_the_currency_travels_onto_every_fact():
    facts = _table("Consolidated balance sheet - EUR (€) € in Millions").facts
    assert facts
    assert all(f.provenance.currency == "EUR" for f in facts)


def test_units_are_still_read_from_the_same_header():
    table = _table("Consolidated balance sheet - EUR (€) € in Millions")
    assert table.units == "millions"


def test_a_share_denominated_header_does_not_confuse_the_currency():
    table = _table("Events after the balance sheet date (Details) "
                   "€ / shares in Units, € in Millions")
    assert table.currency == "EUR"
