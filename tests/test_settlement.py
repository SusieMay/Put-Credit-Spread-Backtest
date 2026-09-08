"""Testy rozliczenia na wygaśnięciu: wartość wewnętrzna, wynik, klasyfikacja."""

import pandas as pd
import pytest

from src.strategy.settlement import (
    put_intrinsic,
    settle_all_spreads,
    settle_spread,
    spread_value_at_expiry,
)


def test_put_intrinsic():
    assert put_intrinsic(100, 90) == 10
    assert put_intrinsic(100, 110) == 0
    assert put_intrinsic(100, 100) == 0


def test_spread_value_bounds():
    # Powyżej short -> 0.
    assert spread_value_at_expiry(3900, 3850, 4000) == 0
    # Poniżej long -> pełna szerokość skrzydła.
    assert spread_value_at_expiry(3900, 3850, 3800) == 50
    # Pomiędzy -> częściowa.
    assert spread_value_at_expiry(3900, 3850, 3875) == 25


def test_settle_max_profit():
    o = settle_spread(
        credit_points=3.0, short_strike=3900, long_strike=3850,
        spot_settle=3950, multiplier=100,
    )
    assert o.outcome == "max_profit"
    assert o.pnl_points == pytest.approx(3.0)
    assert o.pnl_cash == pytest.approx(300.0)
    assert o.is_win is True


def test_settle_max_loss():
    o = settle_spread(
        credit_points=3.0, short_strike=3900, long_strike=3850,
        spot_settle=3800, multiplier=100,
    )
    assert o.outcome == "max_loss"
    # oddajemy 50, dostaliśmy 3 -> -47 pkt.
    assert o.pnl_points == pytest.approx(-47.0)
    assert o.pnl_cash == pytest.approx(-4700.0)
    assert o.is_win is False


def test_settle_partial_loss_can_still_win():
    # settle 3898: value = 3900-3898 = 2, credit 3 -> pnl +1 (wygrana mimo partial).
    o = settle_spread(
        credit_points=3.0, short_strike=3900, long_strike=3850,
        spot_settle=3898, multiplier=100,
    )
    assert o.outcome == "partial_loss"
    assert o.pnl_points == pytest.approx(1.0)
    assert o.is_win is True


def test_settle_partial_loss_losing():
    o = settle_spread(
        credit_points=3.0, short_strike=3900, long_strike=3850,
        spot_settle=3890, multiplier=100,
    )
    assert o.outcome == "partial_loss"
    assert o.pnl_points == pytest.approx(-7.0)  # value 10 - credit 3
    assert o.is_win is False


def test_settle_all_spreads_joins_expiration_close():
    priced = pd.DataFrame(
        {
            "entry_date": [pd.Timestamp("2024-01-08"), pd.Timestamp("2024-01-15")],
            "expiration_date": [pd.Timestamp("2024-01-12"), pd.Timestamp("2024-01-19")],
            "short_strike": [4700.0, 4700.0],
            "long_strike": [4650.0, 4650.0],
            "credit_points": [3.0, 3.0],
        }
    )
    spx = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-12", "2024-01-19"]),
            "close": [4800.0, 4600.0],  # 1. max profit, 2. max loss
        }
    )
    out = settle_all_spreads(priced, spx, settle_basis="close", multiplier=100)
    assert len(out) == 2
    assert out.iloc[0]["outcome"] == "max_profit"
    assert out.iloc[0]["pnl_cash"] == pytest.approx(300.0)
    assert out.iloc[1]["outcome"] == "max_loss"
    assert out.iloc[1]["pnl_cash"] == pytest.approx(-4700.0)


def test_settle_all_spreads_skips_missing_expiration():
    priced = pd.DataFrame(
        {
            "entry_date": [pd.Timestamp("2024-01-08")],
            "expiration_date": [pd.Timestamp("2024-01-12")],
            "short_strike": [4700.0],
            "long_strike": [4650.0],
            "credit_points": [3.0],
        }
    )
    spx = pd.DataFrame({"date": pd.to_datetime(["2024-01-15"]), "close": [4800.0]})
    out = settle_all_spreads(priced, spx)
    assert out.empty
