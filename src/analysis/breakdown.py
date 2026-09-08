"""Analizy pogłębione wyników: rozbicie roczne, zachowanie w krachach, tail risk.

Wszystko liczone ze zrealizowanych transakcji (kolumny ``entry_date``, ``pnl_cash``,
opcjonalnie ``outcome``). Wyniki bazują na wycenie PROXY — traktuj jako przybliżenie.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Domyślne okna „stresowe" (można nadpisać w wywołaniu).
DEFAULT_STRESS_PERIODS: dict[str, tuple[str, str]] = {
    "COVID crash 2020": ("2020-02-19", "2020-04-30"),
    "Bear market 2022": ("2022-01-01", "2022-12-31"),
    "2018 Q4 selloff": ("2018-10-01", "2018-12-31"),
}


def _summary(pnl: np.ndarray) -> dict:
    if pnl.size == 0:
        return {
            "n_trades": 0, "n_wins": 0, "win_rate": 0.0, "total_pnl": 0.0,
            "avg_pnl": 0.0, "best": 0.0, "worst": 0.0,
        }
    wins = int((pnl > 0).sum())
    return {
        "n_trades": int(pnl.size),
        "n_wins": wins,
        "win_rate": wins / pnl.size,
        "total_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean()),
        "best": float(pnl.max()),
        "worst": float(pnl.min()),
    }


def yearly_breakdown(results: pd.DataFrame, pnl_col: str = "pnl_cash") -> pd.DataFrame:
    """Rozbicie wyników rok po roku (wg roku daty wejścia)."""
    if results.empty:
        return pd.DataFrame(
            columns=["year", "n_trades", "n_wins", "win_rate", "total_pnl", "avg_pnl", "best", "worst"]
        )

    df = results.copy()
    df["year"] = pd.to_datetime(df["entry_date"]).dt.year
    rows = []
    for year, grp in df.groupby("year"):
        s = _summary(grp[pnl_col].to_numpy(dtype=float))
        s["year"] = int(year)
        rows.append(s)
    out = pd.DataFrame(rows)
    cols = ["year", "n_trades", "n_wins", "win_rate", "total_pnl", "avg_pnl", "best", "worst"]
    return out[cols].sort_values("year").reset_index(drop=True)


def period_breakdown(
    results: pd.DataFrame,
    periods: dict[str, tuple[str, str]] | None = None,
    pnl_col: str = "pnl_cash",
) -> pd.DataFrame:
    """Rozbicie wyników dla nazwanych okien czasowych (np. krachów)."""
    if periods is None:
        periods = DEFAULT_STRESS_PERIODS

    dates = pd.to_datetime(results["entry_date"]) if not results.empty else pd.Series([], dtype="datetime64[ns]")
    rows = []
    for name, (start, end) in periods.items():
        if results.empty:
            s = _summary(np.array([]))
        else:
            mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
            s = _summary(results.loc[mask.to_numpy(), pnl_col].to_numpy(dtype=float))
        s["period"] = name
        s["start"] = start
        s["end"] = end
        rows.append(s)
    out = pd.DataFrame(rows)
    cols = ["period", "start", "end", "n_trades", "n_wins", "win_rate", "total_pnl", "avg_pnl", "best", "worst"]
    return out[cols]


def tail_stats(
    results: pd.DataFrame,
    pnl_col: str = "pnl_cash",
    *,
    n_worst: int = 10,
    alpha: float = 0.05,
) -> dict:
    """Statystyki ogona strat: percentyle, VaR i CVaR (Expected Shortfall).

    - ``var`` (Value at Risk) = kwantyl ``alpha`` rozkładu P&L (np. 5. percentyl),
    - ``cvar`` (Expected Shortfall) = średni P&L w najgorszych ``alpha`` przypadkach,
    - ``worst_trades`` = DataFrame ``n_worst`` najgorszych transakcji.
    """
    if results.empty:
        return {
            "var": 0.0, "cvar": 0.0, "p1": 0.0, "p5": 0.0, "p50": 0.0,
            "worst_trades": results.copy(),
        }

    pnl = results[pnl_col].to_numpy(dtype=float)
    var = float(np.quantile(pnl, alpha))
    tail = pnl[pnl <= var]
    cvar = float(tail.mean()) if tail.size else var

    worst_cols = [c for c in ["entry_date", "expiration_date", "settle_price", pnl_col, "outcome"] if c in results.columns]
    worst = results.nsmallest(n_worst, pnl_col)[worst_cols].reset_index(drop=True)

    return {
        "var": var,
        "cvar": cvar,
        "p1": float(np.quantile(pnl, 0.01)),
        "p5": float(np.quantile(pnl, 0.05)),
        "p50": float(np.quantile(pnl, 0.50)),
        "worst_trades": worst,
    }
