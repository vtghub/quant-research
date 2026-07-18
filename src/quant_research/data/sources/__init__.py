"""Importing this package registers every built-in data source into DATA_SOURCE_REGISTRY
/ MACRO_SOURCE_REGISTRY. Add a new source by creating a module here and importing it below."""
from quant_research.data.sources import yfinance_source  # noqa: F401
