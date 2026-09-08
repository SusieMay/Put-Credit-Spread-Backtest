"""Testy jednostkowe kontroli jakości danych."""

import pandas as pd

from src.data.quality import data_quality_report, has_errors


def _clean_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
            ),
            "open": [10.0, 10.2, 10.1, 10.3],
            "high": [10.5, 10.6, 10.4, 10.7],
            "low": [9.8, 10.0, 9.9, 10.1],
            "close": [10.2, 10.1, 10.3, 10.5],
            "volume": [0.0, 0.0, 0.0, 0.0],
        }
    )


def _result_for(report: pd.DataFrame, check: str):
    return report.loc[report["check"] == check, "result"].iloc[0]


def test_clean_data_has_no_errors():
    report = data_quality_report(_clean_df())
    assert not has_errors(report)
    assert _result_for(report, "n_rows") == 4
    assert _result_for(report, "duplicate_dates") == 0


def test_duplicate_dates_flagged_as_error():
    df = _clean_df()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True).sort_values("date")
    report = data_quality_report(df)
    assert _result_for(report, "duplicate_dates") == 1
    assert has_errors(report)


def test_high_lt_low_flagged_as_error():
    df = _clean_df()
    df.loc[1, "high"] = 1.0  # high < low
    report = data_quality_report(df)
    assert _result_for(report, "high_lt_low_rows") == 1
    assert has_errors(report)


def test_nonpositive_prices_flagged_as_error():
    df = _clean_df()
    df.loc[2, "close"] = -5.0
    report = data_quality_report(df)
    assert _result_for(report, "nonpositive_prices_rows") == 1
    assert has_errors(report)


def test_empty_dataframe_flagged():
    empty = pd.DataFrame(
        columns=["date", "open", "high", "low", "close", "volume"]
    )
    report = data_quality_report(empty)
    assert has_errors(report)
