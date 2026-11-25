# Forecasting literature: what others have built and scored

A short review of published work on forecasting political instability and armed conflict, to guide `forecast/` (see `docs/forecasting.md`). It records what each project predicts, at what unit, with what inputs and method, how well it scored, and what we can take from it.

**What we have now, for comparison:** country-year states (civil war, armed conflict, democracy, autocracy) from 1946, a Markov chain, and multinomial logits with covariates. On new conflicts in countries at peace the year before, 1-year AUC is about 0.73–0.77 for 1960–2014 cutoffs (`docs/backtests/2026-10-regional-unrest.md`, `2026-10-shocks-violence.md`) and 0.86–0.89 for 2015–2025 (`2026-10-recent-years.md`).

**How to read this file:** every number below is in quotation marks and was copied from the page listed in [Sources](#sources). All pages were fetched on 2026-10-19. Where we could not fetch a page that states a number, the text says "not verified". The scores come from different outcomes, units and test designs, so **they can't be compared directly with each other or with ours**. The notes say where the designs differ.

---

## 1. Political Instability Task Force (PITF)

Goldstone, Bates, Epstein, Gurr, Lustik, Marshall, Ulfelder & Woodward (2010), *American Journal of Political Science* 54(1) [1].

- **Predicts:** onset of "political instability": revolutionary or ethnic wars, adverse regime changes, and genocides or politicides, two years ahead.
- **Unit:** country-year, 1955–2003.
- **Predictors:** four. Regime type (a five-category measure built from Polity, with "partial democracy with factionalism" as the riskiest type), infant mortality, armed conflict in neighbouring states, and state-led discrimination (from Minorities at Risk). The paper notes: "Being situated in a “bad neighborhood” also was a major risk factor" [1].
- **Method:** logistic regression on a case-control sample: "we adopted the case-control method" [1]. Each onset is matched to three stable country-years from the same region and year.
- **Accuracy:** the abstract says the model works "with a two-year lead time and over 80% accuracy" [1]. Table 1 gives "Onsets Correctly Classified 80.3% 80.0% 87.8% Controls Correctly Classified 81.8% 81.0% 87.8%" for all instability, civil wars and adverse regime changes [1]. The cut point was chosen "with equal levels of type 1 and type 2 errors" [1], so this is classification accuracy on a balanced sample, not an AUC on all country-years.
- **Out-of-sample test:** trained on data up to 1994, then used to rank all countries for 1995–2004: "Number of instability onsets in top quintile of model scores: 18 (86%)" [1].
- **Data and code:** George Mason University's PITF page links to the article and "supporting documentation", and says that for later PITF data readers should go to the Center for Systemic Peace [2]. Whether the replication files are still downloadable: not verified.
- **What we can take:** this is the published model `docs/forecasting.md` (step 5) aims to replicate. Its "top quintile" test matches our "riskiest quarter" check. Our neighbour and infant-mortality variables are its variables; regime type and ethnic discrimination are what we lack. Polity is not in our registry, so we'd need a V-Dem substitute for its regime categories.

## 2. ViEWS / VIEWS (Uppsala University and PRIO)

Hegre et al. (2019), *Journal of Peace Research* 56(2) [3]; Hegre et al. (2021), "ViEWS 2020" [4]; the 2023/24 prediction challenge [5, 6]; the project site [7].

- **Predicts:** today, the number of fatalities in state-based armed conflict, 1–36 months ahead, as probability distributions [5, 7]. The 2019 system predicted the probability of "at least one UCDP-GED event" [3].
- **Unit:** country-month (global) and PRIO-GRID cell-month (0.5°, Africa and the Middle East) [5, 7]. The 2019 system covered "state-based conflict, non-state conflict, and one-sided violence in Africa" [3].
- **Predictors:** conflict history, economy, demography and other "themes", combined in an ensemble [3].
- **Method:** ensembles of many constituent models; ViEWS 2020 added "a new infrastructure for training, evaluating, and weighting models" [4].
- **Accuracy (2019, binary):** for Africa at country-month level, January 2015–December 2017, "Adding conflict history to the baseline model increases AUROC from 0.824 to 0.944", and the full ensemble gave "an increase in AUROC from .9448 to .9555" [3]. These are for any conflict, including continuing conflicts, not for onsets.
- **The 2023/24 prediction challenge:** "24 contributions from 13 teams" [5]. "The main scoring and ranking of the contributions will be done in terms of the CRPS" (continuous ranked probability score), with the log score (ignorance) and mean interval score as secondary metrics [5]. A simple benchmark was hard to beat: VIEWS_bm_ph_conflictology_country12 "is the strongest of the benchmarks – using the historical observations for the last 12 months as the prediction distribution, it performs much better on all metrics. The scores equal to 49.36 for CRPS, 0.65 for IGN, and 873.53 for MIS" [5]. In February 2025, PRIO reported: "As of February 2025, VIEWS’ benchmark model Conflictology leads the rankings for both country- and subnational-level predictions" [6].
- **Earlier competition:** in the 2020–21 escalation competition, "When we build a simple ensemble prediction model ... we can measure an improvement in the prediction from the group, over and above what the average individual model can achieve" [8].
- **Data and code:** the site offers "open-access, monthly forecasts" and data and source-code pages [7]. The challenge's evaluation code is on GitHub (`prio-data/prediction_competition_2023`) and the data and benchmark models are on the challenge page [5].
- **What we can take:** (a) the honest lesson that "last 12 months repeated" beats most clever models; our persistence baseline plays that role and should stay in every report. (b) Their metrics (CRPS, log score) for counts, if we ever forecast fatalities. (c) Their published monthly forecasts are a ready benchmark: aggregate their country-month probabilities to country-years and score them against ours on the same years.

## 3. Conflict Forecast (Mueller & Rauh)

Mueller & Rauh, "The Hard Problem of Prediction for Conflict Prevention" (working paper, December 2020; later in the *Journal of the European Economic Association*) [9]; Mueller, Rauh & Seimon, "Introducing a Global Dataset on Conflict Forecasts and News Topics" [10]; conflictforecast.org [11].

- **Predicts:** outbreak of armed conflict, and its intensity for countries already in conflict, "within the next twelve months" on the live site [11]. The paper uses UCDP GED battle deaths, which it collapses "at the country/month level" [9].
- **Unit:** country-month; the live site also has grid cells "of size 55x55km" [10].
- **Predictors:** topic shares from "a newspaper-text corpus of more than 4 million articles" plus conflict history [9].
- **Method:** topic models (unsupervised), then supervised learning. They tested several learners and "found that the random forest model provides the best forecast overall" [9].
- **Accuracy:** on all cases, text alone gives "an AUC of 0.84" and "The model using text & history also reaches an AUC of 0.92" [9]. On "hard" cases, defined as "when a country has not experienced a battle death for at least 10 years", conflict history alone is not better than random and "the AUC of 0.79 of the combined model (blue solid line) now comes entirely from the text" [9]. A year ahead: "The year-ahead model, in particular, performs extremely well with an AUC of 0.96 and 0.73 in hard cases" [9].
- **Data and code:** news topics and forecasts are "openly available" and "updated monthly at conflictforecast.org" [10]. The site has its own terms of service [11]; licence not verified.
- **What we can take:** their "hard cases" split is the same as our "fresh conflicts" split (no conflict for 10 years). Their 0.73 hard-case year-ahead AUC is the closest published number to our hardest test, though their outcome (any battle death in a month) is broader than ours. News text is a candidate input, but only with publication dates kept, so it fits our "knowable on" rule.

## 4. Early Warning Project (US Holocaust Memorial Museum)

Early Warning Project, "Accuracy of Our Forecasting Model" (analysis run in 2025) [12]; downloads page [13].

- **Predicts:** onset of a new mass killing within two years. A mass killing is when armed groups' deliberate actions "result in the deaths of at least 1,000 noncombatant civilians in that country over a period of one year or less" [12].
- **Unit:** country-year, about 160 countries with populations over 500,000 [12].
- **Predictors:** "about 30 potential risk factors"; the strongest are "a history of mass killing, large population size, high infant mortality, and ethnic fractionalization" [12].
- **Method:** "a logistic regression ... and apply elastic net regularization" [12]. The 2024 model was applied backwards to 1994–2023, giving "4,877 country-year risk estimates" and "38 mass killing onsets" [12].
- **Accuracy:** "more than two of every three (68%) of mass killings onsets since 1994 were captured by our Top-30 list in the two years prior to onset" and "if we classify countries with risk scores of 4% or higher as “high risk” countries, the model generates about twenty “false positives” for every mass killing onset" [12].
- **Data and code:** the downloads page links "our data repository on GitHub" [13]; licence not verified.
- **What we can take:** their evaluation style. They report results in plain terms (share of onsets caught by a top-30 list, false alarms per hit), which suits our audience better than AUC alone. They also count a forecast one year early as a miss, which is strict and worth copying in reports.

## 5. Coup forecasting

- **Data:** Powell & Thyne, "Global instances of coups from 1950 to 2010: A new dataset", *Journal of Peace Research* 48(2), 2011 [14]. Their data page returned "403 Forbidden" when fetched, so current terms are not verified. Our registry already marks it blocked on its licence (`docs/forecasting.md`).
- **Ward / Beger forecasts (Predictive Heuristics, 2017):** country-year forecasts for 161 countries of successful and failed coup attempts, using lasso logistic regression and random forests, with an ensemble [15]. Outcomes come from Powell & Thyne [15]. Training used cross-validation on data up to 2006; "The test fit is for predictions from 2007 to 2016" [15]. The results table gives, for example, "Coup Lasso 0.801 0.088 0.766 0.020" (train ROC, train PR, test ROC, test PR) and "Attempt Disjunction 0.806 0.052" (test ROC and PR) [15]. The author's summary: "The overall AUC-ROC is around 0.8" and "the precision of the predictions is not very high" [15].
- **CoupCast (One Earth Future):** "CoupCast estimates up to August 2021 can be found in the original REIGN data files on the One Earth Future website" [16]. It moved to Jonathan Powell in December 2021 and "went dormant"; his page says "A new forecasting project will go online in August 2026" [16]. Accuracy figures: not verified.
- **What we can take:** coup onset AUC around 0.77–0.80 is the published level to beat. Report AUC-PR beside AUC-ROC, as Beger does, because coups happen in fewer than 4% of country-years [15].

## 6. Human forecasters and markets

- **Good Judgment Project (Tetlock, Mellers et al.):** in the IARPA tournament the official metric was "cumulative Brier scores" over "more than 200 questions" [17]. GJP "won the IARPA tournament: Its best wisdom-of-the-crowd algorithms were on the right side of 50/50 on 86.2% of all daily forecasts, outperforming the simple average of the control group ... by 60% and other teams by 40%" [17]. Superforecasters were the "top 2% of forecasters each year" [17]. Public question-level data: not verified.
- **Metaculus:** a public forecasting platform with an API. A secondary source (Alphascope blog, checked 6 October 2026) says the API "requires authentication" and that its access guidance requires "prior written permission for AI/ML training, evaluation or development" [18]. Metaculus's own terms page blocked our fetch, so this is **not verified** against the primary source. One line: usable as a benchmark only with written permission.
- **Polymarket:** a prediction market. Its docs say market data "is public and does not require authentication" [19]. Its terms page did not render for us, so the terms of reuse are **not verified**. One line: prices are easy to read, but check the terms before storing them.
- **What we can take:** a human or market forecast is the strongest benchmark for step 7 of `docs/forecasting.md`. GJP shows that aggregation and extremising matter as much as the forecasters. Because markets and Metaculus ask about specific events, not country-years, they fit our `scenario` items better than our tables.

## 7. Random forests and boosting against logit

- **The claim:** Muchlinski, Siroky, He & Kocher (2016), *Political Analysis* 24(1), say random forests give "significantly more accurate predictions of civil war onset in out-of-sample data than any of the logistic regression models" [20].
- **The numbers, as summarised by a critic:** "With an area under the curve (AUC) of 0.91, their random forest model outperforms by a large margin three leading logistic regression models: Fearon and Laitin ... with an AUC of 0.77, Collier and Hoeffler ... with an AUC of 0.82, and Hegre and Sambanis ... with an AUC of 0.80" [21].
- **Critique 1 (Wang 2019):** the ROC curve shown was from a model trained on all the data: "The real AUC as presented in Figure 2 in the original article is 0.97 rather than 0.91". Boosting did better still: "gradient boosted trees achieve an AUC of 0.94" [21].
- **Critique 2 (Neunhoeffer & Sternberg 2019):** the same cross-validation was used to tune and to report, so reported performance was too high. Their reanalysis: "a reported PR-AUC value of $0.43$ , which drops to only $0.07$ when the same model is used for out-of-sample prediction" [22]. On the claimed out-of-sample test: "we find no evidence that they did so" [22].
- **Reply (Muchlinski et al. 2019):** they accept Wang's point ("Wang’s observations are correct") and call Neunhoeffer and Sternberg's finding "ultimately less consequential but much more embarrassing" [23].
- **Another comparison:** in V-Dem's regime-transition forecasts (section 8), test AUC-ROC was 0.78 for elastic-net logit, 0.82 for random forest and 0.84 for the ensemble [24].
- **What we can take:** trees can add a few AUC points over logit on rare events, but the headline gains in this literature partly came from evaluation mistakes. Our rolling backtest (train only on years before the cutoff, never tune on test years) is the guard. A gradient-boosted model is worth trying as one more variant, scored the same way.

## 8. Regime breakdown, protest and economic crises (brief)

- **V-Dem "Varieties of Forecasts" (Morgan, Beger & Glynn 2019):** forecasts adverse regime transitions (a drop on V-Dem's Regimes of the World scale) two years ahead [24]. Test forecasts for 2011–2017: "Logit w/Elastic-net Regularization 0.78 0.26 0.064 Random Forest 0.82 0.37 0.059 Gradient Boosted Forest 0.81 0.36 0.061 Ensemble 0.84 0.39 0.059" (AUC-ROC, AUC-PR, Brier) [24]. Yearly AUC-PR "ranges from 0.15, which is low but still an informative improvement over that year’s 0.05 base rate, to 0.51" [24].
- **V-Dem Episodes of Regime Transformation (ERT):** episodes of autocratization and democratization. "ERT 16.0 is based on the V-Dem dataset v16", offered as an R package and as csv or xlsx [25]. "Autocratization is defined as any movement towards autocracy which starts within democracies or autocracies" [25]. We already import V-Dem v16, so this is a cheap extra outcome (same CC BY-SA licence still to be confirmed for ERT).
- **Mass protest:** we found no protest-forecasting benchmark with a verified score in this pass. Our `logit+protest` uses V-Dem's mass-mobilisation score as an input, not an outcome.
- **Banking crises (Laeven & Valencia 2020):** "The database draws on 151 systemic banking crisis episodes around the globe during 1970–2017", with crisis dates, policy responses and costs [26]. It is a dataset of crisis dates, not a forecasting model. It would let us test whether banking crises raise the risk of unrest; licence not checked.

---

## What this means for us

1. **Replicate PITF properly and report it two ways.** Rebuild the four-variable model on our country-years with a V-Dem substitute for Polity's regime categories. Report both its own metric (share of onsets in the top quintile, which was "18 (86%)" for 1995–2004 [1]) and our AUC, so the replication can be checked against the paper.
2. **Report the "hard cases" split as Mueller & Rauh do.** We already separate fresh conflicts (no conflict for 10 years). Make that a standard column with a bootstrap interval in every backtest. Their 0.73 hard-case year-ahead AUC [9] is the number to aim at, while noting their outcome is broader.
3. **Add AUC-PR and plain-language hit rates.** AUC-ROC flatters rare events. Add AUC-PR (as Beger [15] and V-Dem [24] do) and a "share of onsets in the top 30 countries, and false alarms per hit" line in the style of the Early Warning Project [12].
4. **Benchmark against ViEWS's public forecasts.** Download their country-month forecasts, turn them into country-year probabilities of any state-based conflict, and score them on the same years and outcome as ours. If we later forecast fatalities, use their metrics: CRPS first, log score and mean interval score second [5]. Keep a "last 12 months repeated" baseline, since it led their challenge [6].
5. **Add a gradient-boosted variant, scored with the same rolling backtest.** The tree-versus-logit gains are real but smaller than first claimed [21, 22]. Nested tuning inside training years only.
6. **Import V-Dem ERT as a second outcome.** It comes from data we already use, and V-Dem's own forecasts give a published bar for regime breakdown (test AUC-ROC 0.84, AUC-PR 0.39 [24]).
7. **Settle licences before importing human and market forecasts.** Metaculus appears to need written permission for AI evaluation [18] (to confirm on its own site), and Polymarket's terms are unchecked. Until then, store them only as `scenario` items with links, not bulk tables.
8. **Unblock coups.** Coup onset is a well-studied target with published AUC around 0.77–0.80 [15]. It needs Powell & Thyne's licence settled, by asking the authors directly.

---

## Sources

All fetched 2026-10-19.

1. Goldstone, J. A., Bates, R. H., Epstein, D. L., Gurr, T. R., Lustik, M. B., Marshall, M. G., Ulfelder, J., & Woodward, M. (2010). "A Global Model for Forecasting Political Instability." *American Journal of Political Science* 54(1). PDF at Center for Systemic Peace: https://www.systemicpeace.org/vlibrary/PITFForecastingInstabilityAJPS2010.pdf
2. George Mason University, Schar School. "Political Instability Task Force." https://scip.gmu.edu/political-instability-task-force/
3. Hegre, H., Allansson, M., Basedau, M., Colaresi, M., Croicu, M., Fjelde, H., et al. (2019). "ViEWS: A political violence early-warning system." *Journal of Peace Research* 56(2). PDF: https://kops.uni-konstanz.de/server/api/core/bitstreams/197041e4-3a22-46b3-8ac4-1d0f6c75b916/content
4. Hegre, H., Bell, C., Colaresi, M., et al. (2021). "ViEWS 2020: Revising and evaluating the ViEWS political Violence Early-Warning System." *Journal of Peace Research* 58(3). PRIO: https://www.prio.org/publications/13335
5. Hegre, H., Vesco, P., Colaresi, M., et al. (2024 preprint; *Journal of Peace Research* 2025). "The 2023/24 VIEWS Prediction challenge: Predicting the number of fatalities in armed conflict, with uncertainty." arXiv:2407.11045v1: https://arxiv.org/html/2407.11045v1
6. PRIO (26 February 2025). "New Results from Prediction Challenge That Seeks to Improve Conflict Forecasting." https://www.prio.org/news/3602
7. VIEWS (Uppsala University and PRIO). Project home page. https://viewsforecasting.org/
8. Vesco, P., Hegre, H., Colaresi, M., et al. (2022). "United they stand: Findings from an escalation prediction competition." *International Interactions* 48(4). PRIO: https://www.prio.org/publications/13337
9. Mueller, H., & Rauh, C. (December 2020). "The Hard Problem of Prediction for Conflict Prevention." Barcelona GSE Working Paper 1244. https://bw.bse.eu/wp-content/uploads/2021/03/1244-file.pdf
10. Mueller, H., Rauh, C., & Seimon, B. "Introducing a Global Dataset on Conflict Forecasts and News Topics." Janeway Institute Working Paper 2402. https://www.janeway.econ.cam.ac.uk/node/705
11. Conflict Forecast. Home page. https://conflictforecast.org/
12. Early Warning Project, US Holocaust Memorial Museum. "Accuracy of Our Forecasting Model." https://earlywarningproject.ushmm.org/accuracy
13. Early Warning Project. "Reports & Downloads." https://earlywarningproject.ushmm.org/downloads
14. Powell, J. M., & Thyne, C. L. (2011). "Global instances of coups from 1950 to 2010: A new dataset." *Journal of Peace Research* 48(2). Record: https://ideas.repec.org/a/sae/joupea/v48y2011i2p249-259.html (data page https://www.uky.edu/~clthyn2/coup_data/home.htm returned 403)
15. Beger, A. (27 January 2017). "Taking stock of the risk of coups d’etat in 2017." Predictive Heuristics blog. https://blog.predictiveheuristics.com/2017/01/27/coup-forecasts-for-2017/
16. Powell, J. "Coup Forecasting." https://jonathanmpowell.com/coupcast-2
17. Tetlock, P. E., Mellers, B. A., Rohrbaugh, N., & Chen, E. (2014). "Forecasting Tournaments: Tools for Increasing Transparency and Improving the Quality of Debate." *Current Directions in Psychological Science* 23(4). https://faculty.wharton.upenn.edu/wp-content/uploads/2015/07/2014---forecasting-tournaments-tools-for-increasing-transparency-and-improving-debate.pdf
18. Alphascope (checked 6 October 2026). "Metaculus API" (secondary source on Metaculus terms). https://www.alphascope.app/blog/metaculus-api
19. Polymarket documentation. "Discover Markets." https://docs.polymarket.com/market-data/discover-markets.md
20. Muchlinski, D., Siroky, D., He, J., & Kocher, M. (2016). "Comparing Random Forest with Logistic Regression for Predicting Class-Imbalanced Civil War Onset Data." *Political Analysis* 24(1). Abstract: https://ideas.repec.org/a/cup/polals/v24y2016i1p87-103_9.html
21. Wang, Y. (2019). "Comparing Random Forest with Logistic Regression for Predicting Class-Imbalanced Civil War Onset Data: A Comment." *Political Analysis* 27(1). https://www.cambridge.org/core/product/B62CC1DA390C58435004D4C5D56DBF71/core-reader
22. Neunhoeffer, M., & Sternberg, S. (2019). "How Cross-Validation Can Go Wrong and What to Do About It." *Political Analysis* 27(1). https://www.cambridge.org/core/product/CA8C4B470E27C99892AB978CE0A3AE29/core-reader
23. Muchlinski, D., Siroky, D., He, J., & Kocher, M. (2019). "Seeing the Forest through the Trees." *Political Analysis* 27(1). https://www.cambridge.org/core/product/E717D15F10CC4F979EDC35C0CB9B55C1/core-reader
24. Morgan, R. K., Beger, A., & Glynn, A. (2019). "Varieties of Forecasts: Predicting Adverse Regime Transitions." V-Dem Working Paper 2019:89. https://www.v-dem.net/media/publications/v-dem_working_paper_2019_89.pdf
25. V-Dem Institute. "ERT" (GitHub repository README). https://github.com/vdeminstitute/ERT
26. Laeven, L., & Valencia, F. (2020). "Systemic Banking Crises Database II." *IMF Economic Review* 68. Abstract: https://ideas.repec.org/a/pal/imfecr/v68y2020i2d10.1057_s41308-020-00107-3.html
