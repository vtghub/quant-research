from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quant_research.cli.main import app
from quant_research.core.registries import DATA_SOURCE_REGISTRY

runner = CliRunner()


def test_list_registry_shows_builtins() -> None:
    result = runner.invoke(app, ["list-registry"])
    assert result.exit_code == 0
    assert "yfinance" in result.stdout
    assert "momentum" in result.stdout
    assert "rank_weighted_long_short" in result.stdout
    assert "parquet" in result.stdout
    assert "fred" in result.stdout


def _write_config(tmp_path, primary_source: str) -> Path:
    yaml_text = textwrap.dedent(
        f"""
        name: cli_test
        universe:
          symbols: [AAA, BBB]
          start: "2020-01-01"
          end: "2020-06-01"
          primary_source: {primary_source}
        cache:
          root_dir: "{tmp_path / "cache"}"
        signals:
          - name: momentum
            alias: mom
        strategy:
          name: rank_weighted_long_short
          signals: [mom]
        report:
          output_dir: "{tmp_path / "reports"}"
          formats: [markdown]
        """
    )
    path = tmp_path / "config.yaml"
    path.write_text(yaml_text)
    return path


def test_validate_config_succeeds(tmp_path) -> None:
    config_path = _write_config(tmp_path, "yfinance")
    result = runner.invoke(app, ["validate-config", str(config_path)])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_validate_config_fails_on_missing_file(tmp_path) -> None:
    result = runner.invoke(app, ["validate-config", str(tmp_path / "nope.yaml")])
    assert result.exit_code != 0


@pytest.fixture
def registered_fake_source(synthetic_long_ohlcv):
    import pandas as pd

    class _FixtureSource:
        name = "cli_fake_source"

        def fetch(self, symbols, start, end, interval="1d"):
            start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
            mask = (
                synthetic_long_ohlcv["symbol"].isin(symbols)
                & (synthetic_long_ohlcv["date"] >= start_ts)
                & (synthetic_long_ohlcv["date"] <= end_ts)
            )
            sliced = synthetic_long_ohlcv.loc[mask].copy()
            sliced["source"] = self.name
            return sliced.sort_values(["symbol", "date"]).reset_index(drop=True)

    DATA_SOURCE_REGISTRY.register("cli_fake_source")(_FixtureSource)
    yield "cli_fake_source"
    DATA_SOURCE_REGISTRY._items.pop("cli_fake_source", None)


def test_research_command_runs_end_to_end_offline(tmp_path, registered_fake_source) -> None:
    config_path = _write_config(tmp_path, registered_fake_source)
    result = runner.invoke(app, ["research", str(config_path)])
    assert result.exit_code == 0
    assert "Fetched prices" in result.stdout
    assert "signal 'mom'" in result.stdout


def test_backtest_command_runs_end_to_end_offline(tmp_path, registered_fake_source) -> None:
    config_path = _write_config(tmp_path, registered_fake_source)
    result = runner.invoke(app, ["backtest", str(config_path)])
    assert result.exit_code == 0
    assert "Final equity" in result.stdout
    assert "Report written to" in result.stdout
