"""Metryki wydajności strategii: metryki transakcyjne i oparte na krzywej kapitału.

Metryki transakcyjne (z listy zrealizowanych P&L):
- win_rate, liczba wygranych/przegranych,
- profit_factor = suma zysków / |suma strat|,
- expectancy = średni P&L na transakcję,
- avg_win, avg_loss, payoff_ratio.

Metryki portfelowe (z krzywej kapitału):
- total_return, CAGR,
- max_drawdown (USD i %),
- Sharpe, Sortino (annualizowane), Calmar = CAGR / |max drawdown %|.

UWAGA: wyniki bazują na wycenie PROXY kredytu (Black-Scholes + VIX), więc metryki są
przybliżeniem, nie faktem rynkowym.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _years_between(start, end) -> float:
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days
    return max(days / 365.25, 1e-9)


def trade_metrics(results: pd.DataFrame, pnl_col: str = "pnl_cash") -> dict:
    """Metryki na poziomie pojedynczych transakcji."""
    if results.empty:
        return {
            "n_trades": 0, "n_wins": 0, "n_losses": 0, "win_rate": 0.0,
            "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": float("nan"),
            "expectancy": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
            "payoff_ratio": float("nan"),
        }

    pnl = results[pnl_col].to_numpy(dtype=float)
    n = len(pnl)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(losses.mean()) if losses.size else 0.0

    return {
        "n_trades": n,
        "n_wins": int(wins.size),
        "n_losses": int(losses.size),
        "win_rate": wins.size / n,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else float("inf"),
        "expectancy": float(pnl.mean()),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": (avg_win / abs(avg_loss)) if avg_loss < 0 else float("inf"),
    }


def equity_metrics(
    curve: pd.DataFrame,
    initial_capital: float,
    *,
    equity_col: str = "equity",
    date_col: str = "entry_date",
) -> dict:
    """Metryki oparte na krzywej kapitału (annualizacja z rzeczywistego okresu)."""
    if curve.empty:
        return {
            "initial_capital": float(initial_capital), "final_equity": float(initial_capital),
            "total_return": 0.0, "cagr": 0.0, "years": 0.0,
            "max_drawdown": 0.0, "max_drawdown_pct": 0.0,
            "sharpe": float("nan"), "sortino": float("nan"), "calmar": float("nan"),
        }

    equity = curve[equity_col].to_numpy(dtype=float)
    dates = pd.to_datetime(curve[date_col]).reset_index(drop=True)
    final = float(equity[-1])
    years = _years_between(dates.iloc[0], dates.iloc[-1])

    total_return = final / initial_capital - 1.0
    cagr = (final / initial_capital) ** (1.0 / years) - 1.0 if final > 0 else -1.0

    # Seria kapitału z kapitałem początkowym na starcie.
    eq_full = np.concatenate([[float(initial_capital)], equity])
    returns = np.diff(eq_full) / eq_full[:-1]

    periods_per_year = len(returns) / years if years > 0 else 0.0
    ann = math.sqrt(periods_per_year) if periods_per_year > 0 else 0.0

    mean_r = float(returns.mean()) if returns.size else 0.0
    std_r = float(returns.std(ddof=1)) if returns.size > 1 else 0.0
    sharpe = (mean_r / std_r * ann) if std_r > 0 else float("nan")

    downside = returns[returns < 0]
    dstd = float(downside.std(ddof=1)) if downside.size > 1 else 0.0
    sortino = (mean_r / dstd * ann) if dstd > 0 else float("inf")

    # Max drawdown liczony na serii z kapitałem początkowym.
    peak = np.maximum.accumulate(eq_full)
    dd_abs = eq_full - peak
    dd_pct = dd_abs / peak
    max_drawdown = float(dd_abs.min())
    max_drawdown_pct = float(dd_pct.min())

    calmar = (cagr / abs(max_drawdown_pct)) if max_drawdown_pct < 0 else float("inf")

    return {
        "initial_capital": float(initial_capital),
        "final_equity": final,
        "total_return": total_return,
        "cagr": cagr,
        "years": years,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
    }


def compute_metrics(
    results: pd.DataFrame,
    curve: pd.DataFrame,
    initial_capital: float,
    *,
    pnl_col: str = "pnl_cash",
) -> dict:
    """Łączy metryki transakcyjne i portfelowe w jeden słownik."""
    out = trade_metrics(results, pnl_col=pnl_col)
    out.update(equity_metrics(curve, initial_capital))
    return out
