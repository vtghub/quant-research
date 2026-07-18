"""Shared type aliases. All are plain pandas objects; these names document intent only."""
from __future__ import annotations

import pandas as pd

# Long-format OHLCV: columns = [date, symbol, open, high, low, close, adj_close, volume, source]
LongPriceFrame = pd.DataFrame

# Long-format macro series: columns = [date, series_id, value, source]
LongMacroFrame = pd.DataFrame

# Wide date-indexed frame, columns = symbols. Used for prices, signals, and weights.
WideFrame = pd.DataFrame
