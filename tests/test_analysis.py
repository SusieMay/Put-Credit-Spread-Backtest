"""Testy analiz: rozbicie roczne, okresy stresowe, tail risk."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.breakdown import (
    period_breakdown,
    tail_stats,
    yearly_breakdown,
)


def _results(dates, pnls, outcomes=None):
    df = pd.DataFrame(
        {
            "entry_date": pd.to_datetime(dates),
            "expiration_date": pd.to_datetime(dates) + pd.Timedelta(days=4),
            "pnl_cash": pnls,
        }
    )
    if outcomes is not None:
        df["outcome"] = outcomes
    return df


def test_yearly_breakdown_groups_by_year():
    res = _results(
        ["2020-03-02", "2020-06-01", "2021-01-04"],
        [300.0, -4700.0, 300.0],
    )
    yb = yearly_breakdown(res)
    assert list(yb["year"]) == [2020, 2021]
    row2020 = yb[yb["year"] == 2020].iloc[0]
    assert row2020["n_trades"] == 2
    assert row2020["total_pnl"] == pytest.approx(-4400.0)
    assert row2020["worst"] == pytest.approx(-4700.0)
    row2021 = yb[yb["year"] == 2021].iloc[0]
    assert row2021["win_rate"] == pytest.approx(1.0)


def test_yearly_breakdown_empty():
    yb = yearly_breakdown(pd.DataFrame())
    assert yb.empty


def test_period_breakdown_filters_windows():
    res = _results(
        ["2020-03-02", "2020-03-16", "2022-06-01", "2019-01-02"],
        [-4700.0, -4700.0, 300.0, 300.0],
    )
    pb = period_breakdown(
        res,
        periods={
            "COVID": ("2020-02-19", "2020-04-30"),
            "Bear 2022": ("2022-01-01", "2022-12-31"),
        },
    )
    covid = pb[pb["period"] == "COVID"].iloc[0]
    assert covid["n_trades"] == 2
    assert covid["total_pnl"] == pytest.approx(-9400.0)
    assert covid["win_rate"] == pytest.approx(0.0)
    bear = pb[pb["period"] == "Bear 2022"].iloc[0]
    assert bear["n_trades"] == 1
    assert bear["total_pnl"] == pytest.approx(300.0)


def test_period_breakdown_empty_window():
    res = _results(["2015-01-05"], [300.0])
    pb = period_breakdown(res, periods={"COVID": ("2020-02-19", "2020-04-30")})
    assert pb.iloc[0]["n_trades"] == 0
    assert pb.iloc[0]["total_pnl"] == 0.0


def test_tail_stats_var_cvar():
    # 20 transakcji: 18 x +100, 2 x -1000.
    pnls = [100.0] * 18 + [-1000.0, -1000.0]
    dates = pd.bdate_range("2020-01-01", periods=20)
    res = _results(dates, pnls)
    t = tail_stats(res, n_worst=3, alpha=0.05)
    # 5% z 20 = 1 najgorsza; VaR ~ -1000.
    assert t["var"] <= -1000.0 + 1e-6
    assert t["cvar"] <= t["var"] + 1e-6
    assert len(t["worst_trades"]) == 3
    assert t["worst_trades"]["pnl_cash"].iloc[0] == pytest.approx(-1000.0)


def test_tail_stats_empty():
    t = tail_stats(pd.DataFrame())
    assert t["var"] == 0.0
    assert t["worst_trades"].empty
