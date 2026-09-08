"""Testy warstwy wyboru spreadu: daty wejścia, ekspiracje, strike'i, brak look-ahead."""

import numpy as np
import pandas as pd
import pytest

from src.strategy.spread_selection import (
    build_all_spreads,
    build_spread_plan,
    expiration_for_entry,
    round_to_increment,
    trading_days,
    weekly_entry_dates,
)


def _make_daily(start: str, periods: int, seed: int = 0) -> pd.DataFrame:
    dates = pd.bdate_range(start=start, periods=periods)
    rng = np.random.default_rng(seed)
    base = 4000 + np.cumsum(rng.normal(0, 15, len(dates)))
    return pd.DataFrame(
        {
            "date": dates,
            "open": base,
            "high": base + 20,
            "low": base - 20,
            "close": base + 5,
            "volume": 0.0,
        }
    )


def test_round_to_increment():
    assert round_to_increment(7535.93, 5) == 7535.0
    assert round_to_increment(7538.0, 5) == 7540.0
    assert round_to_increment(102.5, 5) == 100.0  # bankers? round(20.5)->20 -> 100
    with pytest.raises(ValueError):
        round_to_increment(100, 0)


def test_weekly_entry_dates_are_first_trading_day():
    # 3 pełne tygodnie robocze zaczynając w poniedziałek.
    df = _make_daily("2024-01-01", 15)  # 3 tygodnie po 5 dni
    entries = weekly_entry_dates(df)
    assert len(entries) == 3
    for e in entries:
        assert e.weekday() == 0  # poniedziałek


def test_weekly_entry_skips_holiday_monday():
    # Usuń poniedziałek pierwszego tygodnia -> wejście przesuwa się na wtorek.
    df = _make_daily("2024-01-01", 15)
    df = df[df["date"] != pd.Timestamp("2024-01-01")].reset_index(drop=True)
    entries = weekly_entry_dates(df)
    assert entries[0] == pd.Timestamp("2024-01-02")  # wtorek
    assert entries[0].weekday() == 1


def test_expiration_is_same_week_friday():
    df = _make_daily("2024-01-01", 15)
    days = trading_days(df)
    exp = expiration_for_entry(pd.Timestamp("2024-01-01"), days)  # poniedziałek
    assert exp == pd.Timestamp("2024-01-05")  # piątek tego tygodnia
    assert exp.weekday() == 4


def test_expiration_falls_back_when_friday_missing():
    # Usuń piątek -> ekspiracja spada na czwartek.
    df = _make_daily("2024-01-01", 15)
    df = df[df["date"] != pd.Timestamp("2024-01-05")].reset_index(drop=True)
    days = trading_days(df)
    exp = expiration_for_entry(pd.Timestamp("2024-01-01"), days)
    assert exp == pd.Timestamp("2024-01-04")  # czwartek
    assert exp.weekday() == 3


def test_expiration_none_for_incomplete_last_week():
    # Wejście po ostatnim dniu danych -> brak dnia wygaśnięcia.
    df = _make_daily("2024-01-01", 5)
    days = trading_days(df)
    exp = expiration_for_entry(pd.Timestamp("2024-01-08"), days)
    assert exp is None


def test_build_spread_plan_strikes():
    df = _make_daily("2023-01-02", 120)
    entries = weekly_entry_dates(df)
    entry = entries[-2]  # przedostatni tydzień (pełny)
    plan = build_spread_plan(
        df, entry, atr_period=14, atr_multiplier=-1.0,
        wing_width=50.0, strike_increment=5.0,
    )
    assert plan is not None
    # short strike = poziom zaokrąglony do 5.
    assert plan.short_strike == round_to_increment(plan.raw_level, 5.0)
    # long strike = short - 50, na siatce.
    assert plan.long_strike == plan.short_strike - 50.0
    # strike'i na siatce 5.
    assert plan.short_strike % 5 == 0
    assert plan.long_strike % 5 == 0
    # ekspiracja po wejściu, DTE dodatnie.
    assert plan.expiration_date >= plan.entry_date
    assert plan.dte >= 0


def test_build_spread_plan_none_when_insufficient():
    df = _make_daily("2024-01-01", 10)  # < 14 tygodni ATR
    entries = weekly_entry_dates(df)
    plan = build_spread_plan(df, entries[-1])
    assert plan is None


def test_no_look_ahead_spread_stable_under_truncation():
    df = _make_daily("2022-01-03", 200, seed=42)
    entry = pd.Timestamp("2022-08-01")  # poniedziałek w środku danych

    # Kalendarz ekspiracji jest znany z góry (harmonogram sesji), więc podajemy
    # pełny days_index. Look-ahead badamy dla CEN: obcinamy dane cenowe do < entry.
    full_days = trading_days(df)
    full = build_spread_plan(df, entry, days_index=full_days)
    truncated = build_spread_plan(
        df[df["date"] < entry].reset_index(drop=True), entry, days_index=full_days
    )

    assert full is not None and truncated is not None
    # short/long strike zależą tylko od poprzedniego tygodnia -> muszą być równe.
    assert full.short_strike == truncated.short_strike
    assert full.long_strike == truncated.long_strike
    assert full.raw_level == pytest.approx(truncated.raw_level)


def test_build_all_spreads_table_shape():
    df = _make_daily("2022-01-03", 120)
    table = build_all_spreads(df)
    assert not table.empty
    expected_cols = {
        "entry_date", "expiration_date", "dte", "ref_week_end",
        "prev_close", "atr", "raw_level", "short_strike", "long_strike", "wing_width",
    }
    assert expected_cols.issubset(set(table.columns))
    # Każdy short > long (put credit spread).
    assert (table["short_strike"] > table["long_strike"]).all()
