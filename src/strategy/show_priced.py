"""Podgląd wyceny PROXY spreadów na realnych danych (kredyt/premia).

UWAGA: kredyt jest szacowany modelem Black-Scholes + VIX (PROXY), NIE są to
prawdziwe historyczne ceny opcji SPX. Patrz DATA_SOURCE_REPORT.md.

Uruchamianie (po pobraniu danych SPX i VIX):

    python -m src.strategy.show_priced --config configs/base.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.strategy.pricing import price_all_spreads
from src.strategy.spread_selection import build_all_spreads


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def _load_instrument(cfg: dict) -> dict:
    spec_file = cfg["instrument"]["spec_file"]
    return yaml.safe_load(Path(spec_file).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Podgląd wyceny PROXY spreadów.")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--rows", type=int, default=8)
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    data_cfg = cfg["data"]
    strat = cfg["strategy"]
    pricing_cfg = cfg["pricing"]
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
        spx,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
        wing_width=wing_width,
        strike_increment=strike_increment,
    )
    priced = price_all_spreads(
        plans,
        spx,
        vix,
        spot_basis=pricing_cfg["spot_basis"],
        vol_basis=pricing_cfg["vol_basis"],
        r=float(pricing_cfg["risk_free_rate"]),
        skew_slope=float(pricing_cfg["skew_slope"]),
        multiplier=multiplier,
        day_count=int(pricing_cfg["day_count"]),
    )

    print("*** WYCENA PROXY (Black-Scholes + VIX) — to MODEL, nie realne ceny opcji ***")
    print(
        f"Underlying: {data_cfg['underlying_symbol']}  |  wing: {wing_width}  |  "
        f"r: {pricing_cfg['risk_free_rate']}  |  skew_slope: {pricing_cfg['skew_slope']}"
    )
    print(f"Wycenionych spreadów: {len(priced)}")

    if priced.empty:
        return

    avg_credit = priced["credit_cash"].mean()
    avg_maxloss = priced["max_loss_cash"].mean()
    print(
        f"Średni kredyt (PROXY): {avg_credit:,.0f} USD  |  "
        f"średnia maks. strata: {avg_maxloss:,.0f} USD"
    )

    cols = [
        "entry_date", "expiration_date", "spot", "base_vol",
        "short_strike", "long_strike", "credit_points", "credit_cash", "max_loss_cash",
    ]
    tail = priced[cols].tail(args.rows).copy()
    tail["entry_date"] = tail["entry_date"].dt.date
    tail["expiration_date"] = tail["expiration_date"].dt.date
    tail["base_vol"] = (tail["base_vol"] * 100).round(1)  # pokaż jako VIX%
    tail["credit_points"] = tail["credit_points"].round(2)
    tail["credit_cash"] = tail["credit_cash"].round(0)
    tail["max_loss_cash"] = tail["max_loss_cash"].round(0)
    tail = tail.rename(columns={"base_vol": "vix%"})
    with pd.option_context("display.max_columns", None, "display.width", 140):
        print("\nOstatnie spready (PROXY):")
        print(tail.to_string(index=False))


if __name__ == "__main__":
    main()
