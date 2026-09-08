"""Silnik portfela: sizing pozycji, krzywa kapitału i seria obsunięć (drawdown).

Bierze zrealizowane wyniki transakcji (z ``settle_all_spreads``, P&L na 1 kontrakt)
i buduje krzywą kapitału tydzień po tygodniu, skalując P&L liczbą kontraktów według
wybranej metody sizingu.

Metody sizingu:
- ``fixed_contracts``    – stała liczba kontraktów,
- ``fixed_risk_pct``     – liczba kontraktów tak, by maks. strata ≈ ``risk_pct`` * kapitał,
- ``fixed_capital_alloc``– maks. strata ≈ stała kwota ``capital_alloc``.

Kolejność transakcji: chronologicznie wg ``entry_date``. Sizing liczony jest na
kapitale SPRZED transakcji (brak look-ahead w wielkości pozycji).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


def size_position(
    *,
    equity: float,
    max_loss_per_contract: float,
    sizing: str,
    contracts: int = 1,
    risk_pct: float = 0.02,
    capital_alloc: float = 5000.0,
) -> int:
    """Zwraca liczbę kontraktów dla pojedynczej transakcji wg metody sizingu.

    Dla metod ryzykowych zwraca 0, jeśli nie stać nas na choćby 1 kontrakt
    (maks. strata na kontrakt przekracza budżet ryzyka).
    """
    if sizing == "fixed_contracts":
        return max(0, int(contracts))

    if max_loss_per_contract <= 0:
        return 0

    if sizing == "fixed_risk_pct":
        budget = max(0.0, equity) * risk_pct
    elif sizing == "fixed_capital_alloc":
        budget = capital_alloc
    else:
        raise ValueError(f"Nieznana metoda sizingu: {sizing!r}")

    return max(0, int(math.floor(budget / max_loss_per_contract)))


@dataclass(frozen=True)
class PortfolioConfig:
    initial_capital: float = 100000.0
    sizing: str = "fixed_contracts"
    contracts: int = 1
    risk_pct: float = 0.02
    capital_alloc: float = 5000.0


def build_equity_curve(
    results: pd.DataFrame,
    config: PortfolioConfig,
) -> pd.DataFrame:
    """Buduje krzywą kapitału i serię drawdown z zrealizowanych wyników.

    Oczekuje kolumn: ``entry_date, expiration_date, pnl_cash`` (P&L na 1 kontrakt)
    oraz ``max_loss_cash`` (maks. strata na 1 kontrakt) do sizingu.

    Returns
    -------
    pandas.DataFrame
        Kolumny: ``entry_date, expiration_date, contracts, trade_pnl, equity,
        peak, drawdown, drawdown_pct``. Transakcje z 0 kontraktów są pomijane.
    """
    cols = [
        "entry_date", "expiration_date", "contracts",
        "trade_pnl", "equity", "peak", "drawdown", "drawdown_pct",
    ]
    if results.empty:
        return pd.DataFrame(columns=cols)

    df = results.sort_values("entry_date").reset_index(drop=True)

    equity = float(config.initial_capital)
    peak = equity
    rows = []
    for _, r in df.iterrows():
        max_loss = abs(float(r.get("max_loss_cash", 0.0)))
        n = size_position(
            equity=equity,
            max_loss_per_contract=max_loss,
            sizing=config.sizing,
            contracts=config.contracts,
            risk_pct=config.risk_pct,
            capital_alloc=config.capital_alloc,
        )
        if n <= 0:
            continue

        trade_pnl = float(r["pnl_cash"]) * n
        equity += trade_pnl
        peak = max(peak, equity)
        drawdown = equity - peak
        drawdown_pct = (drawdown / peak) if peak > 0 else 0.0

        rows.append(
            {
                "entry_date": pd.Timestamp(r["entry_date"]),
                "expiration_date": pd.Timestamp(r["expiration_date"]),
                "contracts": n,
                "trade_pnl": trade_pnl,
                "equity": equity,
                "peak": peak,
                "drawdown": drawdown,
                "drawdown_pct": drawdown_pct,
            }
        )

    return pd.DataFrame(rows, columns=cols)


def portfolio_config_from_dict(cfg: dict) -> PortfolioConfig:
    """Tworzy ``PortfolioConfig`` z sekcji ``portfolio`` configu."""
    return PortfolioConfig(
        initial_capital=float(cfg.get("initial_capital", 100000.0)),
        sizing=str(cfg.get("sizing", "fixed_contracts")),
        contracts=int(cfg.get("contracts", 1)),
        risk_pct=float(cfg.get("risk_pct", 0.02)),
        capital_alloc=float(cfg.get("capital_alloc", 5000.0)),
    )
