"""Podgląd poziomu Saty ATR -1 na realnych danych.

Uruchamianie (po pobraniu danych przez src.data.download):

    python -m src.indicators.show_level --config configs/base.yaml

Domyślnie pokazuje poziom dla NAJBLIŻSZEGO poniedziałku po ostatniej dostępnej
dacie oraz kilka ostatnich historycznych poziomów tygodniowych.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.indicators.atr import saty_atr_level, weekly_atr_table


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Podgląd poziomu Saty ATR -1.")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--weeks", type=int, default=8, help="Ile ostatnich tygodni pokazać.")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    data_cfg = cfg["data"]
    strat = cfg["strategy"]

    atr_period = int(strat["saty_atr_definition"]["atr_period"])
    atr_multiplier = float(strat["atr_multiplier"])

    name = _safe_name(data_cfg["underlying_symbol"])
    parquet = Path(data_cfg["processed_dir"]) / f"{name}.parquet"
    if not parquet.exists():
        raise SystemExit(
            f"Brak pliku {parquet}. Najpierw pobierz dane: "
            f"python -m src.data.download --config {args.config}"
        )

    daily = pd.read_parquet(parquet)
    table = weekly_atr_table(daily, atr_period=atr_period)

    print(f"Underlying: {data_cfg['underlying_symbol']}  |  ATR period: {atr_period}  |  multiplier: {atr_multiplier}")
    print(f"Zakres danych: {daily['date'].min().date()} -> {daily['date'].max().date()}")
    print(f"\nOstatnie {args.weeks} tygodni (week_end, close, atr):")
    tail = table.dropna(subset=["atr"]).tail(args.weeks)
    for _, r in tail.iterrows():
        lvl = float(r["close"]) + atr_multiplier * float(r["atr"])
        print(
            f"  {pd.Timestamp(r['week_end']).date()}  close={r['close']:.2f}  "
            f"atr={r['atr']:.2f}  ->  poziom dla kolejnego tygodnia = {lvl:.2f}"
        )

    # Poziom dla najbliższego poniedziałku po ostatniej dacie.
    last_date = pd.Timestamp(daily["date"].max())
    days_to_mon = (7 - last_date.weekday()) % 7
    next_monday = (last_date + pd.Timedelta(days=days_to_mon or 7)).normalize()
    res = saty_atr_level(
        daily, next_monday, atr_period=atr_period, atr_multiplier=atr_multiplier
    )
    print("\n--- Poziom dla najbliższego wejścia ---")
    if res is None:
        print("Za mało danych do wyliczenia poziomu.")
    else:
        print(f"Data wejścia (poniedziałek): {res.entry_date.date()}")
        print(f"Referencyjny koniec tygodnia: {res.ref_week_end.date()}")
        print(f"Poprzednie zamknięcie tyg.:   {res.prev_close:.2f}")
        print(f"Tygodniowy ATR({atr_period}):        {res.atr:.2f}")
        print(f"SHORT STRIKE (Saty ATR {atr_multiplier:+.2f}): {res.level:.2f}")


if __name__ == "__main__":
    main()
