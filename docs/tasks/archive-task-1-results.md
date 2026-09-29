# Task 1: archive run

Added 145 archive URLs across 145 existing records (40 actors, 48 events, 57 links). New items: 0. New links: 0. New source records: 0. Links dropped or downgraded: 0. Review statuses changed: 0.

## Task 0 access

Wikidata, its SPARQL endpoint, Wikipedia, Wayback (including `/save/`), UCDP and V-Dem opened successfully. The replacement Powell page and CSV, Groningen release page, and Maddison Dataverse page and Excel download also returned HTTP 200. TLS verification remained enabled. Python's default CA store failed for Groningen and the Maddison DOI; using the certifi CA bundle bundled with pip resolved both. No server-chain diagnosis was needed.

- Opened [Powell dataset page](https://jonathanmpowell.com/coups/): title excerpt, "Global Instances of Coups, 1950". Opened its [linked CSV](https://jonathanmpowell.com/wp-content/uploads/2026/08/pt_20260829.csv).
- Opened [Groningen release page](https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023) and [Maddison DOI](https://doi.org/10.34894/INZBF2), which resolved to Dataverse: "Maddison Project Database 2023". Opened the [Excel download](https://dataverse.nl/api/access/datafile/421302).
- The old Powell registry URL still returned 404. Dataset registry edits and licence verification remain Task 3a.

## Run and limitations

Ran `python tools/archive.py --dry-run`, then `python tools/archive.py --ca-bundle <trusted-certifi-bundle>`. The dry run found 209 source entries without archives. Successful URLs came from Wayback API responses; no snapshot URL was guessed. The API's available/status metadata was checked; replay content and historical claims were not independently verified.

The live run was interrupted after persistent HTTP 429 responses. An offline pass then applied confirmed cached results to remaining records.

```text
Sources missing archives: 125; added: 61; failures: 64
```

The offline run returned a nonzero exit status because some sources could not be archived. Where the availability response contained no snapshot, Save Page Now was attempted; HTTP 401 responses prevented those new captures. Failed entries retain their original YAML. All existing historical claims and quotes remain for Task 2; no review status was raised. The script edits only archive_url, so failure details are recorded here rather than changing review.notes in this task.

## Sources still missing archives

- [https://en.wikipedia.org/wiki/1973_oil_crisis](https://en.wikipedia.org/wiki/1973_oil_crisis) — `Not attempted after service throttling; no cached snapshot`. Files: `data/events/yom-kippur-war-and-oil-embargo-1973.yaml`, `data/links/six-day-war-1967--led_to--yom-kippur-war-and-oil-embargo-1973.yaml`.
- [https://en.wikipedia.org/wiki/2022_Nord_Stream_pipeline_sabotage](https://en.wikipedia.org/wiki/2022_Nord_Stream_pipeline_sabotage) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/hersh-nord-stream-report-2023.yaml`, `data/events/nord-stream-explosions-2022.yaml`, `data/events/nord-stream-investigations-2024.yaml`, `data/links/hersh-nord-stream-report-2023--revealed--nord-stream-explosions-2022.yaml`, `data/links/nord-stream-investigations-2024--revealed--nord-stream-explosions-2022.yaml`, `data/links/russian-invasion-of-ukraine-2022--led_to--nord-stream-explosions-2022.yaml`.
- [https://en.wikipedia.org/wiki/9/11_Commission](https://en.wikipedia.org/wiki/9/11_Commission) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/9-11-commission.yaml`.
- [https://en.wikipedia.org/wiki/9/11_Commission_Report](https://en.wikipedia.org/wiki/9/11_Commission_Report) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/9-11-commission-report-2004.yaml`, `data/links/9-11-commission-report-2004--revealed--september-11-attacks-2001.yaml`.
- [https://en.wikipedia.org/wiki/Aftermath_of_World_War_II](https://en.wikipedia.org/wiki/Aftermath_of_World_War_II) — `Not attempted after service throttling; no cached snapshot`. Files: `data/events/wwii-ends-in-europe-1945.yaml`.
- [https://en.wikipedia.org/wiki/Al-Qaeda](https://en.wikipedia.org/wiki/Al-Qaeda) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/al-qaeda.yaml`, `data/events/al-qaeda-founded-1988.yaml`, `data/links/muslim-brotherhood-founded-1928--led_to--al-qaeda-founded-1988.yaml`, `data/links/soviet-invasion-of-afghanistan-1979--led_to--al-qaeda-founded-1988.yaml`.
- [https://en.wikipedia.org/wiki/Atomic_bombings_of_Hiroshima_and_Nagasaki](https://en.wikipedia.org/wiki/Atomic_bombings_of_Hiroshima_and_Nagasaki) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/atomic-bombings-of-hiroshima-and-nagasaki-1945.yaml`.
- [https://en.wikipedia.org/wiki/Bay_of_Pigs_Invasion](https://en.wikipedia.org/wiki/Bay_of_Pigs_Invasion) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/bay-of-pigs-invasion-1961.yaml`, `data/links/cuban-revolution-1959--led_to--bay-of-pigs-invasion-1961.yaml`.
- [https://en.wikipedia.org/wiki/Central_Intelligence_Agency](https://en.wikipedia.org/wiki/Central_Intelligence_Agency) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/cia.yaml`.
- [https://en.wikipedia.org/wiki/Cuban_Revolution](https://en.wikipedia.org/wiki/Cuban_Revolution) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/cuban-revolution-1959.yaml`.
- [https://en.wikipedia.org/wiki/Dissolution_of_the_Soviet_Union](https://en.wikipedia.org/wiki/Dissolution_of_the_Soviet_Union) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/dissolution-of-the-soviet-union-1991.yaml`, `data/links/soviet-invasion-of-afghanistan-1979--led_to--dissolution-of-the-soviet-union-1991.yaml`.
- [https://en.wikipedia.org/wiki/Egypt](https://en.wikipedia.org/wiki/Egypt) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/egypt.yaml`.
- [https://en.wikipedia.org/wiki/France](https://en.wikipedia.org/wiki/France) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/france.yaml`.
- [https://en.wikipedia.org/wiki/Gamal_Abdel_Nasser](https://en.wikipedia.org/wiki/Gamal_Abdel_Nasser) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/gamal-abdel-nasser.yaml`.
- [https://en.wikipedia.org/wiki/Gulf_War](https://en.wikipedia.org/wiki/Gulf_War) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/gulf-war-1990.yaml`.
- [https://en.wikipedia.org/wiki/Harry_S._Truman](https://en.wikipedia.org/wiki/Harry_S._Truman) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/harry-truman.yaml`.
- [https://en.wikipedia.org/wiki/Hassan_al-Banna](https://en.wikipedia.org/wiki/Hassan_al-Banna) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/hassan-al-banna.yaml`.
- [https://en.wikipedia.org/wiki/India](https://en.wikipedia.org/wiki/India) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/india.yaml`.
- [https://en.wikipedia.org/wiki/Iraq_War](https://en.wikipedia.org/wiki/Iraq_War) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/invasion-of-iraq-2003.yaml`, `data/links/september-11-attacks-2001--led_to--invasion-of-iraq-2003.yaml`.
- [https://en.wikipedia.org/wiki/Joint_Inquiry_into_Intelligence_Community_Activities_before_and_after_the_Terrorist_Attacks_of_September_11,_2001](https://en.wikipedia.org/wiki/Joint_Inquiry_into_Intelligence_Community_Activities_before_and_after_the_Terrorist_Attacks_of_September_11,_2001) — `Not attempted after service throttling; no cached snapshot`. Files: `data/events/twenty-eight-pages-declassified-2016.yaml`, `data/links/twenty-eight-pages-declassified-2016--revealed--september-11-attacks-2001.yaml`.
- [https://en.wikipedia.org/wiki/Jyllands-Posten_Muhammad_cartoons_controversy](https://en.wikipedia.org/wiki/Jyllands-Posten_Muhammad_cartoons_controversy) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/jyllands-posten-cartoons-2005.yaml`, `data/links/rushdie-fatwa-1989--echo--jyllands-posten-cartoons-2005.yaml`.
- [https://en.wikipedia.org/wiki/Lee_Harvey_Oswald](https://en.wikipedia.org/wiki/Lee_Harvey_Oswald) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/lee-harvey-oswald.yaml`.
- [https://en.wikipedia.org/wiki/NATO](https://en.wikipedia.org/wiki/NATO) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/nato.yaml`.
- [https://en.wikipedia.org/wiki/November_2015_Paris_attacks](https://en.wikipedia.org/wiki/November_2015_Paris_attacks) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/paris-attacks-2015.yaml`, `data/links/european-migrant-crisis-2015--led_to--paris-attacks-2015.yaml`, `data/links/isis-declares-caliphate-2014--led_to--paris-attacks-2015.yaml`.
- [https://en.wikipedia.org/wiki/Osama_bin_Laden](https://en.wikipedia.org/wiki/Osama_bin_Laden) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/osama-bin-laden.yaml`.
- [https://en.wikipedia.org/wiki/Partial_Nuclear_Test_Ban_Treaty](https://en.wikipedia.org/wiki/Partial_Nuclear_Test_Ban_Treaty) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/limited-test-ban-treaty-1963.yaml`, `data/links/cuban-missile-crisis-1962--led_to--limited-test-ban-treaty-1963.yaml`.
- [https://en.wikipedia.org/wiki/President_John_F._Kennedy_Assassination_Records_Collection_Act_of_1992](https://en.wikipedia.org/wiki/President_John_F._Kennedy_Assassination_Records_Collection_Act_of_1992) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/events/jfk-files-released-2017.yaml`, `data/events/jfk-files-released-2025.yaml`, `data/events/jfk-records-act-1992.yaml`, `data/links/jfk-files-released-2017--led_to--jfk-files-released-2025.yaml`, `data/links/jfk-files-released-2017--revealed--kennedy-assassinated-1963.yaml`, `data/links/jfk-files-released-2025--revealed--kennedy-assassinated-1963.yaml`, `data/links/jfk-records-act-1992--led_to--jfk-files-released-2017.yaml`.
- [https://en.wikipedia.org/wiki/Ronald_Reagan](https://en.wikipedia.org/wiki/Ronald_Reagan) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/ronald-reagan.yaml`.
- [https://en.wikipedia.org/wiki/Soviet%E2%80%93Afghan_War](https://en.wikipedia.org/wiki/Soviet%E2%80%93Afghan_War) — `HTTP Error 429: Too Many Requests`. Files: `data/events/soviet-invasion-of-afghanistan-1979.yaml`.
- [https://en.wikipedia.org/wiki/Soviet_Union](https://en.wikipedia.org/wiki/Soviet_Union) — `HTTP Error 401: UNAUTHORIZED`. Files: `data/actors/soviet-union.yaml`.
- [https://en.wikipedia.org/wiki/Suez_Crisis](https://en.wikipedia.org/wiki/Suez_Crisis) — `HTTP Error 429: Too Many Requests`. Files: `data/events/suez-crisis-1956.yaml`, `data/links/israel-founded-1948--led_to--suez-crisis-1956.yaml`, `data/links/wwii-ends-in-europe-1945--led_to--suez-crisis-1956.yaml`.
- [https://en.wikipedia.org/wiki/Sykes%E2%80%93Picot_Agreement](https://en.wikipedia.org/wiki/Sykes%E2%80%93Picot_Agreement) — `Not attempted after service throttling; no cached snapshot`. Files: `data/events/sykes-picot-agreement-1916.yaml`.
- [https://en.wikipedia.org/wiki/Syrian_civil_war](https://en.wikipedia.org/wiki/Syrian_civil_war) — `Not attempted after service throttling; no cached snapshot`. Files: `data/events/syrian-civil-war-2011.yaml`, `data/links/arab-spring-2011--led_to--syrian-civil-war-2011.yaml`.
- [https://en.wikipedia.org/wiki/War_in_Afghanistan_(2001%E2%80%932021)](https://en.wikipedia.org/wiki/War_in_Afghanistan_(2001%E2%80%932021)) — `Not attempted after service throttling; no cached snapshot`. Files: `data/events/us-led-war-in-afghanistan-2001.yaml`, `data/links/september-11-attacks-2001--led_to--us-led-war-in-afghanistan-2001.yaml`.
- [https://en.wikipedia.org/wiki/Windrush_generation](https://en.wikipedia.org/wiki/Windrush_generation) — `Not attempted after service throttling; no cached snapshot`. Files: `data/events/windrush-arrives-1948.yaml`, `data/links/wwii-ends-in-europe-1945--led_to--windrush-arrives-1948.yaml`.

## Validation

The validator reports zero errors and 135 pre-existing warnings, identical to the base branch (including warnings in changed data files). These concern existing metadata and unfinished importers; fixing them would cross into Tasks 2 and 3. No new validation warnings were introduced. Data comparison confirms only archive_url fields changed; formatting checks confirm the original content is recovered by removing those insertions.
