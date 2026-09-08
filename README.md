# SPX ATR -1 Bull Put Spread — Backtester

Profesjonalny backtester **jednej** strategii opcyjnej na SPX:

> **Sell one SPX put credit spread per week, short strike @ Multi-Day Saty ATR -1.**

Projekt budowany etapami. Ten plik zawiera założenia metodologiczne, wzory,
ograniczenia danych oraz różnicę między backtestem TRUE a PROXY.

---

## Status projektu

**ETAP 1 — ukończony:** badanie strategii i danych.
**ETAP 2 — ukończony:** fundament projektu + warstwa danych (pobieranie SPX/VIX, kontrola jakości, testy).
**ETAP 3 — ukończony:** wskaźnik Wilder ATR (tygodniowy) + poziom Saty ATR -1 + testy no-look-ahead.
**ETAP 4 — ukończony:** wybór spreadu (daty wejścia, ekspiracje SPXW, zaokrąglanie strike'ów, long 50 pkt niżej).
**ETAP 5 — ukończony:** wycena PROXY kredytu (Black-Scholes + VIX + skew). To MODEL, nie realne ceny opcji.
**ETAP 6 — ukończony:** P&L na wygaśnięciu (rozliczenie gotówkowe po realnym zamknięciu SPX).
**ETAP 7 — ukończony:** portfel (sizing pozycji, krzywa kapitału, seria drawdown).
**ETAP 8 — ukończony:** metryki wydajności (CAGR, Sharpe/Sortino/Calmar, profit factor, expectancy).
**ETAP 9 — ukończony:** analizy pogłębione (rok po roku, krachy, tail risk / VaR / CVaR).
**ETAP 10 — ukończony:** wizualizacje (krzywa kapitału, drawdown, histogram P&L, wynik roczny).
**ETAP 11 — ukończony:** pełny pipeline + raport końcowy (jedna komenda: dane → raport).
Zrobione w ETAPIE 1:
- Zweryfikowano definicję "Multi-Day Saty ATR -1" wprost z kodu źródłowego autora → [docs/SATY_ATR_DEFINITION.md](docs/SATY_ATR_DEFINITION.md).
- Zbadano darmowe źródła danych SPX i opcji → [DATA_SOURCE_REPORT.md](DATA_SOURCE_REPORT.md).
- Ustalono, że **pełny TRUE backtest opcji SPX nie jest możliwy w 100% za darmo** (patrz niżej).
- Zaproponowano architekturę projektu (patrz niżej).

Zrobione w ETAPIE 2:
- Szkielet projektu, `requirements.txt`, `configs/base.yaml`, `configs/instruments/SPX.yaml`.
- Loader darmowych danych dziennych: **Yahoo Finance** (domyślny) + **Stooq** (zapasowy) → `src/data/loaders.py`.
- Moduł kontroli jakości danych → `src/data/quality.py`.
- CLI pobierania → `python -m src.data.download --config configs/base.yaml`.
- Testy jednostkowe (12) → `tests/`.

Zrobione w ETAPIE 3:
- Tygodniowy resampling + **Wilder ATR** (zgodny z `ta.rma` z Pine) → `src/indicators/atr.py`.
- Funkcja `saty_atr_level` licząca **short strike = poprzednie zamknięcie tyg. − ATR(14)** bez look-ahead.
- CLI podglądu poziomu → `python -m src.indicators.show_level --config configs/base.yaml`.
- Testy (8), w tym test **braku look-ahead** → `tests/test_atr.py`.

Zrobione w ETAPIE 4:
- Daty wejścia = pierwszy dzień handlowy tygodnia; ekspiracja = najbliższy piątek SPXW (fallback na czwartek).
- Zaokrąglanie **short strike** do siatki (co 5 pkt) i **long strike** = short − `wing_width` (50 pkt) → `src/strategy/spread_selection.py`.
- CLI podglądu spreadów → `python -m src.strategy.show_spreads --config configs/base.yaml`.
- Testy (10), w tym test **braku look-ahead** → `tests/test_spread_selection.py`.

Zrobione w ETAPIE 5:
- Wycena PROXY kredytu: Black-Scholes (europejski put) + zmienność z VIX + prosty skew putowy → `src/strategy/pricing.py`.
- **UWAGA:** to MODEL, nie prawdziwe historyczne ceny opcji SPX (brak darmowego źródła — patrz `DATA_SOURCE_REPORT.md`).
- Sekcja `pricing` w `configs/base.yaml` (spot_basis, vol_basis, risk_free_rate, skew_slope, day_count).
- CLI podglądu wyceny → `python -m src.strategy.show_priced --config configs/base.yaml`.
- Testy (10) → `tests/test_pricing.py`.

Zrobione w ETAPIE 6:
- Rozliczenie gotówkowe na wygaśnięciu: wartość wewnętrzna short/long puta z realnego zamknięcia SPX → `src/strategy/settlement.py`.
- Zrealizowany P&L per transakcja + klasyfikacja (max_profit / partial_loss / max_loss) i flaga wygranej.
- CLI podglądu wyników → `python -m src.strategy.show_results --config configs/base.yaml`.
- Testy (8) → `tests/test_settlement.py`.

Zrobione w ETAPIE 7:
- Sizing pozycji: `fixed_contracts` / `fixed_risk_pct` / `fixed_capital_alloc` → `src/portfolio/engine.py`.
- Krzywa kapitału tydzień po tygodniu + seria obsunięć (drawdown, drawdown %).
- CLI podglądu portfela → `python -m src.portfolio.show_portfolio --config configs/base.yaml`.
- Testy (11) → `tests/test_portfolio.py`.

Zrobione w ETAPIE 8:
- Metryki transakcyjne (win rate, profit factor, expectancy, payoff) i portfelowe (CAGR, max drawdown, Sharpe, Sortino, Calmar) → `src/metrics/performance.py`.
- CLI podglądu metryk → `python -m src.metrics.show_metrics --config configs/base.yaml`.
- Testy (8) → `tests/test_metrics.py`.

Zrobione w ETAPIE 9:
- Rozbicie rok po roku, okna stresowe (COVID 2020, bessa 2022, Q4 2018), tail risk (VaR/CVaR, najgorsze transakcje) → `src/analysis/breakdown.py`.
- CLI podglądu analiz → `python -m src.analysis.show_analysis --config configs/base.yaml`.
- Testy (6) → `tests/test_analysis.py`.

Zrobione w ETAPIE 10:
- Wykresy (matplotlib, backend Agg): krzywa kapitału, drawdown (underwater), histogram P&L, wynik rok po roku → `src/viz/plots.py`.
- CLI generowania → `python -m src.viz.generate_charts --config configs/base.yaml` (zapis do `charts/`).
- Testy (6) → `tests/test_viz.py`.

Zrobione w ETAPIE 11:
- Pełny pipeline w jednej funkcji (dane → sygnał → spread → wycena → rozliczenie → portfel) → `src/backtest/pipeline.py`.
- Generator raportu Markdown → `src/backtest/report.py`.
- CLI całości → `python -m src.backtest.run --config configs/base.yaml` (zapis `results/report.md`, `results/trades.csv`, `results/equity_curve.csv` + wykresy).
- Testy (4) → `tests/test_pipeline.py`.

**Projekt kompletny (82 testy przechodzą).** Cały backtest uruchamiasz jedną komendą — patrz sekcja "Jak uruchomić" niżej.

## Jak uruchomić cały backtest

```bash
python -m venv .venv && source .venv/bin/activate    # raz, przy pierwszym uruchomieniu
pip install -r requirements.txt                       # instalacja zależności
python -m src.data.download --config configs/base.yaml   # pobranie danych SPX + VIX (za darmo)
python -m src.backtest.run --config configs/base.yaml    # pełny backtest -> results/ + charts/
```

Wynik: `results/report.md` (zbiorczy raport), `results/trades.csv`, `results/equity_curve.csv`
oraz wykresy PNG w `charts/`. Testy: `python -m pytest -q`.

## Cel

Sprawdzić, czy strategia miała **realną przewagę** (edge), a nie tylko odtworzyć czyjś wynik.
Interesują nas m.in.: win rate, profit factor, expectancy, CAGR, max drawdown,
Sharpe/Sortino/Calmar, zachowanie w krachach (COVID 2020, bear 2022), tail risk.

---

## Strategia (wersja domyślna)

| Parametr | Wartość domyślna |
|---|---|
| Underlying | SPX |
| Częstotliwość | 1 spread / tydzień |
| Dzień wejścia | poniedziałek |
| Godzina wejścia | 10:00 ET |
| Short strike | Multi-Day Saty ATR -1 |
| Long strike | 50 pkt poniżej short strike |
| Wygasanie | najbliższy odpowiedni piątkowy SPXW |
| Trzymanie | do wygaśnięcia (bez rolowania, bez zarządzania) |

Struktura: **Bull Put Spread** = SELL wyższy put + BUY niższy put.

Każde odstępstwo od "oficjalnych" zasad będzie **jawnym parametrem** w configu, nigdy cichą zmianą.

## Definicja poziomu Saty ATR -1 (VERIFIED)

> Multi-Day Saty ATR -1 = (zamknięcie poprzedniego tygodnia) − (14-okresowy Wilder ATR na świecach tygodniowych, z poprzedniego zakończonego tygodnia).

Źródło: open-source Pine Script Saty Mahajana (`github.com/satymahajan/saty_atr_levels`).
Pełny opis i wzory: [docs/SATY_ATR_DEFINITION.md](docs/SATY_ATR_DEFINITION.md).
Poziom jest **stały przez cały tydzień** i w pełni znany przed wejściem w poniedziałek → brak look-ahead dla tego elementu.

---

## Wzory transakcji (osobno zdefiniowane, nie mieszać)

Oznaczenia: $K_s$ = short strike, $K_l$ = long strike, $w = K_s - K_l$ (wing width),
$m$ = mnożnik kontraktu (SPX), $P_s, P_l$ = ceny wejścia short/long put.

- **Credit** (kredyt netto na 1 spread, w punktach): $c = P_s - P_l$
- **Credit ($)**: $C = c \cdot m$
- **Max profit**: $\text{MaxProfit} = c \cdot m$
- **Max loss**: $\text{MaxLoss} = (w - c) \cdot m$
- **Notional (short leg)**: $K_s \cdot m$
- **Margin / kapitał na ryzyko**: definiowany osobno (broker-dependent; domyślnie = MaxLoss)
- **Return on risk**: $\text{RoR} = \dfrac{\text{MaxProfit}}{\text{MaxLoss}}$
- **Return on capital**: liczony względem zaalokowanego kapitału portfela

P&L na wygaśnięciu (rozliczenie **gotówkowe** SPX, settlement $S_T$):
- wewnętrzna wartość short put: $\max(K_s - S_T, 0)$
- wewnętrzna wartość long put: $\max(K_l - S_T, 0)$
- payoff spreadu (koszt zamknięcia): $\text{intr} = \max(K_s - S_T,0) - \max(K_l - S_T,0)$
- **Gross P&L** = $(c - \text{intr}) \cdot m$
- **Net P&L** = Gross P&L − Fees

Mnożnik $m$ oraz specyfikacja instrumentu NIE są hardkodowane — trafią do osobnego
configu instrumentu (`configs/instruments/SPX.yaml`) wraz z udokumentowanym źródłem.

---

## Egzekucja (modele wejścia)

Zaimplementowane zostaną min. 3 modele (jako parametr):
1. **MID** — obie nogi po cenie środkowej (mid).
2. **BID_ASK** — short put po **bid**, long put po **ask** (konserwatywnie).
3. **SLIPPAGE** — mid z konfigurowalnym poślizgiem.

Koszty (konfigurowalne, **nie zmyślamy wartości** — domyślnie 0, do ustawienia przez użytkownika):
`commission_per_contract`, `slippage`, `exchange_fees`, `other_fees`.

Każdy wynik raportuje: **Gross P&L / Fees / Net P&L**.

---

## Dane: TRUE vs PROXY (bardzo ważne)

Pełny opis w [DATA_SOURCE_REPORT.md](DATA_SOURCE_REPORT.md). Skrót:

> **Full historical option-chain backtest cannot currently be performed with fully free data.**

Darmowe, historyczne, śróddzienne kwotowania bid/ask opcji **SPX/SPXW** nie istnieją — są tylko **płatne**
(CBOE DataShop, optionsDX SPX, historicaloptiondata.com, ORATS, Databento, dxFeed, Polygon płatne plany).

Dlatego projekt ma **dwa rozdzielne tryby** (nigdy łączone w jednym zestawieniu):

- **TRUE(-ish) OPTION BACKTEST** — realne opcje z DoltHub `post-no-preference/options`, ale **SPY EOD** (nie SPX, nie 10:00 ET), od ~2020. Prawdziwe bid/ask, do walidacji/kalibracji.
- **PROXY BACKTEST** — **SPX** (Stooq/yfinance, darmowe) + wycena **Black-Scholes** z IV z **VIX** + korekta skew. To **model**, jawnie oznaczony jako proxy.

Zasady twarde:
- Dane syntetyczne **nigdy** nie są przedstawiane jako prawdziwe historyczne ceny opcji.
- Wyniki TRUE i PROXY **nigdy** nie są mieszane.
- Podpięcie płatnego źródła SPX w przyszłości = wymiana modułu `data/loaders`, bez przebudowy reszty.

---

## Znane biasy i ograniczenia (do egzekwowania w kodzie i testach)

- **Look-ahead bias** — zakaz użycia danych z przyszłości. ATR tylko z zakończonych świec; ceny/IV/bid-ask tylko do chwili wejścia. Powstanie osobny test wykrywający look-ahead.
- **Survivorship bias** — dla SPX/SPY (indeks/ETF) mały, ale opisany.
- **Liquidity bias** — model MID/BID_ASK i poślizg; brak realnej książki zleceń.
- **Slippage / bid-ask** — konfigurowalne, konserwatywne domyślne modele.
- **Model wyceny (proxy)** — BS z VIX zaniża skew OTM putów; korekta skew opisana osobno.
- **SPY vs SPX (tryb TRUE)** — różnice skali, dywidend, stylu wykonania, rozliczenia.
- **Settlement** — nie zakładamy, że ostatnia cena w piątek = settlement; jeśli brak danych SET, przybliżenie jest jawnie opisane.

---

## Proponowana architektura (do realizacji w kolejnych etapach)

```
spx_atr_backtest/
  data/
    raw/            # pobrane surowe pliki (nie wersjonowane)
    processed/      # oczyszczone parquet
  src/
    data/           # loadery (Stooq/yfinance/Dolt/VIX) + abstrakcja źródła
    instruments/    # specyfikacja SPX/SPY (mnożnik, rozliczenie) z configów
    indicators/     # Wilder ATR, poziomy Saty ATR
    options/        # Black-Scholes, greeks, skew (proxy) + wybór kontraktu
    strategy/       # logika wejścia/wyjścia
    execution/      # modele MID/BID_ASK/SLIPPAGE, koszty
    portfolio/      # sizing, equity, kapitał, ryzyko
    metrics/        # wszystkie metryki wynikowe
    analysis/       # reżimy, crash analysis, sweep, OOS, Monte Carlo
    visualization/  # wykresy
  configs/          # base.yaml, sweep.yaml, instruments/*.yaml
  tests/            # pytest: ATR, poziom, credit, P&L, settlement, no-lookahead...
  results/          # summary.json, trades.csv, equity.csv, *_returns.csv
  charts/           # equity_curve.png, drawdown.png, ...
  docs/             # SATY_ATR_DEFINITION.md, notatki metodologiczne
  notebooks/
  main.py
  requirements.txt
  README.md
```

Kluczowa separacja przepływu:
**DATA → INDICATORS → STRATEGY → OPTION SELECTION → EXECUTION → PORTFOLIO → METRICS → ANALYSIS**

---

## Uruchamianie (docelowo, po kolejnych etapach)

```bash
python main.py --config configs/base.yaml
python main.py --config configs/sweep.yaml
```

## Reprodukowalność

Wszystkie parametry w `configs/*.yaml`, wersje bibliotek w `requirements.txt`,
ziarno losowe dla Monte Carlo w configu. Każdy wynik zapisywany do `results/`.

## Biblioteki (planowane, minimalny zestaw)

`python`, `pandas`, `numpy`, `scipy`, `matplotlib`, `plotly`, `pyarrow`, `pytest`,
`pyyaml`, `requests` (pobieranie darmowych CSV), opcjonalnie `yfinance`, `doltcli`/klient Dolt.
Nic zbędnego.
