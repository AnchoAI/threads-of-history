# Gradient boosting and many outcomes (October 2026)

Two questions: does a model that gets every table and finds its own patterns (gradient boosting, `forecast/gbm.py`) beat the hand-built logits? And how well can we forecast things other than war (`forecast/outcomes.py`)?

Run with:

    pip install -r requirements-ml.txt
    python tools/importers/powell_thyne.py      # private coup table, see below
    python -m forecast.backtest                  # state forecasts, cutoffs 1960-2014
    python -m forecast.outcomes --from 1975 --to 2024

**Coup data is private.** Coups come from Powell & Thyne's list (version of 29 August 2026, 497 attempts from 1950). Its licence isn't confirmed, so the table lives in `.cache/private-tables/` and is not in git. This report shows only scores and probabilities derived from it.

## 1. State forecasts: boosting against the logits

Same rolling backtest as before (train before X, forecast from X-1, cutoffs 1960-2014).

| | gbm | logit | logit+all | markov |
|---|---|---|---|---|
| 1 year, Brier | **0.1569** | 0.1593 | 0.1620 | 0.1661 |
| 1 year, log score | 0.3423 | **0.3247** | 0.3298 | 0.3621 |
| 5 years, Brier | 0.3126 | **0.3031** | 0.3234 | 0.3411 |
| New conflicts, 1 year, AUC | 0.768 | 0.731 | **0.773** | 0.625 |
| New conflicts, 5 years, AUC | 0.738 | 0.720 | 0.740 | 0.636 |

- Boosting has the best 1-year Brier score but a worse log score than the logit: now and then it is very sure and wrong, and the log score punishes that hard. Its probabilities need calibrating before anyone reads them as odds.
- On new conflicts it gains +0.037 AUC over the plain logit (95% interval +0.011 to +0.065), about as much as `logit+all` (+0.042), which needed several rounds of hand-picked features to get there. It doesn't beat `logit+all`.
- At 5 years the plain logit stays best overall; `logit+unrest` still ranks 5-year new conflicts best (0.749).
- In line with the literature (`docs/forecasting-literature.md`): trees give a modest gain over a good logit, not a leap.

## 2. Many outcomes, 1975-2024

Each outcome is a yes/no question per country-year, forecast from data up to the year before, by models trained only on earlier years. Most are onsets: a country counts only if it wasn't already in that condition. Definitions are in `forecast/outcomes.py`.

| outcome | country-years | events | base rate | AUC logit | AUC gbm | gbm − logit (95% interval) | top 10% logit | top 10% gbm | Brier logit | Brier gbm |
|---|---|---|---|---|---|---|---|---|---|---|
| New armed conflict | 6898 | 246 | 0.036 | 0.842 | 0.834 | -0.008 (-0.027 to +0.008) | 49% | 42% | 0.0352 | 0.0323 |
| Coup attempt | 8436 | 232 | 0.028 | 0.809 | 0.802 | -0.008 (-0.023 to +0.007) | 37% | 34% | 0.0303 | 0.0259 |
| Successful coup | 8436 | 116 | 0.014 | 0.773 | 0.799 | +0.026 (-0.001 to +0.055) | 38% | 38% | 0.0175 | 0.0135 |
| Democratic breakdown | 3518 | 74 | 0.021 | 0.869 | 0.928 | +0.059 (+0.031 to +0.090) | 55% | 70% | 0.0247 | 0.0193 |
| Democratisation | 4809 | 124 | 0.026 | 0.896 | 0.911 | +0.015 (-0.016 to +0.044) | 62% | 73% | 0.0309 | 0.0221 |
| Mass protest wave | 7443 | 277 | 0.037 | 0.800 | 0.811 | +0.011 (-0.010 to +0.030) | 33% | 35% | 0.0385 | 0.0348 |
| Economic collapse (GDP per head -5%) | 6848 | 404 | 0.059 | 0.651 | 0.683 | +0.032 (+0.009 to +0.056) | 21% | 22% | 0.0578 | 0.0558 |
| High inflation (40%+) | 6392 | 80 | 0.013 | 0.812 | 0.872 | +0.061 (+0.023 to +0.107) | 52% | 59% | 0.0184 | 0.0118 |
| Mass violence (1,000+ one-sided/non-state deaths) | 5448 | 61 | 0.011 | 0.897 | 0.925 | +0.029 (-0.012 to +0.072) | 80% | 80% | 0.0107 | 0.0108 |

Reading it:

- **Everything beats a coin flip by a wide margin.** AUC runs from 0.65 (economic collapse) to over 0.9 (democratic breakdown, democratisation, mass violence).
- **Boosting is clearly better** (interval above 0) for democratic breakdown (+0.059), high inflation (+0.061) and economic collapse (+0.032), all outcomes where thresholds and interactions plausibly matter. For new conflicts and coup attempts the logit is as good or slightly better.
- **Boosting's Brier is lower almost everywhere**, so it is the default for the forward look.
- **Economic collapse is the hardest** (AUC 0.65-0.68): recessions are driven by things not in these tables (commodity prices, financial crises, pandemics). Candidates: commodity prices, IMF vintages, banking-crisis data (Laeven & Valencia).
- **Coups** score 0.80-0.81 for attempts and 0.77-0.80 for successes, in line with published coup models (about 0.77-0.81, see the literature review).
- **Democratic breakdown** at 0.93 compares with 0.84 for V-Dem's own forecasting paper, but on a different definition (crossing 0.5 on the electoral democracy index, one year ahead) and test period, so it's not a like-for-like win.
- **Mass violence** (0.93) is mostly escalation where violence already exists: the top features are recent deaths.

### What the boosting model relies on

Mean |SHAP| (log-odds) over the test years. These are patterns in the data, not causes.

- **New armed conflict:** civil liberties (0.53), log population (0.35), mass protest (0.28), GDP growth (3 yr) (0.18), years in current state (0.17), months with violence (0.17)
- **Coup attempt:** civil liberties (0.41), log infant mortality (0.34), years since last coup (0.30), liberal democracy (0.25), region protest (0.18), GDP growth (3 yr) (0.17)
- **Successful coup:** civil liberties (0.37), log infant mortality (0.36), liberal democracy (0.23), electoral democracy (0.22), log GDP per capita (0.20), mass protest (0.20)
- **Democratic breakdown:** electoral democracy (0.54), liberal democracy (0.45), growth shock (0.33), democracy change (1 yr) (0.32), inflation (0.28), mass protest (0.20)
- **Democratisation:** electoral democracy (0.43), democracy change (1 yr) (0.40), liberal democracy (0.39), civil liberties (0.31), mass protest (0.24), log infant mortality (0.22)
- **Mass protest wave:** mass protest (0.98), log population (0.23), civil liberties (0.21), growth shock (0.20), protest change (0.20), region protest (0.19)
- **Economic collapse (GDP per head -5%):** GDP growth (3 yr) (0.24), log GDP per capita (0.23), growth shock (0.23), log population (0.22), youth bulge (0.21), inflation (0.21)
- **High inflation (40%+):** inflation (0.84), mass protest (0.31), growth shock (0.21), GDP growth (3 yr) (0.19), years in current state (0.18), log non-state deaths (0.16)
- **Mass violence (1,000+ one-sided/non-state deaths):** log deaths (GED) (0.30), log non-state deaths (0.27), democracy change (1 yr) (0.23), log GDP per capita (0.22), log population (0.21), GDP growth (3 yr) (0.19)

Civil liberties and infant mortality (a proxy for state capacity) come up again and again, as in the Political Instability Task Force's model. Economic shocks matter for democratic breakdown, inflation and collapse, which supports keeping the economic tables even though they didn't help the war forecasts.

## 3. Forward look: 2026

Trained on every known year; forecast for 2026 from data through 2025. Highest-risk countries by the boosting model. **These are probabilities, not predictions: most of these will not happen**, and they are uncalibrated (see section 1). Onset outcomes leave out countries already in that condition (for example, countries already at war aren't listed for new conflict). Maddison GDP and population end in 2022, so 2023-2025 are extended at each country's trend over its last 3 years; economic collapse needs real growth figures to say who is eligible, so it isn't ranked.

- **New armed conflict**, 2026: TCD 60%, TZA 33%, BDI 27%, EGY 20%, DZA 18%, UGA 18%, TJK 14%, LBN 12%, ZWE 12%, CIV 9%, BOL 9%, MEX 8%
- **Coup attempt**, 2026: MDG 20%, BEN 17%, GNB 9%, MLI 6%, CIV 6%, MRT 5%, SDN 5%, GAB 5%, BOL 4%, TGO 4%, LBR 4%, BGD 4%
- **Successful coup**, 2026: MDG 6%, FJI 4%, CIV 3%, BGD 3%, MOZ 3%, GNB 3%, TGO 3%, LBR 3%, NER 2%, SLE 2%, TZA 2%, BEN 2%
- **Democratic breakdown**, 2026: FJI 35%, ECU 10%, MDA 10%, MYS 8%, HND 6%, NGA 4%, ROU 2%, MDV 2%, BGR 1%, BOL 1%, LBR 1%, MWI 1%
- **Democratisation**, 2026: ZMB 72%, BIH 43%, BEN 19%, LBN 12%, PNG 8%, ALB 5%, GAB 3%, PHL 3%, SLE 2%, GEO 1%, JOR 1%, HUN 1%
- **Mass protest wave**, 2026: IRN 66%, BLR 48%, BGR 47%, SVN 39%, TUR 39%, TUN 34%, BRA 34%, NPL 33%, GRC 31%, CZE 28%, BEL 26%, PER 24%
- **High inflation (40%+)**, 2026: TUR 44%, BOL 21%, MWI 5%, MDG 3%, PSE 3%, BDI 2%, NGA 2%, HTI 2%, LBR 2%, DZA 1%, SRB 1%, ETH 1%
- **Mass violence (1,000+ one-sided/non-state deaths)**, 2026: BRA 4%, ECU 4%, MOZ 3%, GHA 2%, YEM 2%, MLI 2%, UKR 1%, SOM 1%, COL 1%, IRQ 1%, IND 1%, BDI 1%

The 2026 coup data is partial (to August), so a few 2026 events have already resolved; this list was made without using them. If kept, these should become `scenario` items (private for now) so they're scored when 2026 data arrives.

## Fixes made along the way

- In the first runs, "years since last coup" counted up from 1950 for countries that never had one, which quietly encoded the calendar year. It's now capped at 25.
- In the first forward look, GDP was missing for every country (the table ends in 2022), and the model read "missing" as "nothing happens", as it had learned from small states in training. Mass violence came out near 0% for everyone. GDP is now extended at each country's trend.
- With LightGBM set to 4 threads on a loaded machine, a fit took minutes instead of under a second; it now uses one thread.

## Next

- Calibrate boosting's probabilities (isotonic or Platt scaling, fitted on training years only).
- Add an ensemble of logit and boosting; the literature finds ensembles beat single models.
- Add AUC-PR and the "riskiest fifth" measure to match the Political Instability Task Force and V-Dem papers.
- More outcome data: V-Dem's ERT regime-change episodes, Archigos leader exits, banking crises.
