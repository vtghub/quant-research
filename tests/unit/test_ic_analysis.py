from __future__ import annotations

import numpy as np
import pandas as pd

from quant_research.research.forward_returns import forward_returns
from quant_research.research.ic_analysis import (
    decile_spread_returns,
    information_coefficient,
    run_ic_analysis,
    signal_autocorrelation,
    summarize_ic,
)


def test_forward_returns_hand_computed() -> None:
    dates = pd.bdate_range("2020-01-01", periods=6)
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 121.0, 133.1, 146.41, 161.051]}, index=dates)

    fwd = forward_returns(prices, horizons=[1, 2])
    # out[h].loc[t] = price_{t+h} / price_t - 1
    assert np.isclose(fwd[1]["AAA"].iloc[0], 110.0 / 100.0 - 1.0)
    assert np.isclose(fwd[2]["AAA"].iloc[0], 121.0 / 100.0 - 1.0)


def test_information_coefficient_is_one_for_identical_monotonic_series() -> None:
    dates = pd.bdate_range("2020-01-01", periods=10)
    rng = np.random.default_rng(11)
    fwd_ret = pd.DataFrame(rng.normal(0, 0.02, (10, 6)), index=dates, columns=list("ABCDEF"))
    # signal is a monotonic (identity) function of the exact forward return -> IC == 1.0
    signal = fwd_ret.copy()

    ic = information_coefficient(signal, fwd_ret)
    assert np.allclose(ic.dropna(), 1.0)


def test_information_coefficient_is_negative_one_for_inverted_series() -> None:
    dates = pd.bdate_range("2020-01-01", periods=10)
    rng = np.random.default_rng(12)
    fwd_ret = pd.DataFrame(rng.normal(0, 0.02, (10, 6)), index=dates, columns=list("ABCDEF"))
    signal = -fwd_ret

    ic = information_coefficient(signal, fwd_ret)
    assert np.allclose(ic.dropna(), -1.0)


def test_decile_spread_returns_empty_frame_on_no_overlapping_dates() -> None:
    # e.g. a data source returned nothing for the requested range -- prices
    # (and therefore signal/forward-returns) end up completely empty. This
    # must produce an empty-but-correctly-shaped frame, not crash trying to
    # set_index("date") on a frame with zero rows and no columns at all.
    empty = pd.DataFrame()
    result = decile_spread_returns(empty, empty, n_quantiles=5)
    assert result.empty
    assert list(result.columns) == ["q1", "q2", "q3", "q4", "q5", "spread"]
    assert result.index.name == "date"


def test_decile_spread_positive_when_signal_predicts_return() -> None:
    dates = pd.bdate_range("2020-01-01", periods=5)
    # 10 symbols, signal exactly equals rank 0..9, fwd_ret also increasing with rank
    signal = pd.DataFrame(
        {sym: [i] * 5 for i, sym in enumerate("ABCDEFGHIJ")}, index=dates, dtype=float
    )
    fwd_ret = signal.copy() * 0.01  # perfectly monotonic relationship

    spreads = decile_spread_returns(signal, fwd_ret, n_quantiles=5)
    assert (spreads["spread"] > 0).all()


def test_summarize_ic_positive_mean_ic() -> None:
    ic_series = pd.Series([0.1, 0.2, 0.15, -0.05, 0.3])
    summary = summarize_ic(ic_series, horizon=5)
    assert summary.horizon == 5
    assert summary.mean_ic > 0
    assert summary.hit_rate == 0.8  # 4 of 5 positive


def test_summarize_ic_empty_series_does_not_raise() -> None:
    summary = summarize_ic(pd.Series(dtype=float), horizon=1)
    assert summary.mean_ic == 0.0
    assert summary.hit_rate == 0.0


def test_signal_autocorrelation_near_one_for_slow_moving_signal() -> None:
    dates = pd.bdate_range("2020-01-01", periods=50)
    rng = np.random.default_rng(13)
    base = rng.normal(0, 1, 6)
    # signal barely changes day to day -> high autocorrelation
    slow_signal = pd.DataFrame(
        [base + rng.normal(0, 0.001, 6) for _ in range(50)], index=dates, columns=list("ABCDEF")
    )
    autocorr = signal_autocorrelation(slow_signal)
    assert autocorr.dropna().mean() > 0.9


def test_run_ic_analysis_end_to_end(synthetic_prices: pd.DataFrame) -> None:
    # a signal derived from prices themselves (rank of level) -- just proving wiring, not efficacy
    signal = synthetic_prices.rank(axis=1, pct=True)
    result = run_ic_analysis(synthetic_prices, signal, horizons=[1, 5], n_quantiles=5)

    assert set(result.summaries.keys()) == {1, 5}
    assert set(result.ic_series.keys()) == {1, 5}
    assert set(result.decile_spreads.keys()) == {1, 5}
    assert not result.autocorrelation.empty
    for h, summary in result.summaries.items():
        assert np.isfinite(summary.mean_ic) or summary.mean_ic == 0.0
