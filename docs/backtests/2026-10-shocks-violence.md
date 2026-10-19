# Backtest: economic shocks and recent violence (1946-2025), cutoffs 1960-2014

<!-- Generated on 2026-10-19 by `python -m forecast.backtest --out docs/backtests/2026-10-shocks-violence.md`. -->

**Question:** do economic shocks and recent violence help?
- **Shocks** (`logit+shocks`): last year's GDP growth against the country's own average over the five years before, and consumer-price inflation (World Bank).
- **Recent violence** (`logit+violence`): from UCDP's event data (GED, from 1989), the year's deaths from organized violence, deaths in October–December, deaths from non-state and one-sided violence, the number of months with violence, and the share of deaths in the last quarter.
- **All** (`logit+all`): everything that has helped so far, which is unrest plus shocks plus violence.

**Results, scored on new conflicts:**
- **Shocks:** no gain at either horizon.
- **Recent violence:** a small real gain at 1 year (AUC +0.015). It's diluted here, because the event data only covers cutoffs from 1990. See `2026-10-recent-years.md` for the recent period, where it is fully available.
- **`logit+all`:** the best 1-year ranking of new conflicts, AUC 0.773 against 0.731 for `logit` and 0.764 for `logit+unrest`, with an interval clear of zero. At 5 years `logit+unrest` stays best, and `logit+all`'s overall calibration is the weakest of the covariate models.

Lower is better. A model is only useful if it beats both baselines.

## 1 year ahead

| model | forecasts | Brier | log score |
|---|---|---|---|
| logit | 8997 | 0.1593 | 0.3247 |
| logit+violence | 8997 | 0.1594 | 0.3250 |
| logit+shocks | 8997 | 0.1602 | 0.3274 |
| logit+unrest | 8997 | 0.1605 | 0.3258 |
| logit+all | 8997 | 0.1620 | 0.3298 |
| markov | 8997 | 0.1661 | 0.3621 |
| persistence | 8997 | 0.1830 | 0.4405 |
| base-rate | 8997 | 0.6406 | 1.1365 |

## 5 years ahead

| model | forecasts | Brier | log score |
|---|---|---|---|
| logit | 8985 | 0.3031 | 0.5964 |
| logit+shocks | 8985 | 0.3061 | 0.6056 |
| logit+unrest | 8985 | 0.3065 | 0.6049 |
| logit+violence | 8985 | 0.3138 | 0.6176 |
| logit+all | 8985 | 0.3234 | 0.6430 |
| markov | 8985 | 0.3411 | 0.6767 |
| persistence | 8985 | 0.3736 | 0.8532 |
| base-rate | 8985 | 0.6706 | 1.1802 |

## New conflicts: countries at peace the year before

Only countries not in armed conflict or civil war at the start. The question is whether a new conflict breaks out by the horizon. Brier is for that yes/no forecast. AUC is the chance that a country where conflict did break out was rated riskier than one where it didn't (0.5 is a coin flip, 1.0 perfect).

### 1 year ahead

| model | forecasts | new conflicts | Brier | AUC |
|---|---|---|---|---|
| logit+all | 7508 | 279 | 0.0356 | 0.773 |
| logit+unrest | 7508 | 279 | 0.0354 | 0.764 |
| logit+violence | 7508 | 279 | 0.0352 | 0.746 |
| logit+shocks | 7508 | 279 | 0.0352 | 0.737 |
| logit | 7508 | 279 | 0.0351 | 0.731 |
| markov | 7508 | 279 | 0.0356 | 0.625 |
| persistence | 7508 | 279 | 0.0358 | 0.500 |
| base-rate | 7508 | 279 | 0.0453 | 0.480 |

Each variant against the plain covariate model (`logit`), on the same forecasts: the change in AUC, with a 95% interval from 1,000 bootstrap resamples. An interval that includes 0 means the gain could be luck.

- logit+all: +0.042 (+0.024 to +0.062)
- logit+shocks: +0.006 (-0.004 to +0.017)
- logit+unrest: +0.033 (+0.018 to +0.049)
- logit+violence: +0.015 (+0.003 to +0.028)

### 5 years ahead

| model | forecasts | new conflicts | Brier | AUC |
|---|---|---|---|---|
| logit+unrest | 7501 | 540 | 0.0657 | 0.749 |
| logit+all | 7501 | 540 | 0.0714 | 0.740 |
| logit+violence | 7501 | 540 | 0.0681 | 0.721 |
| logit | 7501 | 540 | 0.0652 | 0.720 |
| logit+shocks | 7501 | 540 | 0.0657 | 0.716 |
| markov | 7501 | 540 | 0.0662 | 0.636 |
| persistence | 7501 | 540 | 0.0683 | 0.500 |
| base-rate | 7501 | 540 | 0.0714 | 0.452 |

Each variant against the plain covariate model (`logit`), on the same forecasts: the change in AUC, with a 95% interval from 1,000 bootstrap resamples. An interval that includes 0 means the gain could be luck.

- logit+all: +0.020 (+0.004 to +0.037)
- logit+shocks: -0.004 (-0.013 to +0.005)
- logit+unrest: +0.029 (+0.017 to +0.042)
- logit+violence: +0.001 (-0.011 to +0.013)

## Calibration of the Markov model, 1 year ahead

When the model said about p, how often did it happen?

- **civil-war:** said 1% → happened 1% (n=8581), said 71% → happened 70% (n=416)
- **armed-conflict:** said 3% → happened 4% (n=7847), said 22% → happened 30% (n=77), said 68% → happened 69% (n=1073)
- **democracy:** said 1% → happened 2% (n=6098), said 97% → happened 97% (n=2899)
- **autocracy:** said 4% → happened 3% (n=3664), said 23% → happened 18% (n=724), said 95% → happened 93% (n=4609)
