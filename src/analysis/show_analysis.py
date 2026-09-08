"""Podgląd analiz pogłębionych (rok po roku, krachy, tail risk) — PROXY.

    python -m src.analysis.show_analysis --config configs/base.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.analysis.breakdown import period_breakdown, tail_stats, yearly_breakdown
from src.strategy.pricing import price_all_spreads
from src.strategy.settlement import settle_all_spreads
from src.strategy.spread_selection import build_all_spreads


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def _load_instrument(cfg: dict) -> dict:
    return yaml.safe_load(Path(cfg["instrument"]["spec_file"]).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Podgląd analiz (PROXY).")
    parser.add_argument("--config", default="configs/base.yaml")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    data_cfg = cfg["data"]
    strat = cfg["strategy"]
    pricing_cfg = cfg["pricing"]
    exit_cfg = cfg["exit"]
    instrument = _load_instrument(cfg)

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

    print("*** ANALIZY PROXY — kredyt z modelu (BS+VIX), NIE fakty rynkowe ***")
    if results.empty:
        print("Brak rozliczonych transakcji.")
        return

    yearly = yearly_breakdown(results)
    yb = yearly.copy()
    yb["win_rate"] = (yb["win_rate"] * 100).round(1)
    yb["total_pnl"] = yb["total_pnl"].round(0)
    yb["avg_pnl"] = yb["avg_pnl"].round(0)
    yb["best"] = yb["best"].round(0)
    yb["worst"] = yb["worst"].round(0)
    with pd.option_context("display.max_columns", None, "display.width", 140):
        print("\n== Rok po roku ==")
        print(yb.to_string(index=False))

    stress = period_breakdown(results)
    sb = stress.copy()
    sb["win_rate"] = (sb["win_rate"] * 100).round(1)
    sb["total_pnl"] = sb["total_pnl"].round(0)
    sb["avg_pnl"] = sb["avg_pnl"].round(0)
    sb["best"] = sb["best"].round(0)
    sb["worst"] = sb["worst"].round(0)
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print("\n== Okresy stresowe (krachy) ==")
        print(sb[["period", "n_trades", "win_rate", "total_pnl", "avg_pnl", "worst"]].to_string(index=False))

    tail = tail_stats(results, n_worst=10)
    print("\n== Tail risk (rozkład P&L, USD) ==")
    print(f"  Mediana (p50):   {tail['p50']:,.0f}")
    print(f"  5. percentyl:    {tail['p5']:,.0f}")
    print(f"  1. percentyl:    {tail['p1']:,.0f}")
    print(f"  VaR 5%:          {tail['var']:,.0f}   (5% najgorszych transakcji jest poniżej)")
    print(f"  CVaR 5% (ES):    {tail['cvar']:,.0f}   (średnia w tych 5% najgorszych)")

    wt = tail["worst_trades"].copy()
    if "entry_date" in wt.columns:
        wt["entry_date"] = pd.to_datetime(wt["entry_date"]).dt.date
    if "expiration_date" in wt.columns:
        wt["expiration_date"] = pd.to_datetime(wt["expiration_date"]).dt.date
    for c in ("settle_price", "pnl_cash"):
        if c in wt.columns:
            wt[c] = wt[c].round(2 if c == "settle_price" else 0)
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print("\n== 10 najgorszych transakcji ==")
        print(wt.to_string(index=False))


if __name__ == "__main__":
    main()
