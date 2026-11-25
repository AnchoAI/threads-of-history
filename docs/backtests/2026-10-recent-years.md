# Recent years: new conflicts 2015-2025, seen from the year before

<!-- Generated on 2026-10-19 by `python -m forecast.recent --out docs/backtests/2026-10-recent-years.md`. -->

**The closest test to "current events":** 2015–2025, the most recent years, which no model saw while being trained for them. The models are retrained each year on what was known before it.

**Summary:**
- **Ranking:** across 1,549 forecasts for countries at peace, `logit+all` ranks the 46 new conflicts best (AUC 0.887), ahead of `logit+unrest` (0.870), `logit` (0.858) and the Markov chain (0.692).
- **Recurrences are the easy part.** 32 of the 46 happened in countries with conflict sometime in the previous decade, and the models are very good at those.
- **Fresh conflicts are the hard part.** Of the 14 in countries with no conflict for 10 years, 7 fell in the riskiest quarter (about 4 by chance) and 4 in the top 10. Cameroon 2015, Kenya 2015, Benin 2022 and Indonesia 2018 were flagged. Burkina Faso 2018, Togo 2022, Haiti 2024 and Cambodia 2025 were not.
- **The probabilities are low,** typically 2–20% for countries that then went to war, because even risky countries usually stay at peace in a given year. Read them as "several times the base rate", not as predictions that something will happen.

**Caveat:** the inputs are today's revised data (V-Dem, Maddison, World Bank), so this is still kinder than a live forecast.

Each year the models were trained on what was known before it, then forecast, for every country at peace the year before, the chance of armed conflict or civil war that year. Conflicts are UCDP state-based conflicts on the country's territory (25 or more battle deaths), so a small insurgency counts as much as a large war.

## Scores over the period

| model | forecasts | new conflicts | Brier | AUC |
|---|---|---|---|---|
| logit+all | 1549 | 46 | 0.0245 | 0.887 |
| logit+unrest | 1549 | 46 | 0.0248 | 0.870 |
| logit | 1549 | 46 | 0.0251 | 0.858 |
| markov | 1549 | 46 | 0.0282 | 0.692 |

## Every new conflict, ranked by `logit+all`

46 new conflicts. 26 were in that year's top 10 of 145-odd peaceful countries, and 37 in the riskiest quarter (about 12 expected by chance).

Most of these are **recurrences**: the country had conflict at some point in the 10 years before. Those are easier. Of the 14 **fresh** conflicts (none in the previous 10 years), 4 were in the top 10 and 7 in the riskiest quarter (about 4 expected by chance).

Some entries reflect how UCDP locates interstate conflicts: it lists the countries of the governments involved, so for example the US and UK appear in 2024 because of their strikes on the Houthis, and Russia in 2022 because of its war with Ukraine.

| Year | Country | What happened | Kind | Probability | Rank among countries at peace |
|---|---|---|---|---|---|
| 2015 | TUR | armed-conflict | recurrence | 56% | 1 of 145 |
| 2015 | CMR | armed-conflict | **fresh** | 17% | 3 of 145 |
| 2015 | TCD | armed-conflict | recurrence | 15% | 4 of 145 |
| 2015 | KEN | armed-conflict | **fresh** | 11% | 6 of 145 |
| 2015 | NER | armed-conflict | recurrence | 4% | 25 of 145 |
| 2016 | COD | armed-conflict | recurrence | 50% | 1 of 143 |
| 2016 | IRN | armed-conflict | recurrence | 12% | 3 of 143 |
| 2016 | BGD | armed-conflict | recurrence | 9% | 6 of 143 |
| 2016 | MOZ | armed-conflict | recurrence | 6% | 11 of 143 |
| 2016 | RWA | armed-conflict | recurrence | 6% | 12 of 143 |
| 2016 | AGO | armed-conflict | recurrence | 5% | 17 of 143 |
| 2016 | JOR | armed-conflict | **fresh** | 3% | 37 of 143 |
| 2016 | COG | armed-conflict | **fresh** | 3% | 44 of 143 |
| 2016 | ERI | armed-conflict | recurrence | 2% | 58 of 143 |
| 2017 | CAF | armed-conflict | recurrence | 72% | 1 of 138 |
| 2017 | TCD | armed-conflict | recurrence | 24% | 2 of 138 |
| 2017 | LBN | armed-conflict | recurrence | 17% | 4 of 138 |
| 2018 | ISR | armed-conflict | recurrence | 23% | 2 of 142 |
| 2018 | MOZ | armed-conflict | recurrence | 12% | 4 of 142 |
| 2018 | IDN | armed-conflict | **fresh** | 11% | 7 of 142 |
| 2018 | TJK | armed-conflict | recurrence | 4% | 27 of 142 |
| 2018 | BFA | armed-conflict | **fresh** | 3% | 36 of 142 |
| 2019 | ETH | armed-conflict | recurrence | 70% | 1 of 143 |
| 2019 | AGO | armed-conflict | recurrence | 24% | 2 of 143 |
| 2019 | RWA | armed-conflict | recurrence | 16% | 6 of 143 |
| 2019 | BDI | armed-conflict | recurrence | 9% | 11 of 143 |
| 2019 | USA | armed-conflict | recurrence | 7% | 13 of 143 |
| 2020 | DZA | armed-conflict | recurrence | 73% | 1 of 140 |
| 2020 | SDN | armed-conflict | recurrence | 70% | 2 of 140 |
| 2020 | AZE | civil-war | recurrence | 13% | 5 of 140 |
| 2020 | TZA | armed-conflict | **fresh** | 7% | 12 of 140 |
| 2020 | CHN | armed-conflict | **fresh** | 3% | 41 of 140 |
| 2021 | TJK | armed-conflict | recurrence | 6% | 9 of 137 |
| 2021 | KGZ | armed-conflict | **fresh** | 3% | 26 of 137 |
| 2022 | RUS | armed-conflict | recurrence | 23% | 1 of 142 |
| 2022 | UGA | armed-conflict | recurrence | 22% | 2 of 142 |
| 2022 | BEN | armed-conflict | **fresh** | 16% | 5 of 142 |
| 2022 | AGO | armed-conflict | recurrence | 11% | 10 of 142 |
| 2022 | RWA | armed-conflict | recurrence | 5% | 17 of 142 |
| 2022 | TGO | armed-conflict | **fresh** | 2% | 60 of 142 |
| 2024 | AGO | armed-conflict | recurrence | 20% | 7 of 142 |
| 2024 | HTI | armed-conflict | **fresh** | 6% | 26 of 142 |
| 2024 | USA | armed-conflict | recurrence | 2% | 82 of 142 |
| 2024 | GBR | armed-conflict | **fresh** | 0% | 112 of 142 |
| 2025 | SSD | armed-conflict | recurrence | 30% | 3 of 140 |
| 2025 | KHM | armed-conflict | **fresh** | 2% | 74 of 140 |

## False-alarm check: each year's ten highest-ranked countries at peace

**Bold** marks those where conflict did break out.

- **2015:** **TUR 56%**, IRN 27%, **CMR 17%**, **TCD 15%**, BFA 13%, **KEN 11%**, VEN 10%, LKA 8%, AGO 7%, HKG 7%
- **2016:** **COD 50%**, ISR 50%, **IRN 12%**, VEN 10%, GIN 10%, **BGD 9%**, HND 9%, CIV 6%, MRT 6%, MYS 6%
- **2017:** **CAF 72%**, **TCD 24%**, ISR 18%, **LBN 17%**, BDI 12%, VEN 11%, ARM 11%, MYS 6%, MRT 6%, CIV 6%
- **2018:** ETH 65%, **ISR 23%**, VEN 12%, **MOZ 12%**, BDI 12%, MYS 12%, **IDN 11%**, RWA 9%, HTI 9%, JOR 8%
- **2019:** **ETH 70%**, **AGO 24%**, UGA 19%, BGD 18%, LBN 18%, **RWA 16%**, AZE 15%, HTI 14%, VEN 10%, JOR 10%
- **2020:** **DZA 73%**, **SDN 70%**, UGA 24%, LBN 23%, **AZE 13%**, HTI 11%, HND 10%, BGD 9%, JOR 9%, BOL 8%
- **2021:** CIV 22%, LBN 15%, UGA 14%, BGD 11%, HTI 8%, GIN 7%, BEN 7%, JOR 7%, **TJK 6%**, MAR 6%
- **2022:** **RUS 23%**, **UGA 22%**, LBY 20%, DZA 18%, **BEN 16%**, SLV 13%, TZA 13%, TUN 13%, LBN 12%, **AGO 11%**
- **2023:** SSD 58%, DZA 20%, LBY 18%, BGD 18%, LBN 11%, TUN 10%, POL 10%, TZA 9%, GHA 8%, PNG 7%
- **2024:** EGY 51%, LBN 47%, TUN 31%, LBY 27%, UGA 26%, BGD 21%, **AGO 20%**, SSD 19%, GEO 17%, DZA 15%
- **2025:** TCD 64%, LBN 49%, **SSD 30%**, MEX 26%, EGY 24%, GHA 22%, ECU 18%, GTM 17%, LBY 16%, BGD 14%
