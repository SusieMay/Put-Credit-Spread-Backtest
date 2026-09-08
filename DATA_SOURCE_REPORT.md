# DATA_SOURCE_REPORT.md

Raport dostępności **darmowych** danych potrzebnych do backtestu strategii
"SPX put credit spread, short strike @ Multi-Day Saty ATR -1, 1 spread / tydzień".

Data raportu: 2026-09-08. Wszystkie oceny dotyczą opcji **całkowicie darmowych**
(bez płatnych API, bez płatnych baz, bez triali wymagających karty).

---

## 1. Czego potrzebuje strategia

| Element | Do czego | Krytyczność |
|---|---|---|
| SPX OHLC dzienny → tygodniowy | wyliczenie poziomu Saty ATR -1 (14-tyg. Wilder ATR) | KRYTYCZNE |
| SPX cena w dniu/godzinie wejścia (pon. 10:00 ET) | wycena wejścia (proxy) / kontekst | ŚREDNIE |
| SPX settlement w piątek (wygasanie) | rozliczenie gotówkowe pozycji | KRYTYCZNE |
| Historyczny chain opcji SPX/SPXW (bid/ask) w chwili wejścia | **prawdziwa** cena kredytu spreadu | KRYTYCZNE dla TRUE backtest |
| IV / delta historyczna | wybór strike'ów po delcie (opcjonalnie), wycena | ŚREDNIE |
| VIX historyczny | reżimy rynkowe, ewentualny proxy IV | ŚREDNIE |
| Stopa wolna od ryzyka | wycena Black-Scholes (proxy) | ŚREDNIE |

---

## 2. Tabela porównawcza źródeł

| source | free? | date range | SPX? | SPXW? | bid/ask? | OHLC? | IV? | delta? | API? | limitations |
|---|---|---|---|---|---|---|---|---|---|---|
| **Stooq** (`^spx`) | ✅ w pełni | ~1789/1927–dziś (dziennie) | ✅ (indeks OHLC) | ❌ | ❌ | ✅ | ❌ | ❌ | CSV/URL | tylko OHLC dzienny indeksu; brak opcji; **od 2024/2025 anty-bot proof-of-work → używamy jako zapasowe** |
| **yfinance** `^GSPC` | ✅ | ~1927–dziś dziennie; intraday 1m tylko ~ostatnie 30 dni | ✅ (indeks) | ❌ | ❌ | ✅ | ❌ | ❌ | Python | intraday tylko krótkie okno; brak wielolet. intraday; **domyślne źródło w projekcie** |
| **yfinance** `^VIX` | ✅ | 1990–dziś dziennie | n/d | n/d | ❌ | ✅ (VIX OHLC) | (VIX = IV 30d) | ❌ | Python | VIX to ATM 30d IV, nie skew OTM |
| **CBOE** (pliki VIX/statystyki) | ✅ (część) | VIX 1990–dziś | częściowo | ❌ | ❌ | ✅ (VIX) | ✅ (VIX) | ❌ | CSV | pełny chain opcji SPX = **płatny** (DataShop) |
| **FRED** (`SP500`) | ✅ | ostatnie ~10 lat dziennie | ✅ (price only) | ❌ | ❌ | ✅ (close) | ❌ | ❌ | API/CSV | tylko ostatnie 10 lat; bez dywidend/TR |
| **DoltHub** `post-no-preference/options` | ✅ (CC-BY-SA 4.0) | ~2020–dziś (EOD) | ❌ (brak indeksu SPX) | ❌ | ✅ | (opcje) | ✅ | ✅ (greeks) | Dolt/SQL | pokrywa **SPY** i ETF-y, NIE SPX; **EOD**, nie 10:00; częstotliwość rzadsza w starszych danych |
| **optionsDX** | ⚠️ część darmowa | wybrane miesiące/ticker | ✅ (SPX płatnie) | częściowo | ✅ | ✅ | ✅ | ✅ | download | pełna historia SPX = **płatna**; darmowe = próbki/EOD, wymaga konta |
| **historicaloptiondata.com** | ❌ płatne | 2002–dziś | ✅ | ✅ | ✅ | ✅ | ✅ | download | **płatne** (tylko darmowe sample files) |
| **ORATS / Databento / dxFeed / Polygon opcje** | ❌ płatne | wieloletnie, intraday | ✅ | ✅ | ✅ | ✅ | ✅ | API | **płatne** (trial/limit/karta) |

Legenda: ✅ tak / ❌ nie / ⚠️ częściowo.

---

## 3. Kluczowy wniosek: TRUE backtest vs PROXY

**Full historical option-chain backtest cannot currently be performed with fully free data.**

Konkretnie brakuje **darmowych, historycznych, śróddziennych (pon. 10:00 ET) kwotowań bid/ask opcji SPX/SPXW**. Takie dane są dostępne wyłącznie **odpłatnie** (CBOE DataShop, optionsDX SPX, historicaloptiondata.com, ORATS, Databento, dxFeed, Polygon płatne plany). Żadne w pełni darmowe źródło nie daje kompletnego chainu opcji **indeksu SPX** w historii, a już zwłaszcza z konkretnym znacznikiem czasu 10:00 ET.

### Co dokładnie da się zrobić za darmo

**A) TRUE(-ish) OPTION BACKTEST — na realnych kwotowaniach, ale z ustępstwami**
- Źródło: **DoltHub `post-no-preference/options`** (realne bid/ask/greeks/IV, EOD).
- Instrument zastępczy: **SPY** (ETF, ~1/10 SPX), NIE SPX. SPY ma realne opcje w tej bazie.
- Ograniczenia: dane **EOD** (koniec dnia), nie 10:00 ET; zakres od ~2020; brak SPXW; różnice SPY vs SPX (dywidendy, styl amerykański SPY vs europejski SPX, rozliczenie).
- To jest **prawdziwy** backtest realnych opcji, ale na **SPY EOD** — trzeba to jasno oznaczać i NIE przedstawiać jako SPX 10:00.

**B) PROXY BACKTEST — SPX + model wyceny**
- Underlying: **SPX dzienny/tygodniowy** (Stooq/yfinance, w pełni darmowe).
- Wycena opcji: **Black-Scholes** z IV szacowaną z **VIX** (darmowy) + korekta skew dla OTM put.
- Stopa: FRED/Treasury (darmowe).
- To jest **model, nie realne kwotowania**. Musi być oznaczone jako PROXY i nigdy mieszane z wynikami TRUE.
- Znane błędy proxy: VIX to ATM 30d IV — zaniża IV głębokich OTM putów (skew), więc kredyt może być niedoszacowany bez modelu skew; brak realnego bid/ask spreadu; brak realnej płynności.

### Czego brakuje do pełnego TRUE SPX backtestu (gdyby kiedyś dokupić dane)
- Historyczny chain SPX/SPXW z bid/ask i (najlepiej) znacznikiem 10:00 ET.
- Historyczne wartości settlement SPX (SET) w dni wygasania.
- Architektura projektu jest tak zaprojektowana, że **podpięcie płatnego źródła = wymiana jednego modułu `data/loaders`**, bez przebudowy strategii/metryk.

---

## 4. Rekomendacja dla tego projektu

1. Zbudować rdzeń na **wolnych danych SPX (Stooq/yfinance)** — to wystarcza do poprawnego, weryfikowalnego wyliczenia poziomu **Saty ATR -1** i do benchmarku SPX buy & hold.
2. Domyślny tryb wyceny opcji: **PROXY (SPX + Black-Scholes + VIX/skew)**, jawnie oznaczony.
3. Tryb walidacyjny: **TRUE-ish na SPY EOD z DoltHub** — do sprawdzenia, jak bardzo proxy odbiega od realnych opcji (kalibracja skew, sanity-check kredytu).
4. Interfejs danych (loader) abstrakcyjny, tak by później dało się podłączyć płatne SPX intraday bez zmian w reszcie kodu.

**Żadne dane syntetyczne nie będą przedstawiane jako prawdziwe historyczne ceny opcji.** Wyniki TRUE i PROXY nigdy nie będą łączone w jednym zestawieniu.
