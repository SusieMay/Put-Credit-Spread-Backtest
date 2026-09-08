"""Testy pełnego pipeline'u i generowania raportu."""

import numpy as np
import pandas as pd
import pytest

from src.backtest.pipeline import BacktestParams, run_pipeline
from src.backtest.report import render_report
from src.metrics.performance import compute_metrics
from src.portfolio.engine import PortfolioConfig


def _make_market(start: str, periods: int, seed: int = 0):
    dates = pd.bdate_range(start=start, periods=periods)
    rng = np.random.default_rng(seed)
    base = 4000 + np.cumsum(rng.normal(0, 15, len(dates)))
    spx = pd.DataFrame(
        {
            "date": dates,
            "open": base,
            "high": base + 20,
            "low": base - 20,
            "close": base + 5,
            "volume": 0.0,
        }
    )
    vix = pd.DataFrame(
        {
            "date": dates,
            "open": np.full(len(dates), 18.0),
            "high": np.full(len(dates), 19.0),
            "low": np.full(len(dates), 17.0),
            "close": np.full(len(dates), 18.0),
            "volume": 0.0,
        }
    )
    return spx, vix


def test_run_pipeline_produces_results():
    spx, vix = _make_market("2020-01-01", 200)
    params = BacktestParams(portfolio=PortfolioConfig(initial_capital=100000, contracts=1))
    art = run_pipeline(spx, vix, params)
    assert not art.plans.empty
    assert not art.priced.empty
    assert not art.results.empty
    assert not art.curve.empty
    # kolumny wyniku
    for col in ("credit_cash", "pnl_cash", "outcome"):
        assert col in art.results.columns
    # krzywa kapitału monotonicznie indeksuje equity
    assert "equity" in art.curve.columns


def test_run_pipeline_no_look_ahead_columns_present():
    spx, vix = _make_market("2020-01-01", 200, seed=1)
    params = BacktestParams()
    art = run_pipeline(spx, vix, params)
    # short > long dla każdego spreadu
    assert (art.results["short_strike"] > art.results["long_strike"]).all()
    # is_proxy zawsze True
    assert art.results["is_proxy"].all()


def test_render_report_contains_key_sections():
    spx, vix = _make_market("2020-01-01", 200, seed=2)
    params = BacktestParams()
    art = run_pipeline(spx, vix, params)
    metrics = compute_metrics(art.results, art.curve, params.portfolio.initial_capital)

    from src.analysis.breakdown import period_breakdown, tail_stats, yearly_breakdown

    report = render_report(
        config_name="base.yaml",
        params_summary={"Underlying": "^GSPC"},
        metrics=metrics,
        yearly=yearly_breakdown(art.results),
        stress=period_breakdown(art.results),
        tail=tail_stats(art.results),
        chart_files=["charts/equity_curve.png"],
    )
    assert "# Raport backtestu" in report
    assert "PROXY" in report
    assert "## Wyniki zbiorcze" in report
    assert "## Rok po roku" in report
    assert "## Tail risk" in report
    assert "CAGR" in report
    assert "charts/equity_curve.png" in report


def test_render_report_handles_empty_frames():
    report = render_report(
        config_name="base.yaml",
        params_summary={},
        metrics={},
        yearly=pd.DataFrame(),
        stress=pd.DataFrame(),
        tail={},
    )
    assert "# Raport backtestu" in report
    assert "_Brak danych._" in report
