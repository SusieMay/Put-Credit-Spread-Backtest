"""Wilder ATR na interwale tygodniowym oraz poziom "Multi-Day Saty ATR -1".

Definicja odtworzona wprost z open-source Pine Script Saty Mahajana
(patrz docs/SATY_ATR_DEFINITION.md). Skrót:

    Multi-Day Saty ATR -1 = (zamknięcie poprzedniego tygodnia)
                            - (14-okresowy Wilder ATR na świecach tygodniowych,
                               z poprzedniego zakończonego tygodnia)

Kluczowe fakty odwzorowane tutaj:
- interwał tygodniowy (świece Mon-Fri, etykieta = piątek),
- ATR = Wilder RMA z True Range (nie SMA/EMA),
- True Range uwzględnia lukę do poprzedniego zamknięcia tygodniowego,
- używamy POPRZEDNIEGO zakończonego tygodnia (period_index = 1) -> brak look-ahead.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

OHLC_COLUMNS = ["open", "high", "low", "close"]


def resample_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Agreguje dzienne OHLC do świec tygodniowych (tydzień kończy się w piątek).

    Parameters
    ----------
    daily:
        DataFrame z kolumnami ``date, open, high, low, close`` (i opcjonalnie ``volume``).

    Returns
    -------
    pandas.DataFrame
        Kolumny: ``week_end`` (piątek danego tygodnia), ``open, high, low, close,
        volume``. Tygodnie bez danych (np. święta) są pomijane.
    """
    if daily.empty:
        return pd.DataFrame(columns=["week_end", *OHLC_COLUMNS, "volume"])

    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")

    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"

    weekly = df.resample("W-FRI").agg(agg)
    weekly = weekly.dropna(subset=["close"]).reset_index()
    weekly = weekly.rename(columns={"date": "week_end"})
    if "volume" not in weekly.columns:
        weekly["volume"] = 0.0
    return weekly.reset_index(drop=True)


def true_range(weekly: pd.DataFrame) -> pd.Series:
    """Liczy True Range dla świec tygodniowych.

    TR = max(H-L, |H - C_prev|, |L - C_prev|); dla pierwszej świecy TR = H-L.
    """
    high = weekly["high"]
    low = weekly["low"]
    prev_close = weekly["close"].shift(1)

    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    if len(weekly) > 0:
        tr.iloc[0] = weekly["high"].iloc[0] - weekly["low"].iloc[0]
    return tr


def wilder_rma(series: pd.Series, period: int) -> pd.Series:
    """Wilder RMA (moving average Wildera), zgodne z Pine ``ta.rma``.

    Seed = SMA pierwszych ``period`` wartości (umieszczony na indeksie ``period-1``),
    potem rekurencyjnie: ``rma[i] = (rma[i-1]*(period-1) + x[i]) / period``.
    Wartości przed indeksem ``period-1`` są NaN.
    """
    if period <= 0:
        raise ValueError("period musi być dodatnie")

    arr = series.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    if len(arr) < period:
        return pd.Series(out, index=series.index)

    out[period - 1] = arr[:period].mean()
    for i in range(period, len(arr)):
        out[i] = (out[i - 1] * (period - 1) + arr[i]) / period
    return pd.Series(out, index=series.index)


def weekly_atr_table(daily: pd.DataFrame, atr_period: int = 14) -> pd.DataFrame:
    """Buduje tygodniową tabelę OHLC + True Range + Wilder ATR.

    Returns
    -------
    pandas.DataFrame
        Kolumny: ``week_end, open, high, low, close, volume, tr, atr``.
    """
    weekly = resample_weekly(daily)
    weekly["tr"] = true_range(weekly)
    weekly["atr"] = wilder_rma(weekly["tr"], atr_period)
    return weekly


@dataclass(frozen=True)
class SatyLevel:
    """Wynik wyliczenia poziomu Saty ATR dla danej daty wejścia."""

    entry_date: pd.Timestamp
    ref_week_end: pd.Timestamp   # koniec poprzedniego zakończonego tygodnia
    prev_close: float            # zamknięcie poprzedniego tygodnia
    atr: float                   # tygodniowy Wilder ATR (poprzedni tydzień)
    atr_multiplier: float        # np. -1.0 dla poziomu "-1 ATR"
    level: float                 # prev_close + atr_multiplier * atr


def saty_atr_level(
    daily: pd.DataFrame,
    entry_date,
    atr_period: int = 14,
    atr_multiplier: float = -1.0,
    use_previous_close: bool = True,
) -> SatyLevel | None:
    """Wylicza poziom Saty ATR dla daty wejścia, bez look-ahead.

    Bierze pod uwagę wyłącznie tygodnie **zakończone przed** ``entry_date``
    (odpowiednik ``period_index = 1`` w Pine). Poziom:

        level = prev_close + atr_multiplier * atr

    gdzie ``prev_close`` i ``atr`` pochodzą z ostatniego zakończonego tygodnia.

    Returns
    -------
    SatyLevel | None
        ``None``, jeśli brak wystarczających danych (za mało tygodni na ATR).
    """
    entry_ts = pd.Timestamp(entry_date)
    table = weekly_atr_table(daily, atr_period=atr_period)

    if not use_previous_close:
        raise NotImplementedError(
            "use_previous_close=False (bieżący tydzień) nie jest wspierany — "
            "wprowadzałby look-ahead dla wejścia śróddziennego."
        )

    # Tylko tygodnie ZAKOŃCZONE przed datą wejścia (week_end < entry_date).
    completed = table[table["week_end"] < entry_ts]
    completed = completed.dropna(subset=["atr"])
    if completed.empty:
        return None

    ref = completed.iloc[-1]
    level = float(ref["close"]) + atr_multiplier * float(ref["atr"])
    return SatyLevel(
        entry_date=entry_ts,
        ref_week_end=pd.Timestamp(ref["week_end"]),
        prev_close=float(ref["close"]),
        atr=float(ref["atr"]),
        atr_multiplier=atr_multiplier,
        level=level,
    )
