# Same questions, other forecasters: our models and AI models (October 2026)

The 21 scored questions from the intelligence estimates benchmark (`2026-10-intelligence-estimates.md`) were put to our country-year models and to four AI models.

    python -m forecast.answer_estimates   # our models -> forecast/answers/threads-*.yaml
    python -m forecast.benchmark          # scores everything in forecast/answers/ against the estimates

## How

- **Our models** (`forecast/answer_estimates.py`): they forecast yes/no outcomes per country and year, so only 3 of the 21 questions map onto them: a coup in Uruguay (1965), and whether Ngo Dinh Diem's government in South Vietnam survived (1954, 1960), read as successful coups. Each answer comes from a model trained only on earlier years. The other 18 ask who starts a war, whether a third country intervenes, whether a blockade is lifted, or about a nuclear programme, which our outcomes don't cover.
- **AI models:** Claude Haiku 5.5, Sonnet 5.5, Opus 5.5 and Fable 5.1, each asked through a separate Claude Code subagent with the questions in `forecast/questions/snie-2026-10.yaml`, told to forecast as of the question's date, to use no tools, and to say whether it remembered the outcome. Each was asked twice: with real names and dates ("names shown"), and with names replaced by "Country A" and only the decade given ("names hidden"). The question list used neutral numbers, not our file names. Answers are in `forecast/answers/ai-*.yaml`.

## Results

Brier score: lower is better; 0.25 is always saying 50%. Each forecaster is compared with the original estimates on the same questions.

| forecaster | questions | its Brier | estimates' Brier, same questions | recalled |
|---|---|---|---|---|
| Claude Fable 5.1, names hidden | 21 | 0.123 | 0.135 | 20 |
| Claude Fable 5.1, names shown | 21 | 0.110 | 0.135 | 21 |
| Claude Haiku 5.5, names hidden | 21 | 0.082 | 0.135 | 15 |
| Claude Haiku 5.5, names shown | 21 | 0.051 | 0.135 | 20 |
| Claude Opus 5.5, names hidden | 21 | 0.101 | 0.135 | 18 |
| Claude Opus 5.5, names shown | 21 | 0.101 | 0.135 | 20 |
| Claude Sonnet 5.5, names hidden | 21 | 0.078 | 0.135 | 21 |
| Claude Sonnet 5.5, names shown | 21 | 0.095 | 0.135 | 21 |
| Threads of History: base rate | 3 | 0.001 | 0.052 | – |
| Threads of History: ensemble | 3 | 0.001 | 0.052 | – |
| Threads of History: gbm, all tables | 3 | 0.001 | 0.052 | – |
| Threads of History: gbm | 3 | 0.000 | 0.052 | – |
| Threads of History: logit, all tables | 3 | 0.000 | 0.052 | – |
| Threads of History: logit | 3 | 0.001 | 0.052 | – |

## Reading it

- **The AI models beat the 1950s–80s analysts, but that is mostly memory, not foresight.** Every model said it remembered the outcome of 15 to 21 of the 21 questions, even with names hidden: the details that make a question answerable (a blockaded island off a coast, a capital about to fall in 1975) also identify it. The models were trained on text written decades after these events, so a historical test can't be made fair to them by hiding names.
- **Hiding names helped least where it mattered.** Haiku's score worsened from 0.051 to 0.082 when names were hidden (it recalled fewer outcomes), which shows hindsight at work; Sonnet's and Opus's barely changed because they still recognised nearly every case.
- **Our models' result is uninformative.** Their 3 questions were all "no coup", and a plain base rate scores as well as any model. The all-tables logit gave 0% and 100%: with only a few years of training data in the 1950s it is badly overconfident.
- **What this tells us:** historical questions are good for testing our country-year models (which see only data up to the date) and for scoring human forecasters, but **a fair AI test needs questions that resolve after the model's training data ends.** That means recording forecasts now on questions that resolve in the next months and years: the leaderboard in the forecasting plan.

## Next

1. **A forward question set**, for example 50 questions resolving between early 2027 and 2028 (coups, elections, wars, inflation, leaders leaving office), each with a resolution source fixed in advance. Record our models' and each AI model's probabilities now, as `scenario` items with `forecast_by` and `forecast_on`, and score them as they resolve. (This publishes forecasts, so it needs your go-ahead.)
2. **More historical questions our models can answer:** draw estimates about coups, regime collapse and civil-war onset specifically, so our models and the analysts can be compared on more than 3 questions.
