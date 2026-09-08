"""Source-level SEC filing extraction.

Filings are discovered through the submissions endpoint, then the ORIGINAL
filed document is downloaded and parsed. Standardised XBRL aggregation
endpoints are deliberately never used: they do not tag footnotes.
"""
__all__ = ["http", "edgar", "extract", "validate", "provenance"]
