# Forecasting plan

How Threads of History goes from explaining the past to making forecasts that can be scored. This builds on the "Forecasting is a goal" decision in `CLAUDE.md`. Published models and benchmarks to compare against are reviewed in `forecasting-literature.md`.

## The idea in one paragraph

The event graph (events, links, sources) explains history but can't predict it. Every event in it is unique, and we chose events *because* they mattered, so a model trained on the graph would learn that everything leads somewhere. Predictions instead come from **country-year numbers**: for each country and each year, what state it was in (democracy, autocracy, at war, had a coup...) and what conditions it had (income, population, ethnic exclusion...). Tens of thousands of country-years give enough repeats to estimate probabilities. Every model is then tested the honest way: train on the past, predict years it hasn't seen, and score the predictions.

## Words used here

- **State:** a label for a country in a year, from a small fixed list, for example `civil-war` or `autocracy`.
- **Transition:** going from one state this year to a state next year, possibly the same one.
- **Markov chain:** a model that estimates the chance of each transition from how often it happened before. It looks only at the current state.
- **Baseline:** a deliberately simple forecast that any real model must beat. Two are used here:
  - **Persistence:** "next year looks like this year."
  - **Base rate:** "next year looks like the world on average."
- **Backtest:** pretend it's year X, train on what was known before X, predict X+1 to X+h, then compare with what happened.
- **Brier score:** how wrong a probability forecast was, from 0 (perfect) to 2 (confidently wrong across all states). Lower is better. A model is only useful if its Brier score beats both baselines.
- **Calibration:** whether forecasts made at "30%" come true about 30% of the time.

## Rules

1. **No look-ahead.** A backtest at year X may use only data that was knowable at X. Where a table has a `published` column, as with first-release economic figures, rows published after X are ignored. This is principle 3, two kinds of time, applied to numbers, and it is this project's edge: most forecasting research quietly uses revised data.
2. **Baselines first.** Every model report shows the persistence and base-rate scores beside the model's.
3. **Licences first.** No dataset goes into `data/` until its entry in `data/datasets/` says `redistribution: allowed` (see `AGENTS.md` rule 8). While the project is private, datasets with an unconfirmed licence may be used locally: their importers write to `.cache/private-tables/`, which git ignores, and `forecast.panel.load_table` reads them from there. Powell & Thyne's coups are the first (`tools/importers/powell_thyne.py`). Never commit those tables.
4. **Forecasts are scenarios, not facts.** Published forecasts become `scenario` items in `data/scenarios/`, with `forecast_by`, `forecast_on` and `resolves_by`. They are scored when they resolve, and the scored record stays public, including the misses.
5. **Plain, careful wording.** "Model X gives a 4% chance of a coup in country Y within a year, against a 1% global base rate" is the right form. Never "Y will have a coup."

## Steps

| # | Step | Status |
|---|---|---|
| 1 | Check the licences of the registered datasets (Task 3a); register Ethnic Power Relations, Archigos, Penn World Table, UN population data, World Bank WDI, UCDP GED and IMF World Economic Outlook vintages | done: cleared V-Dem (CC BY-SA, share-alike), UCDP, Maddison, Penn World Table, UN WPP, World Bank WDI; blocked (no readable licence): Powell & Thyne, EPR, Archigos, IMF vintages |
| 2 | Importers into `data/tables/` | V-Dem, UCDP/PRIO, Maddison, World Bank infant mortality and youth bulge (UN WPP figures via the World Bank) and Natural Earth borders done; Powell & Thyne waits on its licence |
| 3 | `forecast/`: country states, a Markov chain, baselines, backtest and Brier scoring | in progress (built and tested on synthetic data) |
| 4 | First real backtest: train up to each year from 1960 to 2014, predict 1–5 years ahead, and compare against the baselines | done: `docs/backtests/2026-10-markov-baseline.md`. The Markov chain beats both baselines |
| 5 | Models with conditions beyond the current state, on the Political Instability Task Force's predictors: infant mortality, regime type, neighbours in conflict, ethnic exclusion. A replication of a published model | first version done: `forecast/logit.py` beats the Markov chain (`docs/backtests/2026-10-logit-covariates.md`). Neighbours, region-wide unrest and protest together (`logit+unrest`) rank new wars best, AUC 0.76 against 0.73 (`2026-10-regional-unrest.md`); youth bulge gives no gain. Ethnic exclusion is blocked on its licence |
| 5b | Gradient boosting on every table (`forecast/gbm.py`, LightGBM, optional `requirements-ml.txt`), with SHAP explanations | built; scored in `docs/backtests/2026-10-gbm-many-outcomes.md` |
| 5c | Many outcomes, not just war (`forecast/outcomes.py`): coups, democratic breakdown and democratisation, mass protest waves, economic collapse, high inflation, mass violence | built; same report |
| 5d | Much more data (V-Dem measures, World Bank indicators, commodity prices), used automatically (`forecast/alltables.py`) | done: helps coups and inflation; the logit + boosting ensemble beats the logit on every outcome (`docs/backtests/2026-10-more-data.md`) |
| 6 | Hierarchical model with contagion from neighbours, then an ensemble | later |
| 7 | Forecast aggregation and benchmarks: prediction markets, human forecasters, and AI models given only what was knowable on a date | later |
| 8 | Viewer: at "today" the timeline fans out into scenario branches, each as thick as its probability | later |
| — | Experiments, kept labelled as such: tipping-point signals, structural-demographic models (cliodynamics), event-level escalation models (Hawkes processes) | later |

## First set of states (draft)

Each country-year gets exactly one state. The first matching rule wins:

1. `civil-war`: UCDP/PRIO records an intrastate conflict with at least 1,000 battle deaths that year.
2. `armed-conflict`: any UCDP/PRIO conflict on the country's territory that year (25 or more battle deaths).
3. `coup`: Powell & Thyne record a successful coup that year. *(Left out until its licence is resolved.)*
4. `democracy`: V-Dem electoral democracy index (`v2x_polyarchy`) of 0.5 or more.
5. `autocracy`: everything else.

The thresholds are a first guess and will be tuned only on training years, never on test years. The code takes the rules as data, so other state sets can be compared.

## What not to expect

These models are good at base rates and at telling higher-risk from lower-risk countries. They are bad at timing rare shocks. A good result looks like "countries we rated in the top 5% for coup risk had several times the base rate of coups", not "we called the 2021 coup in Myanmar."
