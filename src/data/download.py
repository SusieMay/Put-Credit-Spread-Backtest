"""CLI pobierania darmowych danych rynkowych (SPX + VIX) ze Stooq.

Uruchamianie z katalogu głównego projektu:

    python -m src.data.download --config configs/base.yaml

Zapisuje:
    data/raw/<symbol>.csv           (surowy CSV ze Stooq)
    data/processed/<symbol>.parquet (znormalizowany, przefiltrowany po dacie)
i wypisuje raport jakości dla każdego symbolu.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from src.data.loaders import (
    DataDownloadError,
    filter_date_range,
    load_provider_daily,
    save_processed_parquet,
)
from src.data.quality import data_quality_report, has_errors


def _safe_name(symbol: str) -> str:
    """Zamienia symbol na bezpieczną nazwę pliku (np. '^GSPC' -> 'gspc')."""
    return symbol.lstrip("^").replace("/", "_").lower()


def fetch_symbol(
    provider: str,
    symbol: str,
    interval: str,
    raw_dir: str,
    processed_dir: str,
    start_date: str | None,
    end_date: str | None,
) -> None:
    """Pobiera jeden symbol, zapisuje pliki i wypisuje raport jakości."""
    name = _safe_name(symbol)
    print(f"\n=== {symbol} (provider={provider}) ===")

    df = load_provider_daily(provider, symbol, interval=interval)

    # Surowe (pełny zakres) do data/raw jako CSV.
    raw_path = Path(raw_dir) / f"{name}.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(raw_path, index=False)
    print(f"raw CSV      -> {raw_path}  ({len(df)} wierszy, pełny zakres)")

    # Przefiltrowane po dacie do data/processed jako Parquet.
    df_f = filter_date_range(df, start_date=start_date, end_date=end_date)
    proc_path = save_processed_parquet(df_f, Path(processed_dir) / f"{name}.parquet")
    print(f"processed    -> {proc_path}  ({len(df_f)} wierszy po filtrze dat)")

    report = data_quality_report(df_f)
    print("data quality:")
    print(report.to_string(index=False))
    if has_errors(report):
        print(f"!! UWAGA: raport jakości dla '{symbol}' zawiera błędy (severity=error).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pobierz darmowe dane SPX/VIX (Yahoo/Stooq).")
    parser.add_argument("--config", default="configs/base.yaml", help="Ścieżka do config YAML.")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    data_cfg = cfg["data"]

    provider = data_cfg.get("provider", "yahoo")
    symbols = [data_cfg["underlying_symbol"], data_cfg["vix_symbol"]]
    try:
        for symbol in symbols:
            fetch_symbol(
                provider=provider,
                symbol=symbol,
                interval=data_cfg.get("interval", "d"),
                raw_dir=data_cfg["raw_dir"],
                processed_dir=data_cfg["processed_dir"],
                start_date=data_cfg.get("start_date"),
                end_date=data_cfg.get("end_date"),
            )
    except DataDownloadError as exc:
        raise SystemExit(f"Błąd pobierania danych: {exc}")

    print("\nGotowe.")


if __name__ == "__main__":
    main()
