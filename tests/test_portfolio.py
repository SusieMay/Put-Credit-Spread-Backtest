"""Testy portfela: sizing pozycji, krzywa kapitału, drawdown."""

import pandas as pd
import pytest

from src.portfolio.engine import (
    PortfolioConfig,
    build_equity_curve,
    size_position,
)


def test_size_fixed_contracts():
    n = size_position(
        equity=100000, max_loss_per_contract=4700,
        sizing="fixed_contracts", contracts=3,
    )
    assert n == 3


def test_size_fixed_risk_pct():
    # ryzyko = 2% * 100000 = 2000; maks strata/kontrakt 4700 -> floor(2000/4700)=0
    assert size_position(
        equity=100000, max_loss_per_contract=4700,
        sizing="fixed_risk_pct", risk_pct=0.02,
    ) == 0
    # 5% * 100000 = 5000 -> floor(5000/4700)=1
    assert size_position(
        equity=100000, max_loss_per_contract=4700,
        sizing="fixed_risk_pct", risk_pct=0.05,
    ) == 1
    # większy kapitał -> więcej kontraktów
    assert size_position(
        equity=1000000, max_loss_per_contract=4700,
        sizing="fixed_risk_pct", risk_pct=0.05,
    ) == 10


def test_size_fixed_capital_alloc():
    assert size_position(
        equity=100000, max_loss_per_contract=4700,
        sizing="fixed_capital_alloc", capital_alloc=10000,
    ) == 2  # floor(10000/4700)


def test_size_zero_when_maxloss_nonpositive():
    assert size_position(
        equity=100000, max_loss_per_contract=0,
        sizing="fixed_risk_pct", risk_pct=0.05,
    ) == 0


def test_size_unknown_method_raises():
    with pytest.raises(ValueError):
        size_position(
            equity=100000, max_loss_per_contract=4700, sizing="bogus",
        )


def _results(pnls, entries=None, max_loss=4700.0):
    n = len(pnls)
    if entries is None:
        entries = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame(
        {
            "entry_date": entries,
            "expiration_date": [e + pd.Timedelta(days=4) for e in entries],
            "pnl_cash": pnls,
            "max_loss_cash": [max_loss] * n,
        }
    )


def test_equity_curve_accumulates():
    res = _results([300.0, -4700.0, 300.0])
    cfg = PortfolioConfig(initial_capital=100000, sizing="fixed_contracts", contracts=1)
    curve = build_equity_curve(res, cfg)
    assert len(curve) == 3
    # 100000 +300 -4700 +300 = 95900
    assert curve["equity"].iloc[-1] == pytest.approx(95900.0)
    assert curve["trade_pnl"].iloc[0] == pytest.approx(300.0)


def test_equity_curve_drawdown():
    res = _results([1000.0, -3000.0, 500.0])
    cfg = PortfolioConfig(initial_capital=100000, sizing="fixed_contracts", contracts=1)
    curve = build_equity_curve(res, cfg)
    # peak po 1. transakcji = 101000; po 2. equity=98000 -> dd=-3000
    assert curve["drawdown"].iloc[1] == pytest.approx(-3000.0)
    assert curve["drawdown"].min() == pytest.approx(-3000.0)
    # po 3. transakcji equity=98500, peak nadal 101000 -> dd=-2500
    assert curve["drawdown"].iloc[2] == pytest.approx(-2500.0)


def test_equity_curve_sorts_by_entry_date():
    entries = pd.to_datetime(["2024-02-01", "2024-01-01", "2024-01-15"])
    res = _results([100.0, 200.0, 300.0], entries=entries)
    cfg = PortfolioConfig(initial_capital=1000, sizing="fixed_contracts", contracts=1)
    curve = build_equity_curve(res, cfg)
    # posortowane rosnąco po dacie: +200 (Jan1), +300 (Jan15), +100 (Feb1)
    assert list(curve["entry_date"]) == list(pd.to_datetime(
        ["2024-01-01", "2024-01-15", "2024-02-01"]))
    assert curve["equity"].iloc[-1] == pytest.approx(1600.0)


def test_equity_curve_skips_zero_contracts():
    # risk_pct za mały -> 0 kontraktów -> brak transakcji.
    res = _results([300.0, 300.0])
    cfg = PortfolioConfig(
        initial_capital=100000, sizing="fixed_risk_pct", risk_pct=0.001,
    )
    curve = build_equity_curve(res, cfg)
    assert curve.empty


def test_equity_curve_empty_input():
    cfg = PortfolioConfig()
    curve = build_equity_curve(pd.DataFrame(), cfg)
    assert curve.empty
