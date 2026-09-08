"""Podgląd krzywej kapitału i obsunięć (PROXY).

UWAGA: opiera się na wycenie PROXY kredytu (Black-Scholes + VIX). Wyniki to
przybliżenie, nie fakty rynkowe.

    python -m src.portfolio.show_portfolio --config configs/base.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.portfolio.engine import build_equity_curve, portfolio_config_from_dict
from src.strategy.pricing import price_all_spreads
from src.strategy.settlement import settle_all_spreads
from src.strategy.spread_selection import build_all_spreads


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def _load_instrument(cfg: dict) -> dict:
    return yaml.safe_load(Path(cfg["instrument"]["spec_file"]).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Podgląd portfela (PROXY).")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--rows", type=int, default=8)
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

    print("*** PORTFEL PROXY — kredyt z modelu (BS+VIX) ***")
    print(
        f"Kapitał początkowy: {port_cfg.initial_capital:,.0f} USD  |  "
        f"sizing: {port_cfg.sizing}  |  kontrakty: {port_cfg.contracts}"
    )
    if curve.empty:
        print("Brak transakcji w portfelu.")
        return

    final_equity = curve["equity"].iloc[-1]
    total_pnl = final_equity - port_cfg.initial_capital
    ret_pct = total_pnl / port_cfg.initial_capital * 100
    max_dd = curve["drawdown"].min()
    max_dd_pct = curve["drawdown_pct"].min() * 100

    print(f"Transakcji:         {len(curve)}")
    print(f"Kapitał końcowy:    {final_equity:,.0f} USD")
    print(f"Wynik całkowity:    {total_pnl:,.0f} USD  ({ret_pct:+.1f}%)")
    print(f"Maks. obsunięcie:   {max_dd:,.0f} USD  ({max_dd_pct:.1f}%)")

    cols = ["entry_date", "contracts", "trade_pnl", "equity", "drawdown", "drawdown_pct"]
    tail = curve[cols].tail(args.rows).copy()
    tail["entry_date"] = tail["entry_date"].dt.date
    tail["trade_pnl"] = tail["trade_pnl"].round(0)
    tail["equity"] = tail["equity"].round(0)
    tail["drawdown"] = tail["drawdown"].round(0)
    tail["drawdown_pct"] = (tail["drawdown_pct"] * 100).round(1)
    tail = tail.rename(columns={"drawdown_pct": "dd%"})
    with pd.option_context("display.max_columns", None, "display.width", 140):
        print("\nOstatnie transakcje portfela:")
        print(tail.to_string(index=False))


if __name__ == "__main__":
    main()
