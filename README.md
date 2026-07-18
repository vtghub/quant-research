# quant-research

A modular, hook-driven engine for quantitative trading research on **free data
only** -- fetch, cache, compute signals, screen them statistically, combine
them into strategies, and backtest, all wired together by a single YAML
config. New data sources, signals, strategies, and cross-cutting extensions
(logging, data-quality gates, alerting) are added by writing one file and
registering it -- no core code changes required.

## Why this exists

Finding a useful trading signal is a research problem before it's a backtest
problem. This engine treats them as two distinct stages:

1. **Research** (`quant-research research config.yaml`): fetch data, compute
   signals, and run **information coefficient (IC) analysis** -- does this
   signal actually predict forward returns, at what horizon, with what
   decay? This is cheap and requires no strategy or backtest.
2. **Backtest** (`quant-research backtest config.yaml`): everything above,
   plus turning a signal into portfolio weights (a `Strategy`), running it
   through a vectorized backtest with transaction costs, and producing a
   markdown + PNG tearsheet.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,fred]"   # dev = pytest; fred = optional FRED macro data support
```

Requires Python >= 3.11. `fredapi` (the `fred` extra) is only needed if you
use the FRED macro data source -- its absence never breaks the base install.

## Quickstart

```bash
# validate a config without fetching anything
quant-research validate-config configs/example_multi_asset.yaml

# see every registered data source / signal / strategy
quant-research list-registry

# IC screening only (fetch -> signals -> IC analysis)
quant-research research configs/example_multi_asset.yaml

# full pipeline: fetch -> signals -> IC -> strategy -> backtest -> tearsheet
export FRED_API_KEY=your_free_key   # https://fred.stlouisfed.org/docs/api/api_key.html
quant-research backtest configs/example_multi_asset.yaml
```

The example config trades a mixed ETF + crypto universe (`SPY`, `QQQ`, `TLT`,
`GLD`, `BTC-USD`, `ETH-USD`) via yfinance, overlays a FRED Fed Funds Rate
regime signal, blends momentum + mean-reversion + realized-vol into one
composite score, and produces `reports/example_multi_asset/tearsheet.md`.

## Architecture

Two distinct extension mechanisms:

- **Registry** (`core/registry.py`, singletons in `core/registries.py`) swaps
  *implementations* by name -- data sources, cache backends, signals,
  strategies -- resolved from config strings like `primary_source: yfinance`.
  New capability = new file + one `@REGISTRY.register("name")` decorator.
- **Hooks** (`core/hooks.py`) is an event bus
  (`before_fetch` / `after_fetch` / `before_signal` / `after_signal` /
  `before_backtest` / `after_backtest` / `before_report` / `after_report`) for
  cross-cutting concerns that *observe* the pipeline rather than replace its
  logic -- logging, data-quality gates, alerting. A hook can raise
  `HookAbort` to deliberately halt a run; any other exception is caught and
  logged so one broken observer can't take down the pipeline.

```
src/quant_research/
  core/        registry.py, registries.py (singletons), hooks.py, exceptions.py
  config/      schema.py (pydantic models), loader.py
  cache/       base.py (CacheBackend ABC), parquet_backend.py
  data/        base.py (OHLCVDataSource / MacroDataSource ABCs), access.py (cache-through fetch)
               sources/yfinance_source.py, stooq_source.py, coingecko_source.py, fred_source.py
  signals/     base.py (Signal ABC), pipeline.py (dependency-ordered compute)
               library/momentum.py, rsi.py, macd.py, bollinger.py, mean_reversion.py,
                       realized_vol.py, cross_sectional_rank.py, macro_overlay.py, composite.py
  research/    forward_returns.py, ic_analysis.py (IC, decile spreads, signal decay)
  strategy/    base.py (Strategy ABC), vol_target.py
               library/rank_weighted.py, top_bottom_decile.py
  backtest/    costs.py, metrics.py, rebalance.py, engine.py (the lookahead-protection boundary)
  pipeline/    orchestrator.py (assembles everything from a PipelineConfig), results.py
  hooks/builtin/ logging_hooks.py, data_quality_hooks.py
  report/      plots.py, tearsheet.py
  cli/         main.py (typer app)
```

### Data sources (all free)

| Source | Covers | Key required? | Role |
|---|---|---|---|
| `yfinance` | Equities, ETFs, FX, **and crypto** (`BTC-USD` etc.) | No | Primary, for all asset classes |
| `stooq` | Equities/ETFs | No | Cross-check/fallback only (see caveats below) |
| `coingecko` | Crypto | No | Second crypto vendor, cross-check only |
| `fred` | Macro series (rates, CPI, ...) | Yes, free | Macro overlay input |

### Signals (all hand-rolled on pandas/numpy -- no `ta`/`pandas-ta` dependency)

`momentum`, `rsi`, `macd`, `bollinger_z`, `zscore_meanrev`, `realized_vol`,
`xs_rank` (cross-sectional rank of an upstream signal), `macro_overlay`
(broadcasts a macro regime score across the universe), and `composite`
(blends multiple signals' per-date cross-sectional z-scores into one
multi-factor score, via `depends_on`).

### Strategies

`rank_weighted_long_short` (percentile-rank-weighted long/short, dollar
neutral), `top_bottom_decile_ew` (simpler equal-weight top/bottom decile),
`vol_targeted` (wraps any other registered strategy by name and rescales to
a target annualized volatility -- strategies composing other registry
entries, not just signals).

## Adding a new piece

**Data source**: subclass `OHLCVDataSource` (or `MacroDataSource`) in a new
file under `data/sources/`, decorate the class with
`@DATA_SOURCE_REGISTRY.register("my_source")`, and add it to the imports in
`data/sources/__init__.py`. Reference it from config as `primary_source:
my_source`.

**Signal**: subclass `Signal` in `signals/library/`, decorate with
`@SIGNAL_REGISTRY.register("my_signal")`, import it in
`signals/library/__init__.py`. Reference it in config under `signals:`.

**Strategy**: subclass `Strategy` in `strategy/library/`, decorate with
`@STRATEGY_REGISTRY.register("my_strategy")`, import it in
`strategy/library/__init__.py`.

**Hook**: write a module exposing `def register(hooks: HookManager) -> None`
that calls `hooks.on(HookEvent.X)` or `hooks.register(...)`. List its dotted
path under `hooks.modules` in config -- no code changes to the pipeline
itself.

## Config

See `configs/example_multi_asset.yaml` for a complete example. Shape:

```yaml
name: my_pipeline
universe: { symbols: [...], start: ..., end: ..., primary_source: yfinance, fallback_sources: [stooq] }
macro: { series_ids: [FEDFUNDS], source: fred }              # optional
cache: { backend: parquet, root_dir: .cache/quant_research }
signals:
  - { name: momentum, alias: mom, params: { lookback: 126 } }
  - { name: composite, alias: combo, depends_on: [mom, ...], params: { weights: {...} } }
ic_analysis: { enabled: true, horizons: [1, 5, 21, 63], n_quantiles: 5 }
strategy: { name: rank_weighted_long_short, signals: [combo], params: {...} }
backtest: { initial_capital: 1000000, cost_model: { bps_per_trade: 5.0 }, rebalance: weekly }
report: { output_dir: reports/my_pipeline, formats: [markdown, png] }
hooks: { modules: [quant_research.hooks.builtin.logging_hooks] }
```

## Testing

```bash
pytest                 # everything runs offline against synthetic/mocked data
pytest -m network       # (none currently marked; reserved for opt-in live-vendor tests)
```

145+ unit/integration tests, all deterministic and network-free -- including
a dedicated cross-check (`tests/unit/test_lookahead_convention.py`) proving
`BacktestEngine`'s weight-shift and `research/forward_returns`'s t -> t+1
convention can never silently drift apart.

## Known limitations (also printed in every tearsheet)

- **Calendar alignment (MVP simplification)**: crypto (24/7) and macro
  (monthly/quarterly) series are forward-filled onto the equity/ETF trading
  calendar rather than modeled with full 24/7 precision.
- **Cross-check sources aren't drop-in substitutes**: Stooq's and
  CoinGecko's dividend/adjustment methodology isn't guaranteed to match
  yfinance's `adj_close`; treat them as validation sources, not
  interchangeable primaries.
- **`adj_close` isn't immutable**: past dividend-adjusted prices can change
  retroactively as new dividends are declared. The parquet cache records a
  `fetched_at` timestamp per entry; delete a symbol's cache file (or extend
  `CacheBackend.invalidate`) to force a refresh.
- **Free vendors are rate-limited/unofficial**: yfinance is an unofficial
  scraper that can break without notice; FRED caps around 120 req/min. The
  cache is the primary mitigation -- data is fetched once and reused.
- **No point-in-time universe membership**: free sources reflect
  currently-listed tickers only. A small fixed universe (as in the example)
  avoids survivorship bias; a broad "current index constituents" style
  universe would silently introduce it.

## Tooling note

This codebase was built with a separate `mcp-native-core` local MCP server
(`fast_search` / `parse_structure`) available as a token-efficient
code-navigation aid during development. It lives in its own repository, is
unrelated to trading research, and has no runtime dependency on this
project.
