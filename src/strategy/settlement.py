"""Rozliczenie put credit spreadu na wygaśnięciu (cash settlement, SPX/SPXW).

SPX/SPXW są rozliczane GOTÓWKOWO w stylu europejskim (brak wcześniejszego
wykonania). Trzymamy spread do wygaśnięcia, więc wynik zależy wyłącznie od ceny
rozliczenia indeksu w dniu wygaśnięcia:

    wartość spreadu na wygaśnięciu (to, co "oddajemy") =
        max(0, short_K - S_settle) - max(0, long_K - S_settle)

Zrealizowany wynik transakcji (w punktach):
    pnl_points = credit_points - wartość_spreadu_na_wygaśnięciu

Trzy możliwe wyniki:
- S_settle >= short_K            -> oba puty bezwartościowe -> MAKS. ZYSK (cały kredyt),
- long_K < S_settle < short_K    -> częściowa strata,
- S_settle <= long_K             -> pełna szerokość skrzydła -> MAKS. STRATA.

UWAGA: użycie ceny z dnia wygaśnięcia NIE jest look-ahead — to realizacja wyniku
pozycji trzymanej do wygaśnięcia, a nie informacja użyta do podjęcia decyzji.
Cena rozliczenia SPXW = zamknięcie w dniu wygaśnięcia (PM-settled).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def put_intrinsic(strike: float, spot_settle: float) -> float:
    """Wartość wewnętrzna puta na wygaśnięciu: max(0, K - S)."""
    return max(0.0, strike - spot_settle)


def spread_value_at_expiry(
    short_strike: float, long_strike: float, spot_settle: float
) -> float:
    """Wartość put credit spreadu na wygaśnięciu (w punktach, w przedziale [0, wing])."""
    return put_intrinsic(short_strike, spot_settle) - put_intrinsic(long_strike, spot_settle)


@dataclass(frozen=True)
class SpreadOutcome:
    """Zrealizowany wynik pojedynczego spreadu na wygaśnięciu."""

    settle_price: float
    spread_value_points: float   # ile oddajemy na wygaśnięciu
    pnl_points: float            # credit_points - spread_value_points
    pnl_cash: float              # pnl_points * multiplier
    outcome: str                 # "max_profit" | "partial_loss" | "max_loss"
    is_win: bool                 # pnl_cash > 0


def settle_spread(
    *,
    credit_points: float,
    short_strike: float,
    long_strike: float,
    spot_settle: float,
    multiplier: float = 100.0,
) -> SpreadOutcome:
    """Rozlicza spread na wygaśnięciu przy danej cenie rozliczenia indeksu."""
    value = spread_value_at_expiry(short_strike, long_strike, spot_settle)
    pnl_points = credit_points - value
    pnl_cash = pnl_points * multiplier

    if spot_settle >= short_strike:
        outcome = "max_profit"
    elif spot_settle <= long_strike:
        outcome = "max_loss"
    else:
        outcome = "partial_loss"

    return SpreadOutcome(
        settle_price=float(spot_settle),
        spread_value_points=float(value),
        pnl_points=float(pnl_points),
        pnl_cash=float(pnl_cash),
        outcome=outcome,
        is_win=bool(pnl_cash > 0),
    )


def _date_value_map(daily: pd.DataFrame, column: str) -> dict:
    df = daily[["date", column]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return dict(zip(df["date"], df[column].astype(float)))


def settle_all_spreads(
    priced: pd.DataFrame,
    spx_daily: pd.DataFrame,
    *,
    settle_basis: str = "close",
    multiplier: float = 100.0,
) -> pd.DataFrame:
    """Rozlicza każdy wyceniony spread na jego dacie wygaśnięcia.

    Pobiera cenę rozliczenia (``settle_basis``, domyślnie ``close``) z dnia
    wygaśnięcia. Wiersze bez ceny rozliczenia (brak danych na ten dzień) są pomijane.

    Dokłada kolumny: ``settle_price, spread_value_points, pnl_points, pnl_cash,
    outcome, is_win``.
    """
    if priced.empty:
        return priced.copy()

    settle_map = _date_value_map(spx_daily, settle_basis)

    rows = []
    for _, r in priced.iterrows():
        exp = pd.Timestamp(r["expiration_date"]).normalize()
        settle = settle_map.get(exp)
        if settle is None:
            continue

        outcome = settle_spread(
            credit_points=float(r["credit_points"]),
            short_strike=float(r["short_strike"]),
            long_strike=float(r["long_strike"]),
            spot_settle=settle,
            multiplier=multiplier,
        )
        row = dict(r)
        row.update(
            settle_price=outcome.settle_price,
            spread_value_points=outcome.spread_value_points,
            pnl_points=outcome.pnl_points,
            pnl_cash=outcome.pnl_cash,
            outcome=outcome.outcome,
            is_win=outcome.is_win,
        )
        rows.append(row)

    return pd.DataFrame(rows)
