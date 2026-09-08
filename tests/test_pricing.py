"""Testy wyceny PROXY: Black-Scholes, skew, kredyt spreadu, tabela wyceny."""

import math

import numpy as np
import pandas as pd
import pytest

from src.strategy.pricing import (
    bs_put_price,
    norm_cdf,
    price_all_spreads,
    price_spread,
    vol_for_strike,
)


def test_norm_cdf_known_values():
    assert norm_cdf(0.0) == pytest.approx(0.5)
    assert norm_cdf(1.96) == pytest.approx(0.975, abs=1e-3)
    assert norm_cdf(-1.96) == pytest.approx(0.025, abs=1e-3)


def test_bs_put_atm_reference():
    # ATM put, S=K=100, T=1, r=0, sigma=0.2.
    # Analitycznie: put = K*N(-d2) - S*N(-d1); d1 = 0.5*sigma*sqrt(T)=0.1, d2=-0.1.
    price = bs_put_price(S=100, K=100, T=1.0, r=0.0, sigma=0.2)
    expected = 100 * norm_cdf(0.1) - 100 * norm_cdf(-0.1)
    assert price == pytest.approx(expected, rel=1e-9)
    assert price == pytest.approx(7.9656, abs=1e-3)


def test_bs_put_intrinsic_when_expired():
    # T=0 -> wartość wewnętrzna.
    assert bs_put_price(S=90, K=100, T=0.0, r=0.0, sigma=0.2) == pytest.approx(10.0)
    assert bs_put_price(S=110, K=100, T=0.0, r=0.0, sigma=0.2) == pytest.approx(0.0)


def test_bs_put_zero_vol_intrinsic():
    assert bs_put_price(S=95, K=100, T=0.5, r=0.0, sigma=0.0) == pytest.approx(5.0)


def test_bs_put_invalid_inputs():
    with pytest.raises(ValueError):
        bs_put_price(S=-1, K=100, T=1, r=0, sigma=0.2)


def test_vol_skew_increases_for_lower_strikes():
    base = 0.18
    atm = vol_for_strike(base, S=100, K=100, skew_slope=0.8)
    otm = vol_for_strike(base, S=100, K=90, skew_slope=0.8)
    assert atm == pytest.approx(base)
    assert otm > atm  # niższy strike -> wyższa zmienność
    # (100-90)/100 = 0.1 -> +0.08
    assert otm == pytest.approx(base + 0.08)


def test_price_spread_credit_and_maxloss():
    p = price_spread(
        spot=4000,
        base_vol=0.18,
        short_strike=3900,
        long_strike=3850,
        dte_days=4,
        r=0.03,
        skew_slope=0.8,
        multiplier=100,
    )
    assert p.is_proxy is True
    assert p.short_put > p.long_put          # short bliżej ATM -> droższy
    assert 0 < p.credit_points < 50          # kredyt mniejszy niż szerokość skrzydła
    assert p.credit_cash == pytest.approx(p.credit_points * 100)
    # max loss = (wing - credit) * multiplier
    assert p.max_loss_cash == pytest.approx((50 - p.credit_points) * 100)
    assert p.max_profit_cash == pytest.approx(p.credit_cash)


def test_price_spread_requires_short_above_long():
    with pytest.raises(ValueError):
        price_spread(
            spot=4000, base_vol=0.18, short_strike=3850, long_strike=3900,
            dte_days=4,
        )


def test_price_all_spreads_joins_entry_day_data():
    plans = pd.DataFrame(
        {
            "entry_date": [pd.Timestamp("2024-01-08")],
            "expiration_date": [pd.Timestamp("2024-01-12")],
            "dte": [4],
            "short_strike": [4700.0],
            "long_strike": [4650.0],
        }
    )
    spx = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-08", "2024-01-09"]),
            "open": [4750.0, 4760.0],
            "close": [4755.0, 4765.0],
        }
    )
    vix = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-08", "2024-01-09"]),
            "open": [15.0, 16.0],
            "close": [15.5, 16.5],
        }
    )
    out = price_all_spreads(plans, spx, vix, spot_basis="open", vol_basis="open")
    assert len(out) == 1
    row = out.iloc[0]
    assert row["spot"] == 4750.0
    assert row["base_vol"] == pytest.approx(0.15)
    assert row["credit_cash"] > 0
    assert bool(row["is_proxy"]) is True


def test_price_all_spreads_skips_missing_dates():
    plans = pd.DataFrame(
        {
            "entry_date": [pd.Timestamp("2024-01-08")],
            "expiration_date": [pd.Timestamp("2024-01-12")],
            "dte": [4],
            "short_strike": [4700.0],
            "long_strike": [4650.0],
        }
    )
    spx = pd.DataFrame({"date": pd.to_datetime(["2024-01-09"]), "open": [4760.0]})
    vix = pd.DataFrame({"date": pd.to_datetime(["2024-01-09"]), "open": [16.0]})
    out = price_all_spreads(plans, spx, vix)
    assert out.empty
