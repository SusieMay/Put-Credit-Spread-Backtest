"""Testy jednostkowe loadera danych (parsowanie CSV, filtr dat).

Testy NIE korzystają z sieci — używają lokalnego fixture'a i tekstu w pamięci.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.data.loaders import (
    CANONICAL_COLUMNS,
    DataDownloadError,
    filter_date_range,
    parse_stooq_csv,
)

FIXTURE = Path(__file__).parent / "fixtures" / "spx_sample.csv"


def test_parse_stooq_csv_columns_and_types():
    text = FIXTURE.read_text(encoding="utf-8")
    df = parse_stooq_csv(text)

    assert list(df.columns) == CANONICAL_COLUMNS
    assert len(df) == 5
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    for col in ("open", "high", "low", "close", "volume"):
        assert pd.api.types.is_float_dtype(df[col])


def test_parse_stooq_csv_sorted_ascending():
    text = FIXTURE.read_text(encoding="utf-8")
    df = parse_stooq_csv(text)
    assert df["date"].is_monotonic_increasing


def test_parse_stooq_csv_known_values():
    text = FIXTURE.read_text(encoding="utf-8")
    df = parse_stooq_csv(text)
    first = df.iloc[0]
    assert first["date"] == pd.Timestamp("2024-01-02")
    assert first["open"] == pytest.approx(4745.20)
    assert first["close"] == pytest.approx(4742.83)


def test_parse_stooq_csv_missing_columns_raises():
    bad = "Date,Foo\n2024-01-02,1\n"
    with pytest.raises(DataDownloadError):
        parse_stooq_csv(bad)


def test_parse_stooq_csv_drops_incomplete_rows():
    text = (
        "Date,Open,High,Low,Close,Volume\n"
        "2024-01-02,10,11,9,10.5,0\n"
        "2024-01-03,,,,,\n"          # wiersz do odrzucenia (brak OHLC)
        "2024-01-04,10,11,9,10.7,0\n"
    )
    df = parse_stooq_csv(text)
    assert len(df) == 2


def test_parse_stooq_csv_empty_after_parse_raises():
    text = "Date,Open,High,Low,Close,Volume\n2024-01-03,,,,,\n"
    with pytest.raises(DataDownloadError):
        parse_stooq_csv(text)


def test_filter_date_range_inclusive():
    text = FIXTURE.read_text(encoding="utf-8")
    df = parse_stooq_csv(text)
    out = filter_date_range(df, start_date="2024-01-03", end_date="2024-01-05")
    assert out["date"].min() == pd.Timestamp("2024-01-03")
    assert out["date"].max() == pd.Timestamp("2024-01-05")
    assert len(out) == 3
