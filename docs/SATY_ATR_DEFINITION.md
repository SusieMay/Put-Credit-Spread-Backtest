# Definicja poziomu "Multi-Day Saty ATR -1"

Status: **VERIFIED DEFINITION** (z jednym jawnie opisanym założeniem interpretacyjnym — patrz sekcja "Założenie interpretacyjne").

## Źródło (autorytatywne, open-source)

- Autor: Saty Mahajan
- Wskaźnik: **Saty ATR Levels** (`//@version=5`, Copyright (C) 2022 Saty Mahajan)
- Oficjalny kod źródłowy (Pine Script), publiczny i open-source:
  - Repozytorium: `https://github.com/satymahajan/saty_atr_levels`
  - Plik: `Saty ATR Levels.pine`
- Strona autora / dystrybucja wskaźnika: `https://satyland.com/atrlevels`

Definicja poniżej została odczytana **wprost z kodu źródłowego**, a nie zrekonstruowana ze słuchu.

## Kluczowe parametry z kodu

```text
atr_length          = input(14, 'ATR Length')            // domyślnie 14
trigger_percentage  = input(0.236, 'Trigger Percentage') // domyślnie 0.236
use_current_close   = input(false, 'Use Current Close')  // domyślnie FALSE
```

Wybór interwału zależy od trybu ("Trading Type"):

```text
Day        -> 'D'   (dzienny)
Multiday   -> 'W'   (TYGODNIOWY)   <-- to jest tryb "Multi-Day"
Swing      -> 'M'   (miesięczny)
Position   -> '3M'
Long-term  -> '12M'
```

Pobranie danych i wyliczenie poziomów (fragment):

```text
period_index   = use_current_close ? 0 : 1               // domyślnie 1
previous_close = request.security(ticker, TF, close[period_index], lookahead=on)
atr            = request.security(ticker, TF, ta.atr(atr_length)[period_index], lookahead=on)

lower_trigger  = previous_close - trigger_percentage * atr   // poziom "Puts <" (0.236 ATR)
lower_1000     = previous_close - atr                        // poziom "-1 ATR"
upper_1000     = previous_close + atr                        // poziom "+1 ATR"
```

W tabeli informacyjnej wskaźnika poziom `lower_1000` jest jawnie podpisany jako **"-1 ATR"**.

## Wynikowa definicja (to, czego używamy w strategii)

Dla trybu **Multi-Day** (= "Multiday" = interwał **tygodniowy**):

> **Multi-Day Saty ATR -1 = (zamknięcie poprzedniego pełnego tygodnia) − (14-okresowy ATR liczony na świecach tygodniowych, wg stanu na koniec poprzedniego pełnego tygodnia)**

Zapis wzorem:

$$\text{Level}_{-1} = C^{W}_{t-1} - \text{ATR}^{W}_{14}(t-1)$$

gdzie:
- $C^{W}_{t-1}$ — zamknięcie poprzedniego **zakończonego** tygodnia,
- $\text{ATR}^{W}_{14}(t-1)$ — 14-okresowy ATR na świecach **tygodniowych**, wartość z **poprzedniego zakończonego** tygodnia.

## Szczegóły metodologiczne (istotne dla wierności odtworzenia)

1. **Interwał ATR**: tygodniowy (`W`). "Multi-Day" w nazwie strategii = tryb "Multiday" wskaźnika = tydzień.
2. **Liczba okresów ATR**: 14.
3. **Metoda ATR**: Pine `ta.atr(14)` = **Wilder RMA** (wygładzanie Wildera) z True Range. To NIE jest zwykła średnia arytmetyczna (SMA) ani EMA — trzeba użyć RMA (alpha = 1/14).
4. **True Range na świecy tygodniowej**: $TR = \max(H-L,\ |H-C_{prev}|,\ |L-C_{prev}|)$, gdzie $C_{prev}$ to zamknięcie **poprzedniej** świecy tygodniowej (uwzględnia luki między tygodniami).
5. **Poprzednie zamknięcie**: tak — używane jest zamknięcie **poprzedniego** tygodnia (`period_index = 1`, bo `use_current_close = false`).
6. **Completed bars**: tak — `period_index = 1` powoduje, że używamy wartości z **zakończonej** świecy tygodniowej, a nie z bieżącego, formującego się tygodnia.
7. **Kiedy poziom powstaje**: na starcie nowego tygodnia; jest wyliczony z danych poprzedniego, zamkniętego tygodnia.
8. **Czy poziom zmienia się w sesji**: **NIE**. Ponieważ bazuje na zamkniętym tygodniu, poziom jest **stały przez cały bieżący tydzień**. To bardzo ważne: dla wejścia w poniedziałek o 10:00 ET poziom jest w pełni znany z góry (brak look-ahead).
9. **Zaokrąglenie do dostępnych strike'ów**: wskaźnik podaje poziom ciągły (np. 6187.34). Sam wskaźnik **nie** zaokrągla do strike'a. Zaokrąglenie do najbliższego dostępnego strike'a SPX/SPXW to decyzja strategii — w projekcie jest osobnym, konfigurowalnym krokiem (parametr `strike_rounding`). Domyślnie zaokrąglamy short strike do najbliższego dostępnego strike'a (SPX standard: co 5 pkt; SPXW ATM bywa co 5 pkt). Metoda zaokrąglania (nearest / floor / ceil) jest parametrem.

## Uwaga o `lookahead=barmerge.lookahead_on`

W Pine Script konstrukcja `request.security(..., close[1], lookahead=barmerge.lookahead_on)` jest standardowym, **nierepaintującym** idiomem: pobiera wartość **ostatniej zamkniętej** świecy wyższego interwału. Dzięki `[1]` (period_index=1) nie ma zaglądania w przyszłość — to poprawne podejście bez look-ahead bias. W naszej rekonstrukcji w Pythonie odwzorujemy to jako: "użyj wartości ATR i close z ostatniego tygodnia, który zakończył się przed dniem wejścia".

## Założenie interpretacyjne (jedyne)

Nazwa strategii mówi "Multi-Day Saty ATR -1". Wskaźnik ma tryb dosłownie nazwany **"Multiday"**, który mapuje się na interwał **tygodniowy**. Przyjmujemy, że "Multi-Day" = ten tryb "Multiday" (tygodniowy). To jedyne założenie interpretacyjne; sama arytmetyka poziomu jest odczytana wprost z kodu.

W konfiguracji projektu poziom ten jest sterowany parametrem:

```yaml
saty_atr_definition:
  version: "verified"          # "verified" | "reconstructed_approximation"
  source: "github.com/satymahajan/saty_atr_levels (Saty ATR Levels.pine, v5, 2022)"
  mode: "multiday"             # -> timeframe weekly
  atr_period: 14
  atr_method: "wilder_rma"
  use_previous_close: true     # period_index = 1
  timeframe: "W"
```

Jeśli w kolejnych etapach ustalimy, że autor strategii ma na myśli inny wariant (np. dzienny ATR liczony z wielu dni w inny sposób), zmienimy `version` na `reconstructed_approximation` i opiszemy różnicę — bez cichej podmiany.
