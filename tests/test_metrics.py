"""Testy metryk wydajności: transakcyjne i portfelowe."""

import math

import numpy as np
import pandas as pd
import pytest

from src.metrics.performance import (
    compute_metrics,
    equity_metrics,
    trade_metrics,
)


def test_trade_metrics_basic():
    res = pd.DataFrame({"pnl_cash": [300.0, 300.0, -4700.0, 300.0]})
    m = trade_metrics(res)
    assert m["n_trades"] == 4
    assert m["n_wins"] == 3
    assert m["n_losses"] == 1
    assert m["win_rate"] == pytest.approx(0.75)
    assert m["gross_profit"] == pytest.approx(900.0)
    assert m["gross_loss"] == pytest.approx(4700.0)
    assert m["profit_factor"] == pytest.approx(900.0 / 4700.0)
    assert m["expectancy"] == pytest.approx((900 - 4700) / 4)
    assert m["avg_win"] == pytest.approx(300.0)
    assert m["avg_loss"] == pytest.approx(-4700.0)
    assert m["payoff_ratio"] == pytest.approx(300.0 / 4700.0)


def test_trade_metrics_no_losses_infinite_pf():
    res = pd.DataFrame({"pnl_cash": [100.0, 200.0]})
    m = trade_metrics(res)
    assert m["profit_factor"] == float("inf")
    assert m["payoff_ratio"] == float("inf")


def test_trade_metrics_empty():
    m = trade_metrics(pd.DataFrame())
    assert m["n_trades"] == 0
    assert m["win_rate"] == 0.0


def test_equity_metrics_total_return_and_cagr():
    # 2 lata, kapitał podwaja się -> CAGR ~ 41.4%.
    dates = pd.to_datetime(["2020-01-01", "2022-01-01"])
    curve = pd.DataFrame({"entry_date": dates, "equity": [150000.0, 200000.0]})
    m = equity_metrics(curve, initial_capital=100000.0)
    assert m["final_equity"] == pytest.approx(200000.0)
    assert m["total_return"] == pytest.approx(1.0)
    assert m["years"] == pytest.approx(2.0, abs=0.01)
    assert m["cagr"] == pytest.approx(2 ** 0.5 - 1, rel=1e-2)


def test_equity_metrics_max_drawdown():
    dates = pd.bdate_range("2020-01-01", periods=4)
    # start 100000 -> 110000 -> 90000 -> 95000
    curve = pd.DataFrame({"entry_date": dates, "equity": [110000.0, 130000.0, 90000.0, 95000.0]})
    m = equity_metrics(curve, initial_capital=100000.0)
    # peak 130000, trough 90000 -> dd = -40000 / 130000
    assert m["max_drawdown"] == pytest.approx(-40000.0)
    assert m["max_drawdown_pct"] == pytest.approx(-40000.0 / 130000.0)


def test_equity_metrics_sharpe_positive_for_growth():
    dates = pd.bdate_range("2020-01-01", periods=10)
    equity = np.linspace(101000, 110000, 10)  # stały wzrost
    curve = pd.DataFrame({"entry_date": dates, "equity": equity})
    m = equity_metrics(curve, initial_capital=100000.0)
    assert m["sharpe"] > 0
    # brak ujemnych zwrotów -> Sortino nieskończony
    assert m["sortino"] == float("inf")


def test_equity_metrics_empty():
    m = equity_metrics(pd.DataFrame(), initial_capital=100000.0)
    assert m["final_equity"] == 100000.0
    assert m["total_return"] == 0.0


def test_compute_metrics_merges():
    res = pd.DataFrame({"pnl_cash": [300.0, -100.0]})
    dates = pd.bdate_range("2020-01-01", periods=2)
    curve = pd.DataFrame({"entry_date": dates, "equity": [100300.0, 100200.0]})
    m = compute_metrics(res, curve, initial_capital=100000.0)
    assert "win_rate" in m and "cagr" in m
    assert m["n_trades"] == 2
    assert m["final_equity"] == pytest.approx(100200.0)
