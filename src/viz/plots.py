"""Wizualizacje wyników backtestu (matplotlib, zapis do plików PNG).

Używamy nieinteraktywnego backendu ``Agg`` (zapis do plików, bez okien) — działa
w terminalu i w CI. Wykresy:
- krzywa kapitału (equity curve),
- obsunięcia (underwater / drawdown),
- histogram P&L transakcji,
- słupki wyniku rok po roku.

UWAGA: dane pochodzą z wyceny PROXY (BS+VIX) — wykresy są przybliżeniem.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend bez okien (zapis do plików)

import matplotlib.pyplot as plt
import pandas as pd

PROXY_NOTE = "PROXY (model BS+VIX) — nie realne ceny opcji"


def _ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def plot_equity_curve(curve: pd.DataFrame, out_path: str | Path) -> Path:
    """Rysuje krzywą kapitału i zapisuje do pliku PNG."""
    p = _ensure_dir(out_path)
    fig, ax = plt.subplots(figsize=(11, 5))
    if not curve.empty:
        x = pd.to_datetime(curve["entry_date"])
        ax.plot(x, curve["equity"], color="#1f77b4", linewidth=1.3)
        ax.fill_between(x, curve["equity"], curve["equity"].min(), alpha=0.08, color="#1f77b4")
    ax.set_title(f"Krzywa kapitału — {PROXY_NOTE}")
    ax.set_xlabel("Data wejścia")
    ax.set_ylabel("Kapitał (USD)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    return p


def plot_drawdown(curve: pd.DataFrame, out_path: str | Path) -> Path:
    """Rysuje wykres obsunięć (underwater, w %) i zapisuje do pliku PNG."""
    p = _ensure_dir(out_path)
    fig, ax = plt.subplots(figsize=(11, 4))
    if not curve.empty:
        x = pd.to_datetime(curve["entry_date"])
        dd_pct = curve["drawdown_pct"] * 100
        ax.fill_between(x, dd_pct, 0, color="#d62728", alpha=0.35)
        ax.plot(x, dd_pct, color="#d62728", linewidth=1.0)
    ax.set_title(f"Obsunięcia kapitału (drawdown) — {PROXY_NOTE}")
    ax.set_xlabel("Data wejścia")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    return p


def plot_pnl_histogram(results: pd.DataFrame, out_path: str | Path, pnl_col: str = "pnl_cash") -> Path:
    """Rysuje histogram P&L transakcji i zapisuje do pliku PNG."""
    p = _ensure_dir(out_path)
    fig, ax = plt.subplots(figsize=(9, 5))
    if not results.empty:
        pnl = results[pnl_col].to_numpy(dtype=float)
        ax.hist(pnl, bins=50, color="#2ca02c", alpha=0.75, edgecolor="white")
        ax.axvline(0, color="black", linewidth=0.8)
        ax.axvline(pnl.mean(), color="#ff7f0e", linestyle="--", linewidth=1.2,
                   label=f"średnia = {pnl.mean():,.0f} USD")
        ax.legend()
    ax.set_title(f"Rozkład P&L transakcji — {PROXY_NOTE}")
    ax.set_xlabel("P&L transakcji (USD)")
    ax.set_ylabel("Liczba transakcji")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    return p


def plot_yearly_pnl(yearly: pd.DataFrame, out_path: str | Path) -> Path:
    """Rysuje słupki wyniku rok po roku i zapisuje do pliku PNG."""
    p = _ensure_dir(out_path)
    fig, ax = plt.subplots(figsize=(10, 5))
    if not yearly.empty:
        colors = ["#2ca02c" if v >= 0 else "#d62728" for v in yearly["total_pnl"]]
        ax.bar(yearly["year"].astype(str), yearly["total_pnl"], color=colors, alpha=0.8)
        ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(f"Wynik rok po roku — {PROXY_NOTE}")
    ax.set_xlabel("Rok")
    ax.set_ylabel("P&L (USD)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(p, dpi=110)
    plt.close(fig)
    return p
