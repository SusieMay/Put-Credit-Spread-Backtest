"""Warstwa strategii: wybór konkretnego put credit spreadu na każdy tydzień.

Ten moduł przekształca surowy poziom Saty ATR -1 (z warstwy wskaźników) w
konkretny, wykonalny spread na dany tydzień:

- **data wejścia** – pierwszy dzień handlowy tygodnia (docelowo poniedziałek; jeśli
  poniedziałek to święto, bierzemy pierwszy dostępny dzień handlowy),
- **ekspiracja** – najbliższy piątek SPXW tego samego tygodnia (a jeśli piątek jest
  wolny, ostatni dzień handlowy tego tygodnia),
- **short strike** – poziom Saty ATR -1 zaokrąglony do siatki strike'ów (np. co 5 pkt),
- **long strike** – short strike minus szerokość skrzydła (``wing_width``, domyślnie 50),
  również na siatce strike'ów.

WAŻNE: nie ma tu żadnego look-ahead. Poziom pochodzi z poprzedniego zakończonego
tygodnia (patrz ``src/indicators/atr.py``), a ceny wykonania liczymy wyłącznie z
danych dostępnych w/przed dniem wejścia.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.indicators.atr import saty_atr_level


def round_to_increment(value: float, increment: float) -> float:
    """Zaokrągla wartość do najbliższej wielokrotności ``increment`` (siatka strike'ów)."""
    if increment <= 0:
        raise ValueError("increment musi być dodatnie")
    return round(value / increment) * increment


def trading_days(daily: pd.DataFrame) -> pd.DatetimeIndex:
    """Zwraca posortowany, unikalny indeks dni handlowych z danych dziennych."""
    dates = pd.to_datetime(daily["date"]).drop_duplicates().sort_values()
    return pd.DatetimeIndex(dates.to_numpy())


def weekly_entry_dates(daily: pd.DataFrame) -> list[pd.Timestamp]:
    """Wyznacza daty wejścia = pierwszy dzień handlowy każdego tygodnia kalendarzowego.

    Zwykle poniedziałek; po święcie (np. Nowy Rok) – pierwszy dostępny dzień handlowy.
    """
    days = trading_days(daily)
    if len(days) == 0:
        return []
    iso = days.isocalendar()
    key = list(zip(iso["year"].to_numpy(), iso["week"].to_numpy()))
    entries: list[pd.Timestamp] = []
    seen: set[tuple[int, int]] = set()
    for ts, k in zip(days, key):
        if k not in seen:
            seen.add(k)
            entries.append(pd.Timestamp(ts))
    return entries


def expiration_for_entry(
    entry_date,
    days_index: pd.DatetimeIndex,
    *,
    calendar_fallback: bool = False,
) -> pd.Timestamp | None:
    """Znajduje datę wygaśnięcia dla wejścia: najbliższy piątek tego samego tygodnia.

    Jeśli dokładny piątek nie jest dniem handlowym (święto), bierze ostatni dzień
    handlowy tego tygodnia przypadający na/przed piątkiem (zwykle czwartek).

    Zwraca ``None``, gdy w danych nie ma żadnego pasującego dnia handlowego
    (np. brak danych do końca tygodnia – ostatni, niepełny tydzień). Jeśli
    ``calendar_fallback=True``, zamiast ``None`` zwraca kalendarzowy piątek (użyteczne
    tylko do PODGLĄDU przyszłego tygodnia — nie w backteście).
    """
    entry_ts = pd.Timestamp(entry_date).normalize()
    # Piątek tego samego tygodnia: Monday=0 ... Friday=4.
    friday_target = entry_ts + pd.Timedelta(days=(4 - entry_ts.weekday()))
    if friday_target < entry_ts:  # zabezpieczenie (wejście po piątku)
        friday_target = entry_ts + pd.Timedelta(days=(4 - entry_ts.weekday()) % 7)

    # Kandydaci: dni handlowe w oknie [entry_date, friday_target].
    mask = (days_index >= entry_ts) & (days_index <= friday_target)
    window = days_index[mask]
    if len(window) == 0:
        return friday_target if calendar_fallback else None
    return pd.Timestamp(window[-1])


@dataclass(frozen=True)
class SpreadPlan:
    """Konkretny put credit spread zaplanowany na dany tydzień."""

    entry_date: pd.Timestamp
    expiration_date: pd.Timestamp
    dte: int                       # dni kalendarzowe do wygaśnięcia
    ref_week_end: pd.Timestamp     # koniec poprzedniego zakończonego tygodnia
    prev_close: float
    atr: float
    raw_level: float               # niezaokrąglony poziom Saty ATR -1
    short_strike: float            # zaokrąglony do siatki
    long_strike: float             # short_strike - wing_width, na siatce
    wing_width: float


def build_spread_plan(
    daily: pd.DataFrame,
    entry_date,
    *,
    atr_period: int = 14,
    atr_multiplier: float = -1.0,
    wing_width: float = 50.0,
    strike_increment: float = 5.0,
    days_index: pd.DatetimeIndex | None = None,
    calendar_fallback: bool = False,
) -> SpreadPlan | None:
    """Buduje plan spreadu dla pojedynczej daty wejścia (bez look-ahead).

    Zwraca ``None``, gdy brak poziomu Saty (za mało danych) lub brak dnia
    wygaśnięcia w danych. ``calendar_fallback=True`` służy tylko do podglądu
    przyszłego tygodnia (nie używać w backteście).
    """
    if days_index is None:
        days_index = trading_days(daily)

    level = saty_atr_level(
        daily,
        entry_date,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
    )
    if level is None:
        return None

    expiration = expiration_for_entry(
        entry_date, days_index, calendar_fallback=calendar_fallback
    )
    if expiration is None:
        return None

    short_strike = round_to_increment(level.level, strike_increment)
    long_strike = round_to_increment(short_strike - wing_width, strike_increment)

    entry_ts = pd.Timestamp(entry_date).normalize()
    dte = int((expiration.normalize() - entry_ts).days)

    return SpreadPlan(
        entry_date=entry_ts,
        expiration_date=expiration,
        dte=dte,
        ref_week_end=level.ref_week_end,
        prev_close=level.prev_close,
        atr=level.atr,
        raw_level=level.level,
        short_strike=float(short_strike),
        long_strike=float(long_strike),
        wing_width=float(wing_width),
    )


def build_all_spreads(
    daily: pd.DataFrame,
    *,
    atr_period: int = 14,
    atr_multiplier: float = -1.0,
    wing_width: float = 50.0,
    strike_increment: float = 5.0,
) -> pd.DataFrame:
    """Buduje tabelę planów spreadów dla każdego tygodnia w danych.

    Pomija tygodnie bez wystarczających danych (początek serii) oraz ostatni,
    niepełny tydzień bez dnia wygaśnięcia.

    Returns
    -------
    pandas.DataFrame
        Po jednym wierszu na tydzień; kolumny odpowiadają polom ``SpreadPlan``.
    """
    days_index = trading_days(daily)
    rows = []
    for entry in weekly_entry_dates(daily):
        plan = build_spread_plan(
            daily,
            entry,
            atr_period=atr_period,
            atr_multiplier=atr_multiplier,
            wing_width=wing_width,
            strike_increment=strike_increment,
            days_index=days_index,
        )
        if plan is not None:
            rows.append(plan.__dict__)
    return pd.DataFrame(rows)
