"""Podgląd zaplanowanych spreadów na realnych danych.

Uruchamianie (po pobraniu danych):

    python -m src.strategy.show_spreads --config configs/base.yaml

Pokazuje kilka ostatnich zaplanowanych put credit spreadów oraz plan na najbliższe
wejście (poniedziałek po ostatniej dacie w danych).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.strategy.spread_selection import (
    build_all_spreads,
    build_spread_plan,
    trading_days,
)


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def _load_instrument(cfg: dict) -> dict:
    spec_file = cfg["instrument"]["spec_file"]
    return yaml.safe_load(Path(spec_file).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Podgląd zaplanowanych spreadów.")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--rows", type=int, default=8, help="Ile ostatnich tygodni pokazać.")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    data_cfg = cfg["data"]
    strat = cfg["strategy"]
    instrument = _load_instrument(cfg)

    atr_period = int(strat["saty_atr_definition"]["atr_period"])
    atr_multiplier = float(strat["atr_multiplier"])
    wing_width = float(strat["wing_width"])
    strike_increment = float(instrument["strike_increment"])

    name = _safe_name(data_cfg["underlying_symbol"])
    parquet = Path(data_cfg["processed_dir"]) / f"{name}.parquet"
    if not parquet.exists():
        raise SystemExit(
            f"Brak pliku {parquet}. Najpierw pobierz dane: "
            f"python -m src.data.download --config {args.config}"
        )

    daily = pd.read_parquet(parquet)

    print(
        f"Underlying: {data_cfg['underlying_symbol']}  |  ATR: {atr_period}  |  "
        f"mult: {atr_multiplier}  |  wing: {wing_width}  |  strike grid: {strike_increment}"
    )
    print(f"Zakres danych: {daily['date'].min().date()} -> {daily['date'].max().date()}")

    plans = build_all_spreads(
        daily,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
        wing_width=wing_width,
        strike_increment=strike_increment,
    )
    print(f"\nZaplanowano spreadów (tygodni): {len(plans)}")
    print(f"\nOstatnie {args.rows} spreadów:")
    cols = [
        "entry_date", "expiration_date", "dte",
        "raw_level", "short_strike", "long_strike",
    ]
    tail = plans[cols].tail(args.rows).copy()
    tail["entry_date"] = tail["entry_date"].dt.date
    tail["expiration_date"] = tail["expiration_date"].dt.date
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(tail.to_string(index=False))

    # Plan na najbliższe wejście (poniedziałek po ostatniej dacie).
    last_date = pd.Timestamp(daily["date"].max())
    days_to_mon = (7 - last_date.weekday()) % 7
    next_monday = (last_date + pd.Timedelta(days=days_to_mon or 7)).normalize()
    days_index = trading_days(daily)
    plan = build_spread_plan(
        daily,
        next_monday,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
        wing_width=wing_width,
        strike_increment=strike_increment,
        days_index=days_index,
        calendar_fallback=True,
    )
    print("\n--- Plan na najbliższe wejście ---")
    if plan is None:
        print("Za mało danych lub brak dnia wygaśnięcia w danych.")
    else:
        print(f"Data wejścia:        {plan.entry_date.date()}")
        print(f"Wygaśnięcie (SPXW):  {plan.expiration_date.date()}  (DTE={plan.dte})")
        print(f"Poziom Saty ATR -1:  {plan.raw_level:.2f}")
        print(f"SHORT put strike:    {plan.short_strike:.0f}")
        print(f"LONG  put strike:    {plan.long_strike:.0f}  (szerokość {plan.wing_width:.0f} pkt)")


if __name__ == "__main__":
    main()
