# Backtest: region-wide unrest, neighbours and protest (1946-2025), cutoffs 1960-2014

<!-- Generated on 2026-10-19 by `python -m forecast.backtest` and `python -m forecast.cases --model unrest`. -->

**Question:** does region-wide unrest help forecast *new* wars? It's tested as several variants of the covariate model, alone and together with neighbours at war (`forecast/logit.py`):
- **Region** (`logit+region`): among the other countries in the same V-Dem region that year, the share in armed conflict, and the share where a new conflict began this year or last.
- **Protest** (`logit+protest`): V-Dem's mass-mobilization score for the country, its change from the year before, and the regional average.
- **All together** (`logit+unrest`): neighbours, region and protest.

**A new scoreboard:** the overall scores in earlier reports are dominated by "wars continue, peace continues", so they barely notice new wars. This report adds a section that looks only at countries at peace the year before, with AUC (how well the model ranks the countries that went to war above those that didn't) and a bootstrap interval for each gain.

**Results:**
- **`logit+unrest` ranks new wars best:** AUC 0.764 at 1 year and 0.749 at 5 years, against 0.731 and 0.720 for the plain covariate model and about 0.63 for the Markov chain. Both gains have bootstrap intervals well clear of zero.
- **Separately:** neighbours help at both horizons, protest at 1 year, and region-wide conflict at 5 years. The youth bulge doesn't help.
- **The trade-off:** its overall scores are very slightly worse (Brier 0.1605 against 0.1593 at 1 year), and its new-war probabilities are a little less well calibrated. The plain model stays the default for "what state will this country be in"; `logit+unrest` is the model for "where could a new war break out".
- **This corrects `2026-10-neighbours-youth.md`,** which concluded that neighbours don't help. They don't move the overall scores, but they do help rank new wars.

**Case studies with `logit+unrest`:** among countries at peace the year before, 7 of the 9 new wars on the map moved up the ranking.
- Iran 1979: 31st → 5th. The 1978 protests show up in the protest score.
- Crimea 2014: 22nd → 13th.
- Kosovo 1998: 22nd → 16th.
- Yugoslavia 1991: 58th → 46th.
- Syria 2011: 73rd → 56th. Still a miss: with yearly data, the Arab Spring that began in December 2010 is barely visible from the start of 2011.
- Lebanon 1975 and Chechnya 1999 moved down. The full case table follows the backtest.

Lower is better. A model is only useful if it beats both baselines.

## 1 year ahead

| model | forecasts | Brier | log score |
|---|---|---|---|
| logit | 8997 | 0.1593 | 0.3247 |
| logit+region | 8997 | 0.1594 | 0.3255 |
| logit+youth | 8997 | 0.1595 | 0.3261 |
| logit+protest | 8997 | 0.1595 | 0.3248 |
| logit+neighbours | 8997 | 0.1597 | 0.3250 |
| logit+region+protest | 8997 | 0.1597 | 0.3253 |
| logit+unrest | 8997 | 0.1605 | 0.3258 |
| markov | 8997 | 0.1661 | 0.3621 |
| persistence | 8997 | 0.1830 | 0.4405 |
| base-rate | 8997 | 0.6406 | 1.1365 |

## 5 years ahead

| model | forecasts | Brier | log score |
|---|---|---|---|
| logit | 8985 | 0.3031 | 0.5964 |
| logit+neighbours | 8985 | 0.3036 | 0.5977 |
| logit+region | 8985 | 0.3043 | 0.6003 |
| logit+protest | 8985 | 0.3055 | 0.6034 |
| logit+region+protest | 8985 | 0.3057 | 0.6048 |
| logit+youth | 8985 | 0.3059 | 0.6007 |
| logit+unrest | 8985 | 0.3065 | 0.6049 |
| markov | 8985 | 0.3411 | 0.6767 |
| persistence | 8985 | 0.3736 | 0.8532 |
| base-rate | 8985 | 0.6706 | 1.1802 |

## New conflicts: countries at peace the year before

Only countries not in armed conflict or civil war at the start. The question is whether a new conflict breaks out by the horizon. Brier is for that yes/no forecast. AUC is the chance that a country where conflict did break out was rated riskier than one where it didn't (0.5 is a coin flip, 1.0 perfect).

### 1 year ahead

| model | forecasts | new conflicts | Brier | AUC |
|---|---|---|---|---|
| logit+unrest | 7508 | 279 | 0.0354 | 0.764 |
| logit+neighbours | 7508 | 279 | 0.0351 | 0.751 |
| logit+protest | 7508 | 279 | 0.0353 | 0.750 |
| logit+region+protest | 7508 | 279 | 0.0353 | 0.749 |
| logit+youth | 7508 | 279 | 0.0353 | 0.733 |
| logit+region | 7508 | 279 | 0.0353 | 0.733 |
| logit | 7508 | 279 | 0.0351 | 0.731 |
| markov | 7508 | 279 | 0.0356 | 0.625 |
| persistence | 7508 | 279 | 0.0358 | 0.500 |
| base-rate | 7508 | 279 | 0.0453 | 0.480 |

Each variant against the plain covariate model (`logit`), on the same forecasts: the change in AUC, with a 95% interval from 1,000 bootstrap resamples. An interval that includes 0 means the gain could be luck.

- logit+neighbours: +0.020 (+0.010 to +0.032)
- logit+protest: +0.019 (+0.007 to +0.032)
- logit+region: +0.002 (-0.007 to +0.011)
- logit+region+protest: +0.019 (+0.006 to +0.032)
- logit+unrest: +0.033 (+0.018 to +0.049)
- logit+youth: +0.002 (-0.004 to +0.008)

### 5 years ahead

| model | forecasts | new conflicts | Brier | AUC |
|---|---|---|---|---|
| logit+unrest | 7501 | 540 | 0.0657 | 0.749 |
| logit+region+protest | 7501 | 540 | 0.0654 | 0.740 |
| logit+neighbours | 7501 | 540 | 0.0650 | 0.736 |
| logit+region | 7501 | 540 | 0.0650 | 0.732 |
| logit+youth | 7501 | 540 | 0.0660 | 0.728 |
| logit+protest | 7501 | 540 | 0.0667 | 0.726 |
| logit | 7501 | 540 | 0.0652 | 0.720 |
| markov | 7501 | 540 | 0.0662 | 0.636 |
| persistence | 7501 | 540 | 0.0683 | 0.500 |
| base-rate | 7501 | 540 | 0.0714 | 0.452 |

Each variant against the plain covariate model (`logit`), on the same forecasts: the change in AUC, with a 95% interval from 1,000 bootstrap resamples. An interval that includes 0 means the gain could be luck.

- logit+neighbours: +0.016 (+0.007 to +0.026)
- logit+protest: +0.006 (-0.003 to +0.015)
- logit+region: +0.012 (+0.004 to +0.020)
- logit+region+protest: +0.020 (+0.009 to +0.030)
- logit+unrest: +0.029 (+0.017 to +0.042)
- logit+youth: +0.008 (+0.002 to +0.016)

## Calibration of the Markov model, 1 year ahead

When the model said about p, how often did it happen?

- **civil-war:** said 1% → happened 1% (n=8581), said 71% → happened 70% (n=416)
- **armed-conflict:** said 3% → happened 4% (n=7847), said 22% → happened 30% (n=77), said 68% → happened 69% (n=1073)
- **democracy:** said 1% → happened 2% (n=6098), said 97% → happened 97% (n=2899)
- **autocracy:** said 4% → happened 3% (n=3664), said 23% → happened 18% (n=724), said 95% → happened 93% (n=4609)

---

## Case studies (`logit+unrest`)

For each conflict, the models were trained only on what was known before it started. "Risk" is the probability of armed conflict or civil war on that country's territory. Rank is among all countries that year (1 = highest).

For a new war in a country at peace the year before, the fairer comparison is the last column: the rank among countries that were also at peace, since ongoing wars fill the top of the overall ranking.

| Event | Country | State the year before | Covariate model: risk that year (rank) | within 5 years (rank) | Markov chain: risk that year (rank) | Rank among countries at peace |
|---|---|---|---|---|---|---|
| Nigerian Civil War (1967) | NGA | armed-conflict | 68% (20 of 154) | 57% (15) | 68% (18) | already in conflict |
| Bangladesh Liberation War (1971) | PAK | autocracy | 11% (29 of 155) | 13% (52) | 4% (86) | 7 of 133 |
| Lebanese Civil War (1975) | LBN | autocracy | 4% (57 of 157) | 5% (100) | 4% (74) | 32 of 132 |
| Soviet invasion of Afghanistan (1979) | AFG | civil-war | 93% (11 of 156) | 78% (6) | 84% (1) | already in conflict |
| Iranian Revolution (1979) | IRN | autocracy | 19% (33 of 156) | 30% (32) | 4% (67) | 5 of 128 |
| Iran–Iraq War (1980) | IRQ | armed-conflict | 91% (15 of 156) | 81% (6) | 75% (18) | already in conflict |
| Yugoslav Wars (1991) | SRB | autocracy | 5% (82 of 170) | 11% (86) | 4% (99) | 46 of 134 |
| Rwandan genocide (1994) | RWA | armed-conflict | 78% (24 of 173) | 66% (26) | 75% (27) | already in conflict |
| First Chechen War (1994) | RUS | armed-conflict | 80% (23 of 173) | 80% (11) | 75% (26) | already in conflict |
| First Congo War (1996) | COD | autocracy | 4% (93 of 173) | 9% (90) | 4% (42) | 62 of 142 |
| Kosovo War (1998) | SRB | autocracy | 9% (47 of 173) | 12% (66) | 4% (84) | 16 of 142 |
| Second Chechen War (1999) | RUS | autocracy | 22% (41 of 174) | 25% (42) | 4% (80) | 8 of 141 |
| US-led war in Afghanistan (2001) | AFG | civil-war | 99% (1 of 175) | 92% (2) | 91% (1) | already in conflict |
| Sectarian civil war in Iraq (2006) | IRQ | civil-war | 87% (15 of 175) | 62% (21) | 91% (4) | already in conflict |
| Syrian civil war (2011) | SYR | autocracy | 3% (81 of 175) | 7% (75) | 5% (80) | 56 of 150 |
| Russia annexes Crimea (2014) | UKR | autocracy | 9% (40 of 176) | 12% (50) | 5% (86) | 13 of 149 |
| Yemeni civil war (2014) | YEM | armed-conflict | 85% (20 of 176) | 66% (17) | 77% (27) | already in conflict |
| Russia invades Ukraine (2022) | UKR | armed-conflict | 85% (24 of 176) | 63% (28) | 78% (34) | already in conflict |

The covariate model ranked 6 of 18 cases among the 20 highest-risk countries in the year they started. Of the 9 wars that began in a country at peace, it placed 6 in the riskiest quarter of peaceful countries (a random guess would place about 2).

## Who else was flagged: the false-alarm check

The covariate model's ten highest-risk countries for the start year of each case, with what actually happened that year (state from the latest data). Countries that were already at war mostly stay at war, so the interesting entries are the peaceful ones near the top.

- **1967:** VDR 95%, LAO 93%, VNM 93%, IDN 92%, IND 92%, MYS 91% **(no conflict)**, MMR 90%, ISR 90%, YEM 88%, YMD 84%
- **1971:** MMR 97%, LAO 97%, VDR 96%, IND 96%, KHM 95%, VNM 93%, ETH 91%, TCD 90%, ISR 89%, IRQ 85% **(no conflict)**
- **1975:** VDR 97%, VNM 97%, COL 92%, ETH 89%, ISR 89%, ZAF 89%, MMR 87%, CHN 87% **(no conflict)**, GTM 87%, THA 86%
- **1979:** PHL 98%, ZAF 98%, VNM 97%, IDN 94%, MMR 94%, COL 94%, ZWE 94%, KHM 93%, TCD 93%, ISR 93%
- **1980:** ZAF 97%, AFG 96%, COL 94%, PHL 94%, THA 94%, MMR 94%, IRN 94%, TCD 93%, ISR 93%, ETH 93%
- **1991:** AFG 99%, IND 99%, TCD 98%, ETH 98%, PHL 98%, SOM 97%, BGD 97%, COL 97%, NIC 97% **(no conflict)**, SLV 96%
- **1994:** AFG 100%, AGO 98%, TUR 97%, IND 96%, COL 95%, AZE 95%, LKA 94%, GEO 93% **(no conflict)**, PHL 93%, ISR 93%
- **1996:** AFG 99%, PAK 96%, TUR 96%, COL 95%, IND 95%, SDN 94%, ETH 94%, AGO 93%, SLE 92%, GTM 92% **(no conflict)**
- **1998:** AFG 99%, PAK 96%, TUR 95%, IND 95%, AGO 94%, COL 93%, RWA 93%, KHM 93%, DZA 93%, LKA 93%
- **1999:** AFG 99%, AGO 98%, PAK 97%, SLE 97%, IND 96%, RWA 95%, DZA 95%, LKA 95%, TUR 95%, COL 94%
- **2001:** AFG 99%, TCD 98%, AGO 97%, IND 96%, SDN 96%, BDI 96%, PHL 96%, LKA 95%, PAK 95%, COL 94%
- **2006:** NPL 97%, AFG 97%, IND 95%, DZA 94%, TUR 93%, COL 93%, IDN 92% **(no conflict)**, PHL 92%, MMR 91%, SDN 91%
- **2011:** PAK 98%, AFG 97%, SDN 96%, TUR 94%, IND 94%, DZA 94%, IRQ 94%, TCD 93% **(no conflict)**, THA 92%, COL 91%
- **2014:** IRQ 98%, PAK 98%, AFG 98%, TUR 97% **(no conflict)**, THA 95%, COD 95%, IND 94%, DZA 94%, MMR 93%, UGA 92%
- **2022:** NGA 98%, ETH 98%, PAK 97%, SOM 97%, IRQ 96%, SDN 95%, YEM 95%, IND 94%, AFG 94%, MLI 93%
