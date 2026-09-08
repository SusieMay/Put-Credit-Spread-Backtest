"""Testy wizualizacji: wykresy zapisują niepuste pliki PNG."""

import numpy as np
import pandas as pd
import pytest

from src.viz.plots import (
    plot_drawdown,
    plot_equity_curve,
    plot_pnl_histogram,
    plot_yearly_pnl,
)


def _curve(n=10):
    dates = pd.bdate_range("2020-01-01", periods=n)
    equity = np.linspace(100000, 110000, n)
    peak = np.maximum.accumulate(equity)
    return pd.DataFrame(
        {
            "entry_date": dates,
            "equity": equity,
            "peak": peak,
            "drawdown": equity - peak,
            "drawdown_pct": (equity - peak) / peak,
        }
    )


def _results(n=20):
    dates = pd.bdate_range("2020-01-01", periods=n)
    pnl = [300.0] * (n - 2) + [-4700.0, -4700.0]
    return pd.DataFrame({"entry_date": dates, "pnl_cash": pnl})


def _yearly():
    return pd.DataFrame({"year": [2020, 2021], "total_pnl": [5000.0, -3000.0]})


def _assert_png(path):
    assert path.exists()
    assert path.stat().st_size > 0
    with open(path, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"  # sygnatura PNG


def test_plot_equity_curve(tmp_path):
    p = plot_equity_curve(_curve(), tmp_path / "eq.png")
    _assert_png(p)


def test_plot_drawdown(tmp_path):
    p = plot_drawdown(_curve(), tmp_path / "dd.png")
    _assert_png(p)


def test_plot_pnl_histogram(tmp_path):
    p = plot_pnl_histogram(_results(), tmp_path / "hist.png")
    _assert_png(p)


def test_plot_yearly_pnl(tmp_path):
    p = plot_yearly_pnl(_yearly(), tmp_path / "yearly.png")
    _assert_png(p)


def test_plots_handle_empty(tmp_path):
    empty = pd.DataFrame()
    _assert_png(plot_equity_curve(empty, tmp_path / "e1.png"))
    _assert_png(plot_drawdown(empty, tmp_path / "e2.png"))
    _assert_png(plot_pnl_histogram(empty, tmp_path / "e3.png"))
    _assert_png(plot_yearly_pnl(empty, tmp_path / "e4.png"))


def test_plot_creates_nested_dir(tmp_path):
    p = plot_equity_curve(_curve(), tmp_path / "nested" / "deep" / "eq.png")
    _assert_png(p)
