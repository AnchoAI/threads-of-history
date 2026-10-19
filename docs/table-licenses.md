# Licences of the imported tables

The tables in `data/tables/` come from external datasets, and each keeps its source's licence. They are not covered by whatever licence the rest of this project's data ends up under. Full details, citations and quoted licence text are in `data/datasets/`.

| Tables | Dataset | Licence | Credit |
|---|---|---|---|
| `vdem-*.csv` | V-Dem Country-Year v16 | CC BY-SA 4.0 (share-alike: anything built from these tables and shared must use the same licence) | Coppedge et al. 2026, "V-Dem Country-Year Dataset v16", https://doi.org/10.23696/vdemds26 |
| `ucdp-*.csv` | UCDP/PRIO Armed Conflict Dataset 26.1 and UCDP Georeferenced Event Dataset 26.1 (`ucdp-ged-*`) | CC BY 4.0 | Cite the publications listed in `data/datasets/ucdp-prio-armed-conflict.yaml` and `ucdp-ged.yaml` |
| `maddison-*.csv` | Maddison Project Database 2023 | CC BY 4.0 | Bolt and van Zanden (2024); graphs must also credit the per-country sources listed in the database (see `data/datasets/maddison-project.yaml`) |
| `wdi-*.csv` | World Bank World Development Indicators | CC BY 4.0, plus World Bank terms | "The World Bank: World Development Indicators: <indicator source>" must appear with any use |

`forecast/data/neighbours.json` (land borders) is derived from Natural Earth, which is public domain.
