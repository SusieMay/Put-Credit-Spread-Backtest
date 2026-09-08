"""Podgląd zrealizowanych wyników (P&L na wygaśnięciu) — PROXY.

UWAGA: wyniki opierają się na wycenie PROXY kredytu (Black-Scholes + VIX), a nie na
prawdziwych cenach opcji. Cena rozliczenia to realne zamknięcie SPX w dniu
wygaśnięcia. Traktuj wyniki jako przybliżenie.

    python -m src.strategy.show_results --config configs/base.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.strategy.pricing import price_all_spreads
from src.strategy.settlement import settle_all_spreads
from src.strategy.spread_selection import build_all_spreads


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def _load_instrument(cfg: dict) -> dict:
    return yaml.safe_load(Path(cfg["instrument"]["spec_file"]).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Podgląd wyników P&L (PROXY).")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--rows", type=int, default=8)
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
        spx,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
        wing_width=wing_width,
        strike_increment=strike_increment,
    )
    priced = price_all_spreads(
        plans, spx, vix,
        spot_basis=pricing_cfg["spot_basis"],
        vol_basis=pricing_cfg["vol_basis"],
        r=float(pricing_cfg["risk_free_rate"]),
        skew_slope=float(pricing_cfg["skew_slope"]),
        multiplier=multiplier,
        day_count=int(pricing_cfg["day_count"]),
    )
    results = settle_all_spreads(
        priced, spx,
        settle_basis=exit_cfg["settle_price_basis"],
        multiplier=multiplier,
    )

    print("*** WYNIKI PROXY — kredyt z modelu (BS+VIX), rozliczenie po realnym zamknięciu SPX ***")
    print(f"Rozliczonych spreadów: {len(results)}")
    if results.empty:
        return

    n = len(results)
    wins = int(results["is_win"].sum())
    total = results["pnl_cash"].sum()
    avg = results["pnl_cash"].mean()
    win_rate = wins / n * 100
    counts = results["outcome"].value_counts().to_dict()

    print(f"Win rate:        {win_rate:.1f}%  ({wins}/{n})")
    print(f"Suma P&L (PROXY): {total:,.0f} USD")
    print(f"Średni P&L/tydz.: {avg:,.0f} USD")
    print(
        f"Rozkład wyników: max_profit={counts.get('max_profit', 0)}, "
        f"partial_loss={counts.get('partial_loss', 0)}, max_loss={counts.get('max_loss', 0)}"
    )

    cols = [
        "entry_date", "expiration_date", "short_strike", "long_strike",
        "credit_cash", "settle_price", "pnl_cash", "outcome",
    ]
    tail = results[cols].tail(args.rows).copy()
    tail["entry_date"] = tail["entry_date"].dt.date
    tail["expiration_date"] = tail["expiration_date"].dt.date
    tail["credit_cash"] = tail["credit_cash"].round(0)
    tail["pnl_cash"] = tail["pnl_cash"].round(0)
    tail["settle_price"] = tail["settle_price"].round(2)
    with pd.option_context("display.max_columns", None, "display.width", 140):
        print("\nOstatnie wyniki:")
        print(tail.to_string(index=False))


if __name__ == "__main__":
    main()
