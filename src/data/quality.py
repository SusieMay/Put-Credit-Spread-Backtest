"""Kontrola jakości danych OHLC.

Generuje raport (DataFrame check/result) przed użyciem danych w backteście.
Sprawdza m.in.: duplikaty dat, braki, ujemne ceny, niespójne OHLC (high<low),
oraz luki w dniach handlowych (dni robocze bez notowania).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def data_quality_report(df: pd.DataFrame) -> pd.DataFrame:
    """Buduje raport jakości dla znormalizowanego DataFrame OHLC.

    Oczekiwane kolumny: ``date, open, high, low, close, volume``.

    Returns
    -------
    pandas.DataFrame
        Kolumny: ``check`` (nazwa testu), ``result`` (wartość/liczba),
        ``severity`` ("info" | "warning" | "error").
    """
    rows: list[dict] = []

    def add(check: str, result, severity: str = "info") -> None:
        rows.append({"check": check, "result": result, "severity": severity})

    n = len(df)
    add("n_rows", n)

    if n == 0:
        add("empty_dataset", True, "error")
        return pd.DataFrame(rows, columns=["check", "result", "severity"])

    add("date_min", df["date"].min().date().isoformat())
    add("date_max", df["date"].max().date().isoformat())

    # Duplikaty dat.
    dup_dates = int(df["date"].duplicated().sum())
    add("duplicate_dates", dup_dates, "error" if dup_dates else "info")

    # Braki wartości w kluczowych kolumnach.
    for col in ("open", "high", "low", "close"):
        miss = int(df[col].isna().sum())
        add(f"missing_{col}", miss, "error" if miss else "info")

    # Ujemne lub zerowe ceny.
    nonpos = int((df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    add("nonpositive_prices_rows", nonpos, "error" if nonpos else "info")

    # Niespójne OHLC: high < low.
    high_lt_low = int((df["high"] < df["low"]).sum())
    add("high_lt_low_rows", high_lt_low, "error" if high_lt_low else "info")

    # high powinno być >= max(open, close); low <= min(open, close).
    hi_bad = int((df["high"] < df[["open", "close"]].max(axis=1)).sum())
    lo_bad = int((df["low"] > df[["open", "close"]].min(axis=1)).sum())
    add("high_below_body_rows", hi_bad, "warning" if hi_bad else "info")
    add("low_above_body_rows", lo_bad, "warning" if lo_bad else "info")

    # Luki w dniach handlowych: dni robocze (Mon-Fri) bez notowania w zakresie.
    all_business = pd.bdate_range(df["date"].min(), df["date"].max())
    present = pd.DatetimeIndex(df["date"].dt.normalize().unique())
    missing_business = all_business.difference(present)
    add("missing_business_days", int(len(missing_business)), "info")

    # Podejrzanie duże skoki dziennego zwrotu (>20%) — potencjalne błędne dane.
    close = df["close"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        rets = np.diff(close) / close[:-1]
    big_jumps = int(np.sum(np.abs(rets) > 0.20)) if len(rets) else 0
    add("daily_moves_gt_20pct", big_jumps, "warning" if big_jumps else "info")

    return pd.DataFrame(rows, columns=["check", "result", "severity"])


def has_errors(report: pd.DataFrame) -> bool:
    """Zwraca True, jeśli raport zawiera jakikolwiek wpis o severity == 'error'."""
    return bool((report["severity"] == "error").any())
