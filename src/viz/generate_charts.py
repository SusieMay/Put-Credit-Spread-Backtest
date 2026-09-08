"""Generuje komplet wykresów backtestu i zapisuje do folderu charts/ (PROXY).

    python -m src.viz.generate_charts --config configs/base.yaml

Zapisuje: equity_curve.png, drawdown.png, pnl_histogram.png, yearly_pnl.png.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.analysis.breakdown import yearly_breakdown
from src.portfolio.engine import build_equity_curve, portfolio_config_from_dict
from src.strategy.pricing import price_all_spreads
from src.strategy.settlement import settle_all_spreads
from src.strategy.spread_selection import build_all_spreads
from src.viz.plots import (
    plot_drawdown,
    plot_equity_curve,
    plot_pnl_histogram,
    plot_yearly_pnl,
)


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def _load_instrument(cfg: dict) -> dict:
    return yaml.safe_load(Path(cfg["instrument"]["spec_file"]).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generowanie wykresów (PROXY).")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--out-dir", default="charts")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    data_cfg = cfg["data"]
    strat = cfg["strategy"]
    pricing_cfg = cfg["pricing"]
    exit_cfg = cfg["exit"]
    instrument = _load_instrument(cfg)
    port_cfg = portfolio_config_from_dict(cfg["portfolio"])

    atr_period = int(strat["saty_atr_definition"]["atr_period"])
    atr_multiplier = float(strat["atr_multiplier"])
    wing_width = float(strat["wing_width"])
    strike_increment = float(instrument["strike_increment"])
    multiplier = float(instrument["multiplier"])

    processed = Path(data_cfg["processed_dir"])
    spx_path = processed / f"{_safe_name(data_cfg['underlying_symbol'])}.parquet"
    vix_path = processed / f"{_safe_name(data_cfg['vix_symbol'])}.parquet"
    for p in (spx_path, vix_path):
        if not p.exists():
            raise SystemExit(
                f"Brak pliku {p}. Najpierw pobierz dane: "
                f"python -m src.data.download --config {args.config}"
            )

    spx = pd.read_parquet(spx_path)
    vix = pd.read_parquet(vix_path)

    plans = build_all_spreads(
        spx, atr_period=atr_period, atr_multiplier=atr_multiplier,
        wing_width=wing_width, strike_increment=strike_increment,
    )
    priced = price_all_spreads(
        plans, spx, vix,
        spot_basis=pricing_cfg["spot_basis"], vol_basis=pricing_cfg["vol_basis"],
        r=float(pricing_cfg["risk_free_rate"]), skew_slope=float(pricing_cfg["skew_slope"]),
        multiplier=multiplier, day_count=int(pricing_cfg["day_count"]),
    )
    results = settle_all_spreads(
        priced, spx, settle_basis=exit_cfg["settle_price_basis"], multiplier=multiplier,
    )
    curve = build_equity_curve(results, port_cfg)
    yearly = yearly_breakdown(results)

    out_dir = Path(args.out_dir)
    paths = [
        plot_equity_curve(curve, out_dir / "equity_curve.png"),
        plot_drawdown(curve, out_dir / "drawdown.png"),
        plot_pnl_histogram(results, out_dir / "pnl_histogram.png"),
        plot_yearly_pnl(yearly, out_dir / "yearly_pnl.png"),
    ]

    print("*** WYKRESY PROXY zapisane (kredyt z modelu BS+VIX) ***")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
