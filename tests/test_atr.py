"""Testy wskaźnika: Wilder ATR, resampling tygodniowy, poziom Saty, brak look-ahead."""

import numpy as np
import pandas as pd
import pytest

from src.indicators.atr import (
    resample_weekly,
    saty_atr_level,
    true_range,
    weekly_atr_table,
    wilder_rma,
)


def _daily_range(start: str, periods: int) -> pd.DatetimeIndex:
    # Same dni robocze (Mon-Fri).
    return pd.bdate_range(start=start, periods=periods)


def test_wilder_rma_hand_computed():
    # TR = 2,4,...,20 ; period=5.
    tr = pd.Series([2.0, 4, 6, 8, 10, 12, 14, 16, 18, 20])
    rma = wilder_rma(tr, 5)
    # Seed na indeksie 4 = SMA(2,4,6,8,10) = 6.
    assert np.isnan(rma.iloc[3])
    assert rma.iloc[4] == pytest.approx(6.0)
    # index5 = (6*4 + 12)/5 = 7.2
    assert rma.iloc[5] == pytest.approx(7.2)
    # index6 = (7.2*4 + 14)/5 = 8.56
    assert rma.iloc[6] == pytest.approx(8.56)


def test_wilder_rma_too_short_all_nan():
    s = pd.Series([1.0, 2.0, 3.0])
    rma = wilder_rma(s, 5)
    assert rma.isna().all()


def test_resample_weekly_ohlc():
    # 2 pełne tygodnie robocze zaczynając w poniedziałek 2024-01-01.
    dates = _daily_range("2024-01-01", 10)  # 2 tygodnie po 5 dni
    df = pd.DataFrame(
        {
            "date": dates,
            "open": np.arange(10, dtype=float) + 100,
            "high": np.arange(10, dtype=float) + 105,
            "low": np.arange(10, dtype=float) + 95,
            "close": np.arange(10, dtype=float) + 101,
            "volume": np.zeros(10),
        }
    )
    weekly = resample_weekly(df)
    assert len(weekly) == 2
    # Tydzień 1: open = pierwszy dzień, close = piąty dzień.
    assert weekly.iloc[0]["open"] == pytest.approx(100.0)
    assert weekly.iloc[0]["close"] == pytest.approx(101.0 + 4)  # 5. dzień, index 4
    assert weekly.iloc[0]["high"] == pytest.approx(max(105 + i for i in range(5)))
    assert weekly.iloc[0]["low"] == pytest.approx(min(95 + i for i in range(5)))
    # Etykieta week_end to piątek.
    assert weekly.iloc[0]["week_end"].weekday() == 4


def test_true_range_first_bar_is_high_low():
    weekly = pd.DataFrame(
        {
            "week_end": pd.to_datetime(["2024-01-05", "2024-01-12"]),
            "open": [100.0, 110.0],
            "high": [110.0, 120.0],
            "low": [90.0, 105.0],
            "close": [105.0, 118.0],
        }
    )
    tr = true_range(weekly)
    assert tr.iloc[0] == pytest.approx(20.0)  # 110 - 90
    # Druga świeca: max(120-105, |120-105|, |105-105|) = max(15,15,0)=15
    assert tr.iloc[1] == pytest.approx(15.0)


def test_saty_level_hand_example():
    # Zbuduj dane tak, by ostatni zakończony tydzień miał znane close i atr.
    # Prościej: zweryfikuj wzór level = prev_close + mult*atr na tabeli tygodniowej.
    dates = _daily_range("2023-01-02", 100)
    rng = np.random.default_rng(0)
    base = 100 + np.cumsum(rng.normal(0, 1, len(dates)))
    df = pd.DataFrame(
        {
            "date": dates,
            "open": base,
            "high": base + 2,
            "low": base - 2,
            "close": base + 0.5,
            "volume": 0.0,
        }
    )
    table = weekly_atr_table(df, atr_period=14)
    completed = table.dropna(subset=["atr"])
    ref = completed.iloc[-1]
    entry = pd.Timestamp(ref["week_end"]) + pd.Timedelta(days=3)  # kolejny poniedziałek
    res = saty_atr_level(df, entry, atr_period=14, atr_multiplier=-1.0)
    assert res is not None
    assert res.prev_close == pytest.approx(float(ref["close"]))
    assert res.atr == pytest.approx(float(ref["atr"]))
    assert res.level == pytest.approx(float(ref["close"]) - float(ref["atr"]))


def test_saty_level_none_when_insufficient_data():
    dates = _daily_range("2024-01-01", 10)  # tylko 2 tygodnie < 14 okresów ATR
    df = pd.DataFrame(
        {
            "date": dates,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 0.0,
        }
    )
    res = saty_atr_level(df, pd.Timestamp("2024-01-15"), atr_period=14)
    assert res is None


def test_no_look_ahead_level_stable_under_truncation():
    # Poziom dla entry_date NIE może zależeć od danych z/po entry_date.
    dates = _daily_range("2022-01-03", 200)
    rng = np.random.default_rng(42)
    base = 4000 + np.cumsum(rng.normal(0, 15, len(dates)))
    df = pd.DataFrame(
        {
            "date": dates,
            "open": base,
            "high": base + 20,
            "low": base - 20,
            "close": base + 5,
            "volume": 0.0,
        }
    )
    entry = pd.Timestamp("2022-08-01")  # poniedziałek w środku danych

    full = saty_atr_level(df, entry, atr_period=14, atr_multiplier=-1.0)
    truncated_df = df[df["date"] < entry].copy()
    truncated = saty_atr_level(truncated_df, entry, atr_period=14, atr_multiplier=-1.0)

    assert full is not None and truncated is not None
    assert full.level == pytest.approx(truncated.level)
    assert full.prev_close == pytest.approx(truncated.prev_close)
    assert full.atr == pytest.approx(truncated.atr)
    assert full.ref_week_end == truncated.ref_week_end


def test_use_previous_close_false_raises():
    dates = _daily_range("2023-01-02", 100)
    df = pd.DataFrame(
        {
            "date": dates,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 0.0,
        }
    )
    with pytest.raises(NotImplementedError):
        saty_atr_level(df, pd.Timestamp("2023-03-01"), use_previous_close=False)
