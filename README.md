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
pip install -e ".[dev,fred,duckdb]"   # dev = pytest; fred/duckdb are optional extras
```

Requires Python >= 3.11. `fredapi` (`fred` extra) and `duckdb` (`duckdb` extra)
are only needed if you use the FRED macro source or the DuckDB cache backend
respectively -- their absence never breaks the base install, only that
piece's use.

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
  cache/       base.py (CacheBackend ABC), parquet_backend.py, duckdb_backend.py
  data/        base.py (OHLCVDataSource / MacroDataSource / FundamentalsDataSource ABCs),
               access.py (cache-through fetch, macro/fundamentals reshaping helpers)
               sources/yfinance_source.py, stooq_source.py, coingecko_source.py, fred_source.py,
                       alpha_vantage_source.py, nasdaq_data_link_source.py, sec_edgar_source.py
  signals/     base.py (Signal ABC), pipeline.py (dependency-ordered compute)
               library/momentum.py, rsi.py, macd.py, bollinger.py, mean_reversion.py,
                       realized_vol.py, cross_sectional_rank.py, macro_overlay.py, composite.py,
                       breakout.py, pairs_zscore.py, value_proxy.py
  research/    forward_returns.py, ic_analysis.py (IC, decile spreads, signal decay)
  strategy/    base.py (Strategy ABC), vol_target.py
               library/rank_weighted.py, top_bottom_decile.py, risk_parity.py, min_variance.py
  backtest/    costs.py, metrics.py, rebalance.py, engine.py (the lookahead-protection boundary)
  universe/    base.py (UniverseProvider ABC), static.py, point_in_time.py
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
| `alpha_vantage` | Equities/ETFs | Yes, free | Spot cross-check only -- ~25 req/day free-tier cap, no adjusted series |
| `fred` | Macro series (rates, CPI, ...) | Yes, free | Macro overlay input |
| `nasdaq_data_link` | Misc free datasets (e.g. `LBMA/GOLD`) | Yes, free | Macro overlay input, heterogeneous dataset columns |
| `sec_edgar` | Fundamentals (XBRL company facts: Assets, EPS, ...) | No (needs a descriptive User-Agent) | Value/quality signal input |

### Signals (all hand-rolled on pandas/numpy -- no `ta`/`pandas-ta` dependency)

`momentum`, `rsi`, `macd`, `bollinger_z`, `zscore_meanrev`, `realized_vol`,
`breakout` (Donchian channel), `xs_rank` (cross-sectional rank of an upstream
signal), `macro_overlay` (broadcasts a macro regime score across the
universe), `value_proxy` (a fundamentals concept divided by price, e.g. EPS/
price = earnings yield), `pairs_zscore` (stat-arb: rolling z-score of a
configured pair's log-price spread), and `composite` (blends multiple
signals' per-date cross-sectional z-scores into one multi-factor score, via
`depends_on`).

### Strategies

`rank_weighted_long_short` (percentile-rank-weighted long/short, dollar
neutral), `top_bottom_decile_ew` (simpler equal-weight top/bottom decile),
`risk_parity` (inverse-volatility-weighted, long-only), `min_variance`
(long-only min-variance via scipy SLSQP), `vol_targeted` (wraps any other
registered strategy by name and rescales to a target annualized volatility --
strategies composing other registry entries, not just signals).

### Cache backends

`parquet` (default: one file + JSON sidecar per cache key) and `duckdb` (one
single-file embedded database, every key a row with the frame stored as an
in-memory parquet blob, queryable via SQL) -- swap via `cache.backend` in
config with no other changes, since both satisfy the same `CacheBackend`
interface (see `tests/unit/test_cache_backend_contract.py`).

### Universe providers

`static` (default: a fixed symbol list for the whole backtest) and
`point_in_time` (membership varies by date, from a CSV of membership
windows -- see "Point-in-time universes" below).

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

**Cache backend**: subclass `CacheBackend` in `cache/`, decorate with
`@CACHE_BACKEND_REGISTRY.register("my_backend")`, and add the class to
`BACKEND_FACTORIES` in `tests/unit/test_cache_backend_contract.py` to inherit
the same parametrized correctness guarantees as `parquet`/`duckdb`.

**Universe provider**: subclass `UniverseProvider` in `universe/`, decorate
with `@UNIVERSE_PROVIDER_REGISTRY.register("my_provider")`, import it
(side-effect) in `pipeline/orchestrator.py`. Select it via
`universe.provider: my_provider` + `universe.provider_params: {...}` in
config.

**Hook**: write a module exposing `def register(hooks: HookManager) -> None`
that calls `hooks.on(HookEvent.X)` or `hooks.register(...)`. List its dotted
path under `hooks.modules` in config -- no code changes to the pipeline
itself.

## Config

See `configs/example_multi_asset.yaml` for a complete example. Shape:

```yaml
name: my_pipeline
universe:
  symbols: [...]                        # required when provider: static (the default)
  start: ...
  end: ...
  primary_source: yfinance
  fallback_sources: [stooq]
  provider: static                      # or point_in_time -- see below
  provider_params: {}                   # e.g. { membership_csv: path/to.csv } for point_in_time
macro: { series_ids: [FEDFUNDS], source: fred }                       # optional
fundamentals: { concepts: [EarningsPerShareBasic], source: sec_edgar }  # optional
cache: { backend: parquet, root_dir: .cache/quant_research }          # or backend: duckdb
signals:
  - { name: momentum, alias: mom, params: { lookback: 126 } }
  - { name: value_proxy, alias: value, depends_on: [fundamentals_EarningsPerShareBasic] }
  - { name: composite, alias: combo, depends_on: [mom, value], params: { weights: {...} } }
ic_analysis: { enabled: true, horizons: [1, 5, 21, 63], n_quantiles: 5 }
strategy: { name: rank_weighted_long_short, signals: [combo], params: {...} }
backtest: { initial_capital: 1000000, cost_model: { bps_per_trade: 5.0 }, rebalance: weekly }
report: { output_dir: reports/my_pipeline, formats: [markdown, png] }
hooks: { modules: [quant_research.hooks.builtin.logging_hooks] }
```

A signal's `depends_on` can name another configured signal's alias, a
broadcast macro series (`macro_<series_id>`), or a pivoted fundamentals
concept (`fundamentals_<concept>`) -- all three are resolved into the same
`inputs` dict a signal's `compute()` receives.

## Point-in-time universes

By default (`universe.provider: static`) the symbol list is fixed for the
whole backtest. For a broader universe that changed membership over time
(e.g. "S&P 500 constituents as of each date"), switch to
`provider: point_in_time` and point `provider_params.membership_csv` at a CSV:

```csv
symbol,start_date,end_date
AAPL,2000-01-01,
ENRN,2000-01-01,2001-12-02
```

`end_date` blank means still a member; a symbol can appear in multiple rows
for non-contiguous membership (removed, later re-added). The pipeline fetches
every symbol that ever appears in the CSV (so a removed symbol's price
history stays available up to its removal date) but masks it out of every
signal -- and therefore IC analysis, ranking, and trading -- on dates it
wasn't a valid member, which is what makes this survivorship-bias-free
instead of silently using only currently-listed constituents throughout.

There is no bundled free, reliably-maintained historical index-membership
dataset shipped with this engine (most sources either aren't free, aren't
point-in-time accurate, or aren't stable enough to hardcode a fetch from).
Typical ways to build your own CSV: Wikipedia's "List of S&P 500 companies"
article has an additions/removals table you can transcribe; several
community-maintained CSVs exist on GitHub (verify accuracy before relying on
one); or maintain it by hand for a small, deliberately-curated universe.

## Testing

```bash
pytest                 # everything runs offline against synthetic/mocked data
pytest -m network       # live-vendor tests -- needs real network access, see below
```

200+ unit/integration tests, all deterministic and network-free -- including
a dedicated cross-check (`tests/unit/test_lookahead_convention.py`) proving
`BacktestEngine`'s weight-shift and `research/forward_returns`'s t -> t+1
convention can never silently drift apart, and an integration test proving a
removed-mid-backtest symbol keeps its price history but is masked out of
ranking/trading after its exit date under `provider: point_in_time`.

## Live testing (CI)

`pytest -m network` (`tests/network/`) hits real vendors: yfinance, Stooq,
and CoinGecko unconditionally (no key needed), FRED/Alpha Vantage/Nasdaq Data
Link/SEC EDGAR skip themselves individually if their credential env var isn't
set, and a full pipeline smoke test runs `configs/example_live_smoke.yaml`
(three ETFs via yfinance, no API keys required) end to end and checks a real
tearsheet comes out the other side.

These are excluded from the default `pytest` run and need real outbound
network access to a handful of external hosts -- which a locked-down dev
sandbox may not have. Two GitHub Actions workflows exist for this:

- **`.github/workflows/tests.yml`**: the offline suite, on every push/PR.
- **`.github/workflows/live-tests.yml`**: the live suite, on a weekly
  schedule and via manual `workflow_dispatch`, using GitHub's own runners
  (independent network access from any single dev session). It runs
  `pytest -m network`, then `quant-research backtest
  configs/example_live_smoke.yaml` to produce a real tearsheet, uploaded as a
  build artifact. Set repo secrets `FRED_API_KEY` / `ALPHAVANTAGE_API_KEY` /
  `NASDAQ_DATA_LINK_API_KEY` / `SEC_EDGAR_USER_AGENT` to also exercise those
  sources; without them, only the credential-free vendors run and the rest
  skip cleanly. Trigger it manually from the Actions tab, or wait for Monday.

This is deliberately a CI concern rather than something the engine tries to
self-verify at runtime: a live vendor going down or changing its API is
exactly the kind of thing you want caught by a scheduled job with a visible
pass/fail history, not silently swallowed inside a research run.

## Known limitations (also printed in every tearsheet)

- **Calendar alignment (MVP simplification)**: crypto (24/7) and macro/
  fundamentals (monthly/quarterly/lower) series are forward-filled onto the
  equity/ETF trading calendar rather than modeled with full 24/7 precision.
- **Cross-check sources aren't drop-in substitutes**: Stooq's, CoinGecko's,
  and Alpha Vantage's (free tier, unadjusted) data isn't guaranteed to match
  yfinance's `adj_close` methodology; treat them as validation sources, not
  interchangeable primaries.
- **`adj_close` isn't immutable**: past dividend-adjusted prices can change
  retroactively as new dividends are declared. Both cache backends record a
  `fetched_at` timestamp per entry; call `CacheBackend.invalidate` (or delete
  a symbol's parquet file / duckdb row) to force a refresh.
- **Free vendors are rate-limited/unofficial**: yfinance is an unofficial
  scraper that can break without notice; FRED caps around 120 req/min; Alpha
  Vantage's free tier caps around 25 requests/day. The cache is the primary
  mitigation -- data is fetched once and reused.
- **Point-in-time universes depend on data you supply**: `provider:
  point_in_time` makes a broader universe survivorship-bias-free *given
  accurate membership data* -- there's no bundled free, verified historical
  index-membership dataset, so the result is only as correct as the CSV you
  provide (see "Point-in-time universes" above).
- **`min_variance` is O(n_dates)** with one scipy optimization per date --
  fine for research-scale universes/date-ranges, not tuned for very large
  universes or high-frequency backtests.

## Tooling note

This codebase was built with a separate `mcp-native-core` local MCP server
(`fast_search` / `parse_structure`) available as a token-efficient
code-navigation aid during development. It lives in its own repository, is
unrelated to trading research, and has no runtime dependency on this
project.
