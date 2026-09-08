"""Wycena PROXY put credit spreadu (kredyt/premia) modelem Black-Scholes.

DLACZEGO PROXY, A NIE PRAWDZIWE CENY:
Nie istnieją w pełni darmowe historyczne ceny (bid/ask) opcji SPX (patrz
DATA_SOURCE_REPORT.md). Dlatego kredyt szacujemy modelem Black-Scholes na cenie
indeksu SPX, ze zmiennością wyprowadzoną z VIX i prostym skewem dla putów OTM.

TO NIE SĄ PRAWDZIWE HISTORYCZNE CENY OPCJI — to model. Każdy wynik oparty na tej
wycenie należy traktować jako przybliżenie (PROXY), nie fakt rynkowy.

Model (europejski put, rozliczenie gotówkowe — pasuje do SPX):
    d1 = (ln(S/K) + (r + 0.5*sigma^2)*T) / (sigma*sqrt(T))
    d2 = d1 - sigma*sqrt(T)
    put = K*exp(-r*T)*N(-d2) - S*N(-d1)

Zmienność dla danego strike'a (prosty skew putowy):
    sigma(K) = base_vol + skew_slope * max(0, (S - K) / S)
gdzie ``base_vol = VIX/100`` (zannualizowana), a ``skew_slope`` to założenie
konfiguracyjne (im głębiej OTM put, tym wyższa zmienność).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


def norm_cdf(x: float) -> float:
    """Dystrybuanta standardowego rozkładu normalnego (bez scipy)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Cena europejskiego puta wg Black-Scholes (w punktach indeksu).

    Obsługuje przypadki brzegowe: ``T<=0`` lub ``sigma<=0`` -> wartość wewnętrzna
    (zdyskontowana), co odpowiada braku wartości czasowej.
    """
    if S <= 0 or K <= 0:
        raise ValueError("S i K muszą być dodatnie")
    if T <= 0 or sigma <= 0:
        return max(K * math.exp(-r * max(T, 0.0)) - S, 0.0)

    sqrt_t = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


def vol_for_strike(base_vol: float, S: float, K: float, skew_slope: float) -> float:
    """Zmienność skorygowana o prosty skew putowy (dla K < S rośnie)."""
    moneyness = max(0.0, (S - K) / S) if S > 0 else 0.0
    return max(1e-6, base_vol + skew_slope * moneyness)


@dataclass(frozen=True)
class SpreadPricing:
    """Wynik wyceny PROXY put credit spreadu w dniu wejścia."""

    spot: float                  # cena SPX użyta jako underlying
    base_vol: float              # bazowa zmienność (VIX/100)
    T: float                     # czas do wygaśnięcia w latach
    r: float                     # stopa wolna od ryzyka
    short_strike: float
    long_strike: float
    short_put: float             # cena short puta (punkty)
    long_put: float              # cena long puta (punkty)
    short_vol: float
    long_vol: float
    credit_points: float         # premia netto w punktach indeksu
    credit_cash: float           # premia w USD (credit_points * multiplier)
    max_profit_cash: float       # = credit_cash
    max_loss_cash: float         # = (wing - credit_points) * multiplier
    multiplier: float
    is_proxy: bool = True        # ZAWSZE True — to model, nie realne ceny


def price_spread(
    *,
    spot: float,
    base_vol: float,
    short_strike: float,
    long_strike: float,
    dte_days: int,
    r: float = 0.03,
    skew_slope: float = 0.8,
    multiplier: float = 100.0,
    day_count: int = 365,
) -> SpreadPricing:
    """Wycenia put credit spread (short wyższy strike, long niższy) modelem PROXY.

    ``base_vol`` to zannualizowana zmienność w ułamku (np. VIX/100 = 0.18).
    """
    if short_strike <= long_strike:
        raise ValueError("short_strike musi być > long_strike (put credit spread)")

    T = max(dte_days, 0) / float(day_count)
    short_vol = vol_for_strike(base_vol, spot, short_strike, skew_slope)
    long_vol = vol_for_strike(base_vol, spot, long_strike, skew_slope)

    short_put = bs_put_price(spot, short_strike, T, r, short_vol)
    long_put = bs_put_price(spot, long_strike, T, r, long_vol)

    credit_points = short_put - long_put
    wing = short_strike - long_strike
    credit_cash = credit_points * multiplier
    max_loss_cash = (wing - credit_points) * multiplier

    return SpreadPricing(
        spot=float(spot),
        base_vol=float(base_vol),
        T=T,
        r=r,
        short_strike=float(short_strike),
        long_strike=float(long_strike),
        short_put=short_put,
        long_put=long_put,
        short_vol=short_vol,
        long_vol=long_vol,
        credit_points=credit_points,
        credit_cash=credit_cash,
        max_profit_cash=credit_cash,
        max_loss_cash=max_loss_cash,
        multiplier=float(multiplier),
    )


def _date_value_map(daily: pd.DataFrame, column: str) -> dict:
    """Buduje mapę: znormalizowana data -> wartość kolumny (np. open/close)."""
    df = daily[["date", column]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return dict(zip(df["date"], df[column].astype(float)))


def price_all_spreads(
    plans: pd.DataFrame,
    spx_daily: pd.DataFrame,
    vix_daily: pd.DataFrame,
    *,
    spot_basis: str = "open",
    vol_basis: str = "open",
    r: float = 0.03,
    skew_slope: float = 0.8,
    multiplier: float = 100.0,
    day_count: int = 365,
) -> pd.DataFrame:
    """Wycenia PROXY każdy spread z tabeli planów, dołączając kolumny wyceny.

    Dla każdego wiersza pobiera cenę SPX (``spot_basis``) i VIX (``vol_basis``) z
    **dnia wejścia** — brak look-ahead (dane z dnia wejścia są dostępne w dniu wejścia).
    Wiersze bez ceny/VIX na dzień wejścia są pomijane.

    Dokłada kolumny: ``spot, base_vol, T, short_put, long_put, short_vol, long_vol,
    credit_points, credit_cash, max_profit_cash, max_loss_cash, is_proxy``.
    """
    if plans.empty:
        return plans.copy()

    spot_map = _date_value_map(spx_daily, spot_basis)
    vix_map = _date_value_map(vix_daily, vol_basis)

    rows = []
    for _, plan in plans.iterrows():
        entry = pd.Timestamp(plan["entry_date"]).normalize()
        spot = spot_map.get(entry)
        vix = vix_map.get(entry)
        if spot is None or vix is None:
            continue

        pricing = price_spread(
            spot=spot,
            base_vol=vix / 100.0,
            short_strike=float(plan["short_strike"]),
            long_strike=float(plan["long_strike"]),
            dte_days=int(plan["dte"]),
            r=r,
            skew_slope=skew_slope,
            multiplier=multiplier,
            day_count=day_count,
        )
        row = dict(plan)
        row.update(
            spot=pricing.spot,
            base_vol=pricing.base_vol,
            T=pricing.T,
            short_put=pricing.short_put,
            long_put=pricing.long_put,
            short_vol=pricing.short_vol,
            long_vol=pricing.long_vol,
            credit_points=pricing.credit_points,
            credit_cash=pricing.credit_cash,
            max_profit_cash=pricing.max_profit_cash,
            max_loss_cash=pricing.max_loss_cash,
            is_proxy=True,
        )
        rows.append(row)

    return pd.DataFrame(rows)
