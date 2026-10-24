# Intelligence estimates as a forecasting benchmark (October 2026)

How good were US intelligence estimates at saying what would happen? And, later: can our models, or AI models, do better given only what was knowable on the same date?

    python -m forecast.benchmark

## How the forecasts were chosen

Choosing famous estimates would bias the result: famous misses make intelligence look bad, famous hits make it look good. So the forecasts were drawn by a rule, set before looking at outcomes:

1. **Pool:** every document headed "Special National Intelligence Estimate" found by searching the State Department's published records (*Foreign Relations of the United States*, history.state.gov): 196 documents, 1952–1988.
2. **Draw:** split into 7 periods, shuffled with a fixed seed, and taken one per period in turn until 35 documents were drawn.
3. **Judgments:** in each drawn document, every judgment in its conclusions that is about an observable event, has a stated or obvious time frame, uses one of Sherman Kent's estimative words, and is not conditional on some future "if".

That gave 29 forecasts from 16 of the 35 documents (about 130 judgments were skipped: about 60 conditional, 40 with no time frame, 20 without a mappable word, 10 too vague). Kent's own table (CIA, *Studies in Intelligence*, 1964) turns words into numbers: "almost certain" 93%, "probable" 75%, "chances about even" 50%, "probably not" 30%, "almost certainly not" 7%. Each forecast records the exact words (`stated_as`) and the mapping (`probability_basis`), in `data/scenarios/`.

## Result

Scored: forecasts whose outcome is `happened` or `did_not_happen` and backed by a quoted source. Six are `ambiguous` and two more rest on indirect outcome evidence (`unverified`); neither kind is scored.

| forecaster | forecasts | happened | Brier | no-skill |
|---|---|---|---|---|
| US intelligence community (SNIE) | 21 | 6 | 0.135 | 0.204 |

## US intelligence community (SNIE)

Calibration: when it said about p, how often did it happen?

- said 0%–15% (mean 7%): happened 0% (n=2)
- said 15%–40% (mean 29%): happened 14% (n=14)
- said 60%–85% (mean 75%): happened 80% (n=5)

Most confident misses:

- SNIE 53/14.3-75: South Vietnam's government survives the dry season (1975-03-27): said 75%, did not happen
- SNIE 100-11-58: China gradually calls off the interdiction of Quemoy (1958-09-16): said 30%, happened
- SNIE 30-5-56: Britain and France intervene against Nasser through another regional crisis (1956-09-19): said 30%, happened
- SNIE 100-11-58: China assaults the major offshore islands (1958-09-16): said 30%, did not happen
- SNIE 100-4-59: China tries to seize Quemoy or cut off its supply (1959-03-13): said 30%, did not happen


## Reading it

- **The estimates show real skill.** A Brier score of 0.135 against 0.204 for a forecaster who always says the overall hit rate means they told likely from unlikely events. But 21 forecasts is a small sample: one or two outcomes change the score noticeably.
- **They leaned towards "it won't happen"**, and were mostly right to: most judgments were "probably not" (about 30%), and those events happened less often than that. The three most confident misses are listed above.
- **Several calls rest on readings a person should check**, each explained in the forecast's `review.notes`: "next few weeks" read as 8 weeks (which decides the Suez 1956 outcome), "dry season" as ending 31 May 1975, two words not on Kent's list ("we do not anticipate" taken as 30%, "highly unlikely" as 7%).

## Next

- **Put the same questions to our models and to AI models**, given only what was knowable on each estimate's date. Our country-year models can answer the questions about coups, wars and regime survival directly; the rest need an AI model with a date cut-off.
- **Draw more.** 35 of 196 documents gave 29 forecasts; the whole pool would give roughly 150, enough to compare decades and topics.
- **Add other forecasters:** National Intelligence Estimates (not only Special ones), declassified British Joint Intelligence Committee assessments, and later the public forecasting record (Good Judgment, Metaculus).
