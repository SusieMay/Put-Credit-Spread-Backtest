"""Podgląd metryk wydajności strategii (PROXY).

UWAGA: metryki bazują na wycenie PROXY kredytu (Black-Scholes + VIX). To
przybliżenie, nie fakty rynkowe.

    python -m src.metrics.show_metrics --config configs/base.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.metrics.performance import compute_metrics
from src.portfolio.engine import build_equity_curve, portfolio_config_from_dict
from src.strategy.pricing import price_all_spreads
from src.strategy.settlement import settle_all_spreads
from src.strategy.spread_selection import build_all_spreads


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def _load_instrument(cfg: dict) -> dict:
    return yaml.safe_load(Path(cfg["instrument"]["spec_file"]).read_text(encoding="utf-8"))


def _fmt(x: float, kind: str = "num") -> str:
    if x != x:  # NaN
        return "—"
    if x in (float("inf"), float("-inf")):
        return "∞"
    if kind == "pct":
        return f"{x * 100:.1f}%"
    if kind == "usd":
        return f"{x:,.0f} USD"
    return f"{x:.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Podgląd metryk (PROXY).")
    parser.add_argument("--config", default="configs/base.yaml")
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
    m = compute_metrics(results, curve, port_cfg.initial_capital)

    print("*** METRYKI PROXY — kredyt z modelu (BS+VIX), NIE fakty rynkowe ***")
    print(f"Okres: {m['years']:.1f} lat  |  transakcji: {m['n_trades']}")
    print("\n== Wyniki ==")
    print(f"  Kapitał końcowy:   {_fmt(m['final_equity'], 'usd')}")
    print(f"  Zwrot całkowity:   {_fmt(m['total_return'], 'pct')}")
    print(f"  CAGR:              {_fmt(m['cagr'], 'pct')}")
    print("\n== Ryzyko ==")
    print(f"  Maks. drawdown:    {_fmt(m['max_drawdown'], 'usd')}  ({_fmt(m['max_drawdown_pct'], 'pct')})")
    print(f"  Sharpe (annual.):  {_fmt(m['sharpe'])}")
    print(f"  Sortino (annual.): {_fmt(m['sortino'])}")
    print(f"  Calmar:            {_fmt(m['calmar'])}")
    print("\n== Statystyka transakcji ==")
    print(f"  Win rate:          {_fmt(m['win_rate'], 'pct')}  ({m['n_wins']}/{m['n_trades']})")
    print(f"  Profit factor:     {_fmt(m['profit_factor'])}")
    print(f"  Expectancy/tr.:    {_fmt(m['expectancy'], 'usd')}")
    print(f"  Śr. wygrana:       {_fmt(m['avg_win'], 'usd')}")
    print(f"  Śr. przegrana:     {_fmt(m['avg_loss'], 'usd')}")
    print(f"  Payoff ratio:      {_fmt(m['payoff_ratio'])}")


if __name__ == "__main__":
    main()
