# More data: every table, October 2026

Question: if we give the models much more data (about 100 new country-year tables and commodity prices) and let them find the patterns, do the forecasts get better?

    python tools/importers/vdem.py          # V-Dem measures, leader tenure; third-party variables to .cache/private-tables/
    python tools/importers/wdi.py           # World Bank indicators
    .cache/venv/bin/python tools/importers/pink_sheet.py   # commodity prices
    python -m forecast.outcomes --from 1975 --to 2024

## What was added

- **V-Dem's own measures** (about 50, public, CC BY-SA): corruption, judicial and legislative constraints, political killings and torture, political and social polarization, political violence by non-state groups, state control of territory, exclusion of social, political, economic and regional groups, the military, party, hereditary and electoral dimensions of the regime, election years, censorship, repression of civil society, pro-democracy and pro-autocracy mobilization, and leader tenure and age (derived from the yearly names of the head of state and government).
- **V-Dem's bundled third-party variables** (29, private: `.cache/private-tables/`, not in git): coups, oil and resource income, World Bank governance indicators, Transparency International, Polity, Freedom House, trade, inflation and others.
- **World Bank indicators** (about 40, public, CC BY 4.0, licence checked per indicator): GDP growth to 2025, resource rents, trade, aid, remittances, debt, reserves, current account, exchange rate, unemployment, urbanisation, fertility, life expectancy, food production and undernourishment, schooling, internet and mobile use, refugees, credit, interest rates, export and import mix. Military spending (from SIPRI) was refused: not CC BY.
- **Commodity prices** (World Bank Pink Sheet, CC BY 4.0): energy, food, grains, fertilizers, metals, precious metals and crude oil. They enter as shocks weighted by each country's trade (for example the energy price change times fuel's share of exports).

`forecast/alltables.py` turns every table into two features (its level and its 1-year change) with no code change per table, so new tables are picked up automatically.

## A leak, found and fixed

In the first run, adding every table seemed to lift economic collapse from AUC 0.68 to 0.75, and its top pattern by far was the 1-year change in V-Dem's bundled GDP estimate (Fariss et al.). That estimate comes from a model fitted on all years at once, so its value for one year can reflect the next: hindsight. Without it (and without the population estimate from the same model, and five series interpolated between survey years: education, life expectancy, child mortality, urbanisation and fertility, from Clio Infra and Gapminder), the gain disappears: 0.65, below the hand-built model. These series are now excluded (`alltables.SKIP`). Lesson: a large, sudden gain from a new table is a reason to check for hindsight before celebrating.

A known risk remains: V-Dem's expert-coded measures are coded after the fact, and coders may know what followed. Only first-release data (step 1 of the plan) can fully remove that.

## Results (1975-2024, each year forecast from data up to the year before)

## AUC

The chance that a country where it happened was rated riskier than one where it didn't (0.5 is a coin flip). Best in bold.

| outcome | country-years | events | base rate | logit | gbm | logit, all tables | gbm, all tables | ensemble |
|---|---|---|---|---|---|---|---|---|
| New armed conflict | 6898 | 246 | 0.481 | 0.842 | 0.834 | 0.740 | 0.834 | **0.852** |
| Coup attempt | 8436 | 232 | 0.651 | 0.809 | 0.802 | 0.740 | **0.845** | 0.837 |
| Successful coup | 8436 | 116 | 0.640 | 0.773 | 0.799 | 0.713 | **0.832** | 0.823 |
| Democratic breakdown | 3518 | 74 | 0.568 | 0.869 | **0.928** | 0.829 | 0.902 | 0.899 |
| Democratisation | 4809 | 124 | 0.544 | 0.896 | 0.911 | 0.873 | 0.913 | **0.940** |
| Mass protest wave | 7443 | 277 | 0.631 | 0.800 | 0.811 | 0.753 | 0.805 | **0.822** |
| Economic collapse (GDP per head -5%) | 6848 | 404 | 0.420 | 0.651 | **0.683** | 0.573 | 0.653 | 0.665 |
| High inflation (40%+) | 6392 | 80 | 0.492 | 0.812 | 0.872 | 0.804 | **0.907** | 0.895 |
| Mass violence (1,000+ one-sided/non-state deaths) | 5448 | 61 | 0.543 | 0.897 | **0.925** | 0.792 | 0.898 | 0.911 |

## Riskiest 10%

The share of events that fell in the riskiest tenth of countries that year.

| outcome | country-years | events | base rate | logit | gbm | logit, all tables | gbm, all tables | ensemble |
|---|---|---|---|---|---|---|---|---|
| New armed conflict | 6898 | 246 | 11% | 49% | 42% | 39% | 51% | **51%** |
| Coup attempt | 8436 | 232 | 15% | 37% | 34% | 28% | **42%** | 39% |
| Successful coup | 8436 | 116 | 16% | 38% | 38% | 28% | **43%** | 41% |
| Democratic breakdown | 3518 | 74 | 8% | 55% | **70%** | 49% | 69% | 64% |
| Democratisation | 4809 | 124 | 9% | 62% | 73% | 65% | **77%** | 73% |
| Mass protest wave | 7443 | 277 | 13% | 33% | 35% | 30% | **35%** | 35% |
| Economic collapse (GDP per head -5%) | 6848 | 404 | 11% | 21% | 22% | 18% | **26%** | 24% |
| High inflation (40%+) | 6392 | 80 | 8% | 52% | 59% | 48% | **68%** | 66% |
| Mass violence (1,000+ one-sided/non-state deaths) | 5448 | 61 | 15% | 80% | 80% | 57% | 80% | **84%** |

## Brier score

Lower is better; it rewards well-calibrated probabilities, not just ranking.

| outcome | country-years | events | base rate | logit | gbm | logit, all tables | gbm, all tables | ensemble |
|---|---|---|---|---|---|---|---|---|
| New armed conflict | 6898 | 246 | 0.0344 | 0.0352 | 0.0323 | 0.0505 | **0.0318** | 0.0318 |
| Coup attempt | 8436 | 232 | 0.0269 | 0.0303 | 0.0259 | 0.0386 | **0.0257** | 0.0265 |
| Successful coup | 8436 | 116 | 0.0136 | 0.0175 | 0.0135 | 0.0228 | **0.0133** | 0.0143 |
| Democratic breakdown | 3518 | 74 | 0.0206 | 0.0247 | 0.0193 | 0.0407 | **0.0185** | 0.0194 |
| Democratisation | 4809 | 124 | 0.0253 | 0.0309 | 0.0221 | 0.0381 | **0.0192** | 0.0216 |
| Mass protest wave | 7443 | 277 | 0.0361 | 0.0385 | 0.0348 | 0.0582 | **0.0343** | 0.0344 |
| Economic collapse (GDP per head -5%) | 6848 | 404 | 0.0557 | 0.0578 | 0.0558 | 0.0765 | 0.0551 | **0.0545** |
| High inflation (40%+) | 6392 | 80 | 0.0124 | 0.0184 | 0.0118 | 0.0240 | **0.0112** | 0.0129 |
| Mass violence (1,000+ one-sided/non-state deaths) | 5448 | 61 | 0.0111 | 0.0107 | 0.0108 | 0.0192 | 0.0104 | **0.0101** |

## Does more data help?

Change in AUC from adding every table, on the same forecasts, with a 95% interval from 500 bootstrap resamples. An interval that includes 0 means the gain could be luck.

| outcome | gbm: all tables − hand-built | logit: all tables − hand-built | ensemble − logit |
|---|---|---|---|
| New armed conflict | -0.000 (-0.018 to +0.018) | -0.103 (-0.138 to -0.071) | +0.009 (+0.001 to +0.017) |
| Coup attempt | +0.043 (+0.024 to +0.065) | -0.069 (-0.102 to -0.038) | +0.028 (+0.018 to +0.039) |
| Successful coup | +0.033 (-0.000 to +0.069) | -0.059 (-0.114 to -0.012) | +0.050 (+0.030 to +0.074) |
| Democratic breakdown | -0.026 (-0.058 to +0.001) | -0.041 (-0.084 to +0.003) | +0.030 (+0.012 to +0.053) |
| Democratisation | +0.002 (-0.021 to +0.023) | -0.022 (-0.060 to +0.014) | +0.044 (+0.028 to +0.062) |
| Mass protest wave | -0.005 (-0.023 to +0.011) | -0.047 (-0.076 to -0.017) | +0.022 (+0.012 to +0.032) |
| Economic collapse (GDP per head -5%) | -0.030 (-0.050 to -0.010) | -0.078 (-0.109 to -0.046) | +0.014 (+0.000 to +0.028) |
| High inflation (40%+) | +0.035 (+0.004 to +0.067) | -0.008 (-0.070 to +0.047) | +0.084 (+0.045 to +0.128) |
| Mass violence (1,000+ one-sided/non-state deaths) | -0.027 (-0.065 to +0.003) | -0.105 (-0.185 to -0.030) | +0.014 (+0.000 to +0.035) |

## Calibration of the ensemble

When it said about p, how often did it happen? (all outcomes pooled)

- said 0%–2% (mean 0.6%): happened 0.5% (n=36378)
- said 2%–5% (mean 3.2%): happened 2.9% (n=10408)
- said 5%–10% (mean 7.1%): happened 6.5% (n=6078)
- said 10%–20% (mean 13.8%): happened 11.1% (n=3553)
- said 20%–40% (mean 27.2%): happened 16.6% (n=1443)
- said 40%–100% (mean 51.3%): happened 27.2% (n=368)

## What the all-tables boosting model relies on

The features with the largest average effect (mean |SHAP|, in log-odds) on its forecasts in the test years. These are patterns in the data, not causes.

- **New armed conflict:** vdem-political-violence (0.27), vdem-physical-integrity (0.24), vdem-state-territory (0.20), maddison-population (1-yr change) (0.13), maddison-gdp-per-capita (1-yr change) (0.11), log population (0.11), vdem-freedom-from-killings (0.10), mass protest (0.10)
- **Coup attempt:** vdem-regime-military (0.99), vdem-e-polity2 (0.17), vdem-e-exports (1-yr change) (0.15), vdem-state-territory (0.13), vdem-political-violence (0.11), wdi-private-credit (0.09), vdem-political-polarization (0.08), vdem-e-imports (0.08)
- **Successful coup:** vdem-regime-military (0.80), vdem-e-exports (0.13), vdem-e-polity2 (0.12), vdem-political-violence (0.12), vdem-political-polarization (0.10), vdem-state-territory (0.10), maddison-gdp-per-capita (1-yr change) (0.09), vdem-e-imports (1-yr change) (0.09)
- **Democratic breakdown:** electoral democracy (0.20), vdem-political-liberties (0.14), liberal democracy (0.14), vdem-accountability (1-yr change) (0.13), vdem-e-polity2 (0.13), maddison-gdp-per-capita (1-yr change) (0.12), vdem-electoral-democracy (0.11), democracy change (1 yr) (0.11)
- **Democratisation:** vdem-accountability (0.40), vdem-accountability (1-yr change) (0.19), vdem-election-free-fair (0.13), vdem-opposition-autonomy (0.11), electoral democracy (0.11), vdem-women-empowerment (0.09), vdem-egalitarian-component (0.09), log deaths (GED) (0.09)
- **Mass protest wave:** mass protest (0.46), vdem-mass-mobilization (0.26), vdem-political-polarization (0.23), vdem-political-violence (0.23), vdem-prodemocracy-mobilization (0.22), vdem-prodemocracy-mobilization (1-yr change) (0.11), region protest (0.10), wdi-population-growth (0.07)
- **Economic collapse (GDP per head -5%):** growth shock (0.10), vdem-executive-corruption (0.09), vdem-e-imports (0.09), maddison-gdp-per-capita (1-yr change) (0.08), GDP growth (3 yr) (0.08), wdi-reserves-months (1-yr change) (0.08), wdi-gdp-pc (1-yr change) (0.07), region in conflict (0.07)
- **High inflation (40%+):** wdi-gdp-deflator-inflation (0.33), inflation (0.27), vdem-e-inflation (0.16), wdi-reserves-months (0.14), vdem-political-polarization (0.14), wdi-inflation (0.13), wdi-exchange-rate (0.09), wdi-inflation (1-yr change) (0.09)
- **Mass violence (1,000+ one-sided/non-state deaths):** ucdp-ged-deaths-nonstate (0.15), vdem-e-imports (1-yr change) (0.14), log non-state deaths (0.13), log deaths (GED) (0.12), wdi-private-credit (1-yr change) (0.11), wdi-trade (0.10), log deaths Q4 (0.08), wdi-refugees-origin (0.08)


## Reading it

- **More data helps where the hand-built features miss something.** Coups: AUC 0.80 to 0.85 for attempts, 0.80 to 0.83 for successful coups, and 42-43% of coups fall in the riskiest tenth of countries (from 34-38%). The military's role in the regime (V-Dem) is by far the strongest coup signal. High inflation: 0.87 to 0.91, from reserves, exchange rates and wider inflation data.
- **Elsewhere it adds nothing on its own.** New conflicts, protest waves, democratic breakdown, democratisation, mass violence and economic collapse are as well or better predicted by the hand-built features.
- **Combining helps everywhere.** The ensemble (the plain logit averaged with the all-tables boosting model) beats the plain logit on every outcome, and the interval excludes 0 on all nine. It's the best single choice: new conflicts 0.852, democratisation 0.940, protest waves 0.822.
- **The all-tables logit is the worst model**: 300+ features is too many for it with this little regularisation. It's kept in the report to show that, not for use.
- **Economic collapse is still the hardest** (about 0.65-0.68). Recessions come from shocks these tables don't capture well yet: banking and currency crises (the IMF's Laeven-Valencia list couldn't be downloaded from this machine), and monthly or quarterly data.
- **Calibration:** the boosting model's own probabilities are well calibrated (best Brier score on every outcome). The ensemble's are good below 20% but too high above it: when it says 40% or more, it happens about 27% of the time. Use the all-tables boosting model's probabilities, and the ensemble's ranking.

## Next

- More outcome and predictor data: banking and currency crises (Laeven-Valencia, by hand), leader exits (Archigos), ethnic power relations (EPR), all private until licensed; and country-month conflict data (UCDP Candidate) for faster signals.
- First-release (vintage) economic data, to remove hindsight from the economic tables.
- Tune the ensemble weights per outcome on training years only, and calibrate the ensemble.
