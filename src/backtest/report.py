"""Generowanie raportu końcowego backtestu (Markdown) z metryk i analiz.

Funkcja ``render_report`` jest czysta (przyjmuje słowniki/DataFrame, zwraca tekst),
dzięki czemu łatwo ją testować bez zapisu na dysk.
"""

from __future__ import annotations

import pandas as pd


def _fmt(x: float, kind: str = "num") -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    if x in (float("inf"), float("-inf")):
        return "∞"
    if kind == "pct":
        return f"{x * 100:.1f}%"
    if kind == "usd":
        return f"{x:,.0f} USD"
    return f"{x:.2f}"


def render_report(
    *,
    config_name: str,
    params_summary: dict,
    metrics: dict,
    yearly: pd.DataFrame,
    stress: pd.DataFrame,
    tail: dict,
    chart_files: list[str] | None = None,
) -> str:
    """Buduje treść raportu w Markdown."""
    lines: list[str] = []
    lines.append("# Raport backtestu — Put Credit Spread (Saty ATR -1)")
    lines.append("")
    lines.append("> **UWAGA:** kredyt (premia) jest szacowany modelem PROXY "
                 "(Black-Scholes + VIX + skew), a **nie** pochodzi z prawdziwych "
                 "historycznych cen opcji SPX. Wyniki traktuj jako przybliżenie, nie fakt rynkowy.")
    lines.append("")

    lines.append("## Parametry")
    lines.append("")
    lines.append("| Parametr | Wartość |")
    lines.append("|---|---|")
    lines.append(f"| Konfiguracja | {config_name} |")
    for k, v in params_summary.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## Wyniki zbiorcze")
    lines.append("")
    lines.append("| Metryka | Wartość |")
    lines.append("|---|---|")
    lines.append(f"| Okres | {_fmt(metrics.get('years', 0))} lat |")
    lines.append(f"| Liczba transakcji | {metrics.get('n_trades', 0)} |")
    lines.append(f"| Kapitał początkowy | {_fmt(metrics.get('initial_capital', 0), 'usd')} |")
    lines.append(f"| Kapitał końcowy | {_fmt(metrics.get('final_equity', 0), 'usd')} |")
    lines.append(f"| Zwrot całkowity | {_fmt(metrics.get('total_return', 0), 'pct')} |")
    lines.append(f"| CAGR | {_fmt(metrics.get('cagr', 0), 'pct')} |")
    lines.append(f"| Maks. drawdown | {_fmt(metrics.get('max_drawdown', 0), 'usd')} ({_fmt(metrics.get('max_drawdown_pct', 0), 'pct')}) |")
    lines.append(f"| Sharpe (annual.) | {_fmt(metrics.get('sharpe'))} |")
    lines.append(f"| Sortino (annual.) | {_fmt(metrics.get('sortino'))} |")
    lines.append(f"| Calmar | {_fmt(metrics.get('calmar'))} |")
    lines.append(f"| Win rate | {_fmt(metrics.get('win_rate', 0), 'pct')} |")
    lines.append(f"| Profit factor | {_fmt(metrics.get('profit_factor'))} |")
    lines.append(f"| Expectancy / transakcję | {_fmt(metrics.get('expectancy', 0), 'usd')} |")
    lines.append(f"| Śr. wygrana / przegrana | {_fmt(metrics.get('avg_win', 0), 'usd')} / {_fmt(metrics.get('avg_loss', 0), 'usd')} |")
    lines.append("")

    lines.append("## Rok po roku")
    lines.append("")
    if yearly.empty:
        lines.append("_Brak danych._")
    else:
        lines.append("| Rok | Transakcje | Win rate | P&L | Najgorsza |")
        lines.append("|---|---|---|---|---|")
        for _, r in yearly.iterrows():
            lines.append(
                f"| {int(r['year'])} | {int(r['n_trades'])} | "
                f"{_fmt(r['win_rate'], 'pct')} | {_fmt(r['total_pnl'], 'usd')} | "
                f"{_fmt(r['worst'], 'usd')} |"
            )
    lines.append("")

    lines.append("## Okresy stresowe (krachy)")
    lines.append("")
    if stress.empty:
        lines.append("_Brak danych._")
    else:
        lines.append("| Okres | Transakcje | Win rate | P&L | Najgorsza |")
        lines.append("|---|---|---|---|---|")
        for _, r in stress.iterrows():
            lines.append(
                f"| {r['period']} | {int(r['n_trades'])} | "
                f"{_fmt(r['win_rate'], 'pct')} | {_fmt(r['total_pnl'], 'usd')} | "
                f"{_fmt(r['worst'], 'usd')} |"
            )
    lines.append("")

    lines.append("## Tail risk (rozkład P&L)")
    lines.append("")
    lines.append("| Miara | Wartość |")
    lines.append("|---|---|")
    lines.append(f"| Mediana (p50) | {_fmt(tail.get('p50', 0), 'usd')} |")
    lines.append(f"| 5. percentyl | {_fmt(tail.get('p5', 0), 'usd')} |")
    lines.append(f"| 1. percentyl | {_fmt(tail.get('p1', 0), 'usd')} |")
    lines.append(f"| VaR 5% | {_fmt(tail.get('var', 0), 'usd')} |")
    lines.append(f"| CVaR 5% (Expected Shortfall) | {_fmt(tail.get('cvar', 0), 'usd')} |")
    lines.append("")

    if chart_files:
        lines.append("## Wykresy")
        lines.append("")
        for cf in chart_files:
            lines.append(f"- `{cf}`")
        lines.append("")

    return "\n".join(lines)
