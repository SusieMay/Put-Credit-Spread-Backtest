"""Pełny pipeline backtestu: od danych do zrealizowanych wyników i portfela.

Spina wszystkie warstwy w jedną funkcję:
    dane -> sygnał (Saty ATR -1) -> spread -> wycena PROXY -> rozliczenie ->
    portfel (krzywa kapitału).

Logika operuje na DataFrame'ach (SPX i VIX), więc jest łatwa do testów bez plików.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from src.portfolio.engine import PortfolioConfig, build_equity_curve, portfolio_config_from_dict
from src.strategy.pricing import price_all_spreads
from src.strategy.settlement import settle_all_spreads
from src.strategy.spread_selection import build_all_spreads


@dataclass(frozen=True)
class BacktestParams:
    atr_period: int = 14
    atr_multiplier: float = -1.0
    wing_width: float = 50.0
    strike_increment: float = 5.0
    multiplier: float = 100.0
    spot_basis: str = "open"
    vol_basis: str = "open"
    risk_free_rate: float = 0.03
    skew_slope: float = 0.8
    day_count: int = 365
    settle_price_basis: str = "close"
    portfolio: PortfolioConfig = PortfolioConfig()


@dataclass(frozen=True)
class BacktestArtifacts:
    plans: pd.DataFrame
    priced: pd.DataFrame
    results: pd.DataFrame
    curve: pd.DataFrame


def run_pipeline(spx: pd.DataFrame, vix: pd.DataFrame, params: BacktestParams) -> BacktestArtifacts:
    """Uruchamia cały pipeline na danych SPX i VIX, zwraca komplet artefaktów."""
    plans = build_all_spreads(
        spx,
        atr_period=params.atr_period,
        atr_multiplier=params.atr_multiplier,
        wing_width=params.wing_width,
        strike_increment=params.strike_increment,
    )
    priced = price_all_spreads(
        plans, spx, vix,
        spot_basis=params.spot_basis,
        vol_basis=params.vol_basis,
        r=params.risk_free_rate,
        skew_slope=params.skew_slope,
        multiplier=params.multiplier,
        day_count=params.day_count,
    )
    results = settle_all_spreads(
        priced, spx,
        settle_basis=params.settle_price_basis,
        multiplier=params.multiplier,
    )
    curve = build_equity_curve(results, params.portfolio)
    return BacktestArtifacts(plans=plans, priced=priced, results=results, curve=curve)


def params_from_config(cfg: dict, instrument: dict) -> BacktestParams:
    """Buduje ``BacktestParams`` z wczytanego configu i specyfikacji instrumentu."""
    strat = cfg["strategy"]
    pricing = cfg["pricing"]
    return BacktestParams(
        atr_period=int(strat["saty_atr_definition"]["atr_period"]),
        atr_multiplier=float(strat["atr_multiplier"]),
        wing_width=float(strat["wing_width"]),
        strike_increment=float(instrument["strike_increment"]),
        multiplier=float(instrument["multiplier"]),
        spot_basis=str(pricing["spot_basis"]),
        vol_basis=str(pricing["vol_basis"]),
        risk_free_rate=float(pricing["risk_free_rate"]),
        skew_slope=float(pricing["skew_slope"]),
        day_count=int(pricing["day_count"]),
        settle_price_basis=str(cfg["exit"]["settle_price_basis"]),
        portfolio=portfolio_config_from_dict(cfg["portfolio"]),
    )


def _safe_name(symbol: str) -> str:
    return symbol.lstrip("^").replace("/", "_").lower()


def load_config_and_data(config_path: str | Path) -> tuple[dict, dict, pd.DataFrame, pd.DataFrame]:
    """Wczytuje config, specyfikację instrumentu oraz dane SPX i VIX z parquet."""
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    instrument = yaml.safe_load(Path(cfg["instrument"]["spec_file"]).read_text(encoding="utf-8"))

    data_cfg = cfg["data"]
    processed = Path(data_cfg["processed_dir"])
    spx_path = processed / f"{_safe_name(data_cfg['underlying_symbol'])}.parquet"
    vix_path = processed / f"{_safe_name(data_cfg['vix_symbol'])}.parquet"
    for p in (spx_path, vix_path):
        if not p.exists():
            raise SystemExit(
                f"Brak pliku {p}. Najpierw pobierz dane: "
                f"python -m src.data.download --config {config_path}"
            )
    spx = pd.read_parquet(spx_path)
    vix = pd.read_parquet(vix_path)
    return cfg, instrument, spx, vix
