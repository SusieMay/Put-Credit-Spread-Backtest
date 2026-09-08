"""Uruchamia pełny backtest i zapisuje raport końcowy, CSV oraz wykresy.

    python -m src.backtest.run --config configs/base.yaml

Zapisuje do folderu results/:
- report.md          – zbiorczy raport (metryki, analizy, odnośniki do wykresów),
- trades.csv         – wszystkie zrealizowane transakcje,
- equity_curve.csv   – krzywa kapitału,
oraz wykresy PNG do charts/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.analysis.breakdown import period_breakdown, tail_stats, yearly_breakdown
from src.backtest.pipeline import load_config_and_data, params_from_config, run_pipeline
from src.backtest.report import render_report
from src.metrics.performance import compute_metrics
from src.viz.plots import (
    plot_drawdown,
    plot_equity_curve,
    plot_pnl_histogram,
    plot_yearly_pnl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pełny backtest + raport końcowy.")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--charts-dir", default="charts")
    parser.add_argument("--no-charts", action="store_true", help="Pomiń generowanie wykresów.")
    args = parser.parse_args()

    cfg, instrument, spx, vix = load_config_and_data(args.config)
    params = params_from_config(cfg, instrument)

    art = run_pipeline(spx, vix, params)
    if art.results.empty:
        raise SystemExit("Brak rozliczonych transakcji — sprawdź dane wejściowe.")

    metrics = compute_metrics(art.results, art.curve, params.portfolio.initial_capital)
    yearly = yearly_breakdown(art.results)
    stress = period_breakdown(art.results)
    tail = tail_stats(art.results, n_worst=10)

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    # CSV z transakcjami i krzywą kapitału.
    art.results.to_csv(results_dir / "trades.csv", index=False)
    art.curve.to_csv(results_dir / "equity_curve.csv", index=False)

    # Wykresy.
    chart_files: list[str] = []
    if not args.no_charts:
        charts_dir = Path(args.charts_dir)
        plot_equity_curve(art.curve, charts_dir / "equity_curve.png")
        plot_drawdown(art.curve, charts_dir / "drawdown.png")
        plot_pnl_histogram(art.results, charts_dir / "pnl_histogram.png")
        plot_yearly_pnl(yearly, charts_dir / "yearly_pnl.png")
        chart_files = [
            str(charts_dir / "equity_curve.png"),
            str(charts_dir / "drawdown.png"),
            str(charts_dir / "pnl_histogram.png"),
            str(charts_dir / "yearly_pnl.png"),
        ]

    params_summary = {
        "Underlying": cfg["data"]["underlying_symbol"],
        "Sygnał": f"Saty ATR {params.atr_multiplier:+.1f} (okres {params.atr_period}, tygodniowy)",
        "Szerokość skrzydła": f"{params.wing_width:.0f} pkt",
        "Siatka strike'ów": f"{params.strike_increment:.0f} pkt",
        "Wycena": "PROXY: Black-Scholes + VIX + skew",
        "Rozliczenie": "gotówkowe, cena zamknięcia w dniu wygaśnięcia",
        "Sizing": f"{params.portfolio.sizing} (kontrakty: {params.portfolio.contracts})",
    }

    report = render_report(
        config_name=Path(args.config).name,
        params_summary=params_summary,
        metrics=metrics,
        yearly=yearly,
        stress=stress,
        tail=tail,
        chart_files=chart_files or None,
    )
    report_path = results_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")

    print("*** BACKTEST ZAKOŃCZONY (PROXY) ***")
    print(f"  Raport:        {report_path}")
    print(f"  Transakcje:    {results_dir / 'trades.csv'}")
    print(f"  Krzywa kap.:   {results_dir / 'equity_curve.csv'}")
    if chart_files:
        print(f"  Wykresy:       {args.charts_dir}/ (4 pliki PNG)")
    print(
        f"\nPodsumowanie: {metrics['n_trades']} transakcji, "
        f"CAGR {metrics['cagr'] * 100:.1f}%, "
        f"maks. drawdown {metrics['max_drawdown_pct'] * 100:.1f}%, "
        f"win rate {metrics['win_rate'] * 100:.1f}%."
    )


if __name__ == "__main__":
    main()
