"""Loader darmowych danych dziennych OHLC ze Stooq (bez klucza API).

Stooq udostępnia historię dzienną jako zwykły plik CSV pod adresem:
    https://stooq.com/q/d/l/?s=<symbol>&i=d

Format CSV: Date,Open,High,Low,Close,Volume

Ten moduł NIE ocenia jakości danych (to robi ``quality.py``); tu tylko
pobieramy i parsujemy do znormalizowanego ``pandas.DataFrame``.
"""

from __future__ import annotations

import hashlib
import re
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

STOOQ_URL = "https://stooq.com/q/d/l/"
STOOQ_VERIFY_URL = "https://stooq.com/__verify"

# Znormalizowane nazwy kolumn używane w całym projekcie.
CANONICAL_COLUMNS = ["date", "open", "high", "low", "close", "volume"]

# Komunikaty, które Stooq zwraca zamiast danych (np. limit dzienny).
_STOOQ_ERROR_MARKERS = ("Przekroczono dzienny limit", "Exceeded the daily hits limit")

# Nagłówek udający zwykłą przeglądarkę (Stooq odrzuca puste UA).
_HEADERS = {"User-Agent": "Mozilla/5.0 (backtest-data-loader)"}

# Wzorzec wyłuskujący parametry wyzwania proof-of-work ze strony anty-botowej.
_CHALLENGE_RE = re.compile(r'c="([^"]+)",\s*d=(\d+)')


class DataDownloadError(RuntimeError):
    """Błąd pobierania danych ze źródła zewnętrznego."""


def _looks_like_challenge(text: str) -> bool:
    """Czy odpowiedź to strona z wyzwaniem proof-of-work Stooq (anty-bot)."""
    return "/__verify" in text and "crypto.subtle.digest" in text


def _solve_stooq_challenge(session: requests.Session, html: str, timeout: int) -> bool:
    """Rozwiązuje wyzwanie proof-of-work Stooq i potwierdza je przez /__verify.

    Strona liczy SHA-256(c + n) i szuka ``n``, dla którego szesnastkowy skrót
    zaczyna się od ``d`` zer, po czym wysyła (c, n) do /__verify. Odtwarzamy
    tę samą logikę w Pythonie, aby uzyskać cookie sesji.

    Returns
    -------
    bool
        True, jeśli weryfikacja się powiodła.
    """
    match = _CHALLENGE_RE.search(html)
    if not match:
        return False
    challenge = match.group(1)
    difficulty = int(match.group(2))
    prefix = "0" * difficulty

    n = 0
    while True:
        digest = hashlib.sha256(f"{challenge}{n}".encode()).hexdigest()
        if digest.startswith(prefix):
            break
        n += 1

    try:
        resp = session.post(
            STOOQ_VERIFY_URL,
            data={"c": challenge, "n": n},
            headers=_HEADERS,
            timeout=timeout,
        )
    except requests.RequestException:  # pragma: no cover - zależne od sieci
        return False
    return resp.ok


def download_stooq_csv(symbol: str, interval: str = "d", timeout: int = 30) -> str:
    """Pobiera surowy tekst CSV ze Stooq dla danego symbolu.

    Obsługuje anty-botowe wyzwanie proof-of-work: jeśli zamiast CSV wróci
    strona weryfikacyjna, rozwiązujemy je i ponawiamy żądanie w tej samej sesji.

    Parameters
    ----------
    symbol:
        Symbol Stooq, np. ``"^spx"`` lub ``"^vix"``.
    interval:
        ``"d"`` = dzienny (jedyny używany w tym etapie).
    timeout:
        Limit czasu żądania HTTP w sekundach.

    Returns
    -------
    str
        Zawartość CSV jako tekst.

    Raises
    ------
    DataDownloadError
        Gdy żądanie się nie powiedzie lub Stooq zwróci komunikat błędu/limitu.
    """
    params = {"s": symbol, "i": interval}
    session = requests.Session()

    def _get() -> requests.Response:
        return session.get(STOOQ_URL, params=params, headers=_HEADERS, timeout=timeout)

    try:
        resp = _get()
        resp.raise_for_status()
        text = resp.text.strip()

        # Do 3 prób rozwiązania wyzwania proof-of-work.
        for _ in range(3):
            if not _looks_like_challenge(text):
                break
            if not _solve_stooq_challenge(session, text, timeout):
                break
            resp = _get()
            resp.raise_for_status()
            text = resp.text.strip()
    except requests.RequestException as exc:  # pragma: no cover - zależne od sieci
        raise DataDownloadError(f"Pobieranie ze Stooq nie powiodło się dla '{symbol}': {exc}") from exc

    if any(marker in text for marker in _STOOQ_ERROR_MARKERS):
        raise DataDownloadError(
            f"Stooq zwrócił komunikat limitu/błędu dla '{symbol}'. "
            f"Spróbuj ponownie później. Treść: {text[:120]!r}"
        )
    if _looks_like_challenge(text):
        raise DataDownloadError(
            f"Nie udało się przejść weryfikacji anty-botowej Stooq dla '{symbol}'."
        )
    if not text or text.lower().startswith("<!doctype") or "<html" in text.lower():
        raise DataDownloadError(f"Stooq nie zwrócił danych CSV dla '{symbol}'.")
    return text


def parse_stooq_csv(text: str) -> pd.DataFrame:
    """Parsuje CSV ze Stooq do znormalizowanego DataFrame.

    Zwraca kolumny: ``date`` (datetime64), ``open/high/low/close`` (float),
    ``volume`` (float; może być 0 dla indeksów). Wiersze posortowane rosnąco
    po dacie; wiersze z niekompletnym OHLC są odrzucane.

    Raises
    ------
    DataDownloadError
        Gdy CSV nie ma oczekiwanych kolumn lub jest pusty.
    """
    df = pd.read_csv(StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"date", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise DataDownloadError(f"CSV nie zawiera wymaganych kolumn: {sorted(missing)}")

    if "volume" not in df.columns:
        df["volume"] = 0.0

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    df = df[CANONICAL_COLUMNS]
    # Odrzuć wiersze bez daty lub bez kompletnego OHLC.
    df = df.dropna(subset=["date", "open", "high", "low", "close"])
    df = df.sort_values("date").reset_index(drop=True)

    if df.empty:
        raise DataDownloadError("Po sparsowaniu CSV nie pozostały żadne poprawne wiersze.")
    return df


def load_daily(symbol: str, interval: str = "d", timeout: int = 30) -> pd.DataFrame:
    """Pobiera i parsuje dzienne OHLC ze Stooq (pobranie + parsowanie)."""
    text = download_stooq_csv(symbol, interval=interval, timeout=timeout)
    return parse_stooq_csv(text)


def load_yahoo_daily(symbol: str) -> pd.DataFrame:
    """Pobiera dzienne OHLC z Yahoo Finance (yfinance) do znormalizowanego DataFrame.

    Używane symbole: ``^GSPC`` (S&P 500 = SPX), ``^VIX``. Zwraca kolumny
    ``date, open, high, low, close, volume`` posortowane rosnąco.

    Raises
    ------
    DataDownloadError
        Gdy yfinance nie zwróci danych.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise DataDownloadError(
            "Brak biblioteki 'yfinance'. Zainstaluj: pip install yfinance"
        ) from exc

    try:
        raw = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False)
    except Exception as exc:  # pragma: no cover - zależne od sieci
        raise DataDownloadError(f"Pobieranie z Yahoo nie powiodło się dla '{symbol}': {exc}") from exc

    if raw is None or raw.empty:
        raise DataDownloadError(f"Yahoo nie zwrócił danych dla '{symbol}'.")

    df = raw.reset_index()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Kolumna daty bywa nazwana 'date' lub 'datetime'.
    date_col = "date" if "date" in df.columns else ("datetime" if "datetime" in df.columns else None)
    if date_col is None:
        raise DataDownloadError(f"Yahoo: brak kolumny daty w wyniku dla '{symbol}'.")

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise DataDownloadError(f"Yahoo: brak wymaganych kolumn {sorted(missing)} dla '{symbol}'.")

    if "volume" not in df.columns:
        df["volume"] = 0.0

    # Usuń strefę czasową i zredukuj do samej daty (dane dzienne).
    dates = pd.to_datetime(df[date_col], errors="coerce")
    if getattr(dates.dt, "tz", None) is not None:
        dates = dates.dt.tz_localize(None)
    df["date"] = dates.dt.normalize()

    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    df = df[CANONICAL_COLUMNS].dropna(subset=["date", "open", "high", "low", "close"])
    df = df.sort_values("date").reset_index(drop=True)

    if df.empty:
        raise DataDownloadError(f"Yahoo: po normalizacji brak poprawnych wierszy dla '{symbol}'.")
    return df


def load_provider_daily(
    provider: str, symbol: str, interval: str = "d", timeout: int = 30
) -> pd.DataFrame:
    """Dyspozytor: pobiera dzienne OHLC z wybranego darmowego źródła.

    Parameters
    ----------
    provider:
        ``"yahoo"`` (domyślne, stabilne) lub ``"stooq"`` (zapasowe).
    """
    provider = provider.lower()
    if provider == "yahoo":
        return load_yahoo_daily(symbol)
    if provider == "stooq":
        return load_daily(symbol, interval=interval, timeout=timeout)
    raise DataDownloadError(f"Nieznany provider danych: '{provider}' (użyj 'yahoo' lub 'stooq').")


def filter_date_range(
    df: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Filtruje DataFrame po zakresie dat (włącznie). ``None`` = brak granicy."""
    out = df
    if start_date:
        out = out[out["date"] >= pd.Timestamp(start_date)]
    if end_date:
        out = out[out["date"] <= pd.Timestamp(end_date)]
    return out.reset_index(drop=True)


def save_raw_csv(text: str, path: str | Path) -> Path:
    """Zapisuje surowy CSV do pliku (data/raw)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def save_processed_parquet(df: pd.DataFrame, path: str | Path) -> Path:
    """Zapisuje znormalizowany DataFrame do Parquet (data/processed)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path
