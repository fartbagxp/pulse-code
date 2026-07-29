# Pulse

[![PyPI](https://img.shields.io/pypi/v/pulse-code?style=for-the-badge)](https://pypi.org/project/pulse-code/)
[![Python versions](https://img.shields.io/badge/python-3.14%2B-blue?style=for-the-badge)](https://pypi.org/project/pulse-code/)
[![Publish](https://img.shields.io/github/actions/workflow/status/fartbagxp/pulse-code/publish.yml?style=for-the-badge&label=publish)](https://github.com/fartbagxp/pulse-code/actions/workflows/publish.yml)
[![Pages](https://img.shields.io/github/actions/workflow/status/fartbagxp/pulse-code/pages.yml?style=for-the-badge&label=pages)](https://fartbagxp.github.io/pulse-code/)
[![License](https://img.shields.io/badge/license-CC0--1.0-blue?style=for-the-badge)](LICENSE)

CDC public health data query CLI. Explore datasets, run bundled queries, and use Claude to build and refine custom XML queries — across CDC WONDER, NCI SEER cancer statistics, CDC Open Data, WISQARS injury data, ATSDR GRASP disease surveillance, NSSP ED visits, and NIS vaccination surveys.

## What is this?

![pulse-code demo](docs/demo/pulse-demo.gif)

[CDC WONDER](https://wonder.cdc.gov/) (Wide-ranging ONline Data for Epidemiologic Research) is the government's primary interface for public health statistics: drug overdose deaths, maternal mortality, birth rates, COVID deaths by race, suicide trends, vaccine adverse events, and much more. Its XML API is powerful but opaque.

`pulse` makes it usable:

- **Explore** all datasets with clear descriptions of what they cover and when
- **Search** by topic to find the right dataset or a working example query
- **Run** bundled, validated XML queries directly against the CDC API
- **Build** new queries from natural language using Claude
- **Refine** existing queries with conversational feedback

Beyond WONDER, `pulse` gives direct access to six more live CDC/NCI/ATSDR sources — no LLM required for those, just a dataset lookup and a query: `seer`, `cdc-open`, `wisqars`, `grasp`, `nssp`, and `nis`.

## Setup

```bash
# From PyPI (requires Python 3.14+)
pip install pulse-code

# Or from source
uv sync

# For build/query/refine/compare/chat commands, set your Anthropic API key:
export ANTHROPIC_API_KEY=sk-ant-...
# or put it in a .env file:
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### LLM provider

`pulse` defaults to Anthropic Claude but can also run against an Azure
OpenAI Foundry deployment (e.g. GPT-5.4). Select the provider with
`LLM_PROVIDER` (defaults to `anthropic`):

```bash
# Anthropic (default), needs ANTHROPIC_API_KEY as above

# Azure OpenAI Foundry
export LLM_PROVIDER=azure_openai
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
export AZURE_OPENAI_DEPLOYMENT=<your-gpt-5.4-deployment-name>
export AZURE_OPENAI_API_VERSION=<api-version-your-resource-supports>
```

All four `AZURE_OPENAI_*` variables are required when `LLM_PROVIDER=azure_openai`;
`pulse` will tell you which ones are missing. These can also go in a `.env`
file alongside `ANTHROPIC_API_KEY`.

If the LLM endpoint isn't directly reachable (e.g. an Azure OpenAI resource
with public network access disabled, requiring a private endpoint), bridge
the connection through a proxy with `LLM_HTTP_PROXY`. Applies to both
providers, and supports `http://`, `https://`, `socks5://`, and `socks5h://`
(DNS resolved through the proxy):

```bash
export LLM_HTTP_PROXY=socks5h://user:pass@host:port
```

## Commands

### `pulse datasets` — what's available

```bash
pulse datasets                    # all datasets
pulse datasets --topic Mortality  # filter by topic
pulse datasets --json             # JSON output
```

Shows all 26+ CDC WONDER datasets with: topic, year range, what the data covers, number of bundled example queries, and whether age-adjusted rates are available.

**Topics:** Mortality · Infant Mortality · Natality · Environment · Vaccine Safety · Infectious Disease

### `pulse info <ID>` — deep dive on a dataset

```bash
pulse info D176    # Provisional Mortality (2018–present)
pulse info D66     # Natality / birth data
pulse info D8      # VAERS vaccine adverse events
```

Shows: subject description, available measures, key grouping dimensions, and all bundled example queries for that dataset.

### `pulse search "<topic>"` — find what you need

```bash
pulse search "opioid overdose deaths by state"
pulse search "maternal mortality by race"
pulse search "birth rates 2010 to 2020"
pulse search "tick-borne disease cases" --queries   # queries only
pulse search "recent COVID deaths" --datasets       # datasets only
```

### `pulse list-queries` — all bundled example queries

```bash
pulse list-queries
pulse list-queries --dataset D176   # filter by dataset
```

23 working XML queries covering: drug/opioid/fentanyl deaths, maternal mortality, births, COVID deaths by race, suicide, tick-borne diseases, racial mortality gap, infant mortality, heart disease vs. cancer, and more.

### `pulse seer` — NCI SEER cancer statistics

```bash
pulse seer sites --search breast              # look up a cancer site code
pulse seer mortality --site 55 --sex female -f csv
pulse seer mortality --site 47 --compare-by race -f csv
pulse seer incidence --site 55 --stage 104 -f csv
pulse seer by-age --site 1 -f csv
pulse seer compare-sites 55 47 66 -f csv       # breast vs. lung vs. melanoma
```

Cancer incidence and U.S. mortality rates/counts by site, sex, race, and age group, back to 1975 — calls the same unauthenticated JSON endpoints [SEER*Explorer](https://seer.cancer.gov/statistics-network/explorer/) itself uses. No API key needed.

### `pulse cdc-open` — CDC Open Data (data.cdc.gov)

```bash
pulse cdc-open list                            # 60+ datasets: mortality, vaccination, wastewater, NNDSS, HAI, and more
pulse cdc-open list --search wastewater
pulse cdc-open query leading_death --where "year='2015'" -f csv
pulse cdc-open query bi63-dtpu --where "state='California'" --limit 500 -f json
```

Raw [SODA](https://dev.socrata.com/) queries (`--where`, `--select`, `--group`, `--order`) against any of the registered Socrata datasets, by registry key or by Socrata ID directly. No API key needed (set `CDC_DATA_APP_TOKEN` for a higher rate limit).

### `pulse wisqars` — WISQARS injury & violence data

```bash
pulse wisqars list
pulse wisqars mortality --intent Suicide --mechanism Firearm -f csv       # 1999-2016
pulse wisqars national --intent FA_Deaths --type year -f csv             # 2019-present
pulse wisqars state --intent Drug_OD --year 2023 -f table
pulse wisqars county --state Texas --intent FA_Deaths --year 2023
pulse wisqars tract --state Texas --intent All_Homicide --year 2022      # census-tract granularity
pulse wisqars query t6u2-f84c --where "intent='Drug_OD' AND type='year'"
```

Fatal firearm/suicide/homicide/drug-overdose data from [WISQARS](https://wisqars.cdc.gov/) at national, state, county, and census-tract granularity, backed by data.cdc.gov Socrata datasets (same client as `cdc-open`). No API key needed.

### `pulse grasp` — ATSDR GRASP disease surveillance

```bash
pulse grasp list
pulse grasp hantavirus cases --outcome Dead -f table              # pre-1993-present
pulse grasp hantavirus by-year -f table
pulse grasp hantavirus by-state -f table
pulse grasp fluview ili-data --region nat --region ca --region tx --epiweeks 202001-202026
pulse grasp fluview ili-by-region --epiweeks 201940-202020 -f table
pulse grasp fluview clinical-data --region nat --epiweeks 202001-202026
pulse grasp flusurv data --location CA --location OH --epiweeks 202001-202020 -f csv
pulse grasp flusurv by-season --location CA -f table
pulse grasp flusurv by-location --season 2019-20 -f table
```

Hantavirus case data, FluView ILINet influenza-like-illness activity, WHO/NREVSS clinical lab flu positivity, and FluSurv-NET hospitalization rates — sourced from [gis.cdc.gov/grasp](https://gis.cdc.gov/grasp/) and the CMU Delphi Epidata API. No API key needed. Note: repeatable options like `--region`/`--location` take one value per flag (`--region nat --region ca`), unlike `health`'s argparse CLI which accepts space-separated lists after a single flag.

### `pulse nssp` — emergency department visit surveillance

```bash
pulse nssp query covid --geo-type state --geo-value ca -f csv
pulse nssp query influenza --geo-type nation --geo-value us
pulse nssp national --start 202401 -f csv                # all 4 pathogens, national
pulse nssp hhs rsv --region 4 -f table
```

Weekly % of ED visits attributed to COVID/flu/RSV from the [National Syndromic Surveillance Program](https://www.cdc.gov/nssp/), via the CMU Delphi Epidata API. Time values use epiweek format (`YYYYWW`, e.g. `202518` = week 18 of 2025). No API key needed.

### `pulse nis` — National Immunization Survey (vaccination coverage)

```bash
pulse nis list child                                       # available years, 2011-2022
pulse nis stream child 2022 --limit 10 -f json              # raw respondent microdata
pulse nis rates child 2022 -f table                         # state-level UTD rates
pulse nis rates teen 2022 --vaccines P_UTDHPV13 -f csv
pulse nis national child 2022                                # national UTD summary
```

Childhood (19–35mo) and teen (13–17yr) vaccination coverage from CDC's annual random-digit-dial survey. Files are large fixed-width `.dat` files (50–200MB) streamed directly — nothing is written to disk. **Known issue:** CDC has restructured its NIS file hosting since this registry's URLs were last verified (some years now live under `www.cdc.gov/nis/media/files/...` or `ftp.cdc.gov/pub/Vaccines_NIS/` instead of the legacy `ftp.cdc.gov/.../nis/NISPUF{YY}-formats.sas` path baked into `nis_catalog.py`), so live `stream`/`rates`/`national` calls currently 404 for at least the 2015+ years — the same pre-existing gap affects `health`'s own `nis` module. The CLI plumbing and DAT-streaming parser are unit-tested and correct; only the hardcoded per-year URLs need refreshing against CDC's current hosting.

### `pulse run <query>` — execute a query

```bash
# Run a bundled query by filename (no path needed)
pulse run drug-deaths-by-year-2018-2024-req.xml

# Output formats
pulse run opioid-overdose-deaths-2018-2024-req.xml -f csv
pulse run mortality-by-year-cause-2021-2024-req.xml -f json
pulse run births-by-year-2007-2024-req.xml -f table -o births.csv

# Run your own query file
pulse run /path/to/my-query.xml
```

Hits the live CDC WONDER API. No login required; CDC requires a ~2-minute cooldown between queries.

### `pulse build "<description>"` — build a query with Claude

```bash
# Requires ANTHROPIC_API_KEY
pulse build "drug overdose deaths by state and year 2018-2023"
pulse build "maternal mortality by race, 2018-2023" -o maternal-race.xml
pulse build "birth rates by age of mother 2010 to 2024" --no-suggest
```

Suggests closest existing queries first, then calls Claude to build a new XML query. The LLM selects the right dataset and generates overrides merged onto a validated base template.

### `pulse query "<description>"` — build and run in one step

```bash
pulse query "fentanyl deaths by state 2020-2024" -f csv
pulse query "infant mortality by race 2018-2023" --save-xml infant-race.xml
```

### `pulse refine <file> "<feedback>"` — iterate on a query

```bash
pulse refine opioid-overdose-deaths-2018-2024-req.xml "break it down by state"
pulse refine drug-deaths-by-year-2018-2024-req.xml "add sex breakdown" -o drug-sex.xml
pulse refine drug-deaths-by-year-2018-2024-req.xml "show monthly not yearly" --run -f csv
```

## Testing

```bash
uv run pytest                  # unit tests only, fast, no network (default)
uv run pytest -m integration   # + integration tests (see below)
```

Unit tests cover catalog/matcher lookups, XML template merging (including
the CDC WONDER radio-button-trap regression), AAR constraints, provider
selection, and the offline-network-free CLI commands.

Integration tests (`tests/integration/`) are excluded by default and split
into two kinds:

- **`test_socks_proxy_integration.py`**: always runs. Spins up a local
  SOCKS5 relay and a local mock LLM HTTP server, so it actually exercises
  `LLM_HTTP_PROXY` end-to-end (real SOCKS handshake, real HTTP
  request/response) without needing real Azure/Anthropic credentials.
- **`test_llm_provider_live.py`**: hits whatever `ANTHROPIC_API_KEY` /
  `LLM_PROVIDER=azure_openai` + `AZURE_OPENAI_*` / `LLM_HTTP_PROXY` you
  actually have configured. Skips if credentials aren't set; also skips
  (rather than fails) if the provider is reachable but blocked at the
  network layer (e.g. an Azure OpenAI resource with public access disabled
  and no working proxy). That's an environment gap, not a code defect.

## Bundled Datasets (with base templates)

| ID          | Subject                                                       | Years        |
| ----------- | ------------------------------------------------------------- | ------------ |
| D176        | Provisional mortality: opioids, COVID, suicide, heart disease | 2018–present |
| D157        | Final mortality, single race (MCD+UCD)                        | 2018–2023    |
| D158        | Underlying cause of death, single race: maternal mortality    | 2018–2023    |
| D77         | Multiple cause of death: drug deaths (historical)             | 1999–2020    |
| D76         | Underlying cause of death: suicide, cancer (historical)       | 1999–2020    |
| D141        | MCD with US-Mexico border regions                             | 1999–2020    |
| D140        | Compressed mortality ICD-10                                   | 1999–2016    |
| D16         | Compressed mortality ICD-9                                    | 1979–1998    |
| D74         | Compressed mortality ICD-8                                    | 1968–1978    |
| D69         | Linked birth/infant death records                             | 2007–2023    |
| D159        | Linked birth/infant death, expanded race                      | 2017–2023    |
| D31/D18/D23 | Linked birth/infant death (historical)                        | 1995–2006    |
| D66         | Natality: birth rates, birth outcomes                         | 2007–2024    |
| D149        | Natality, expanded race detail                                | 2016–2024    |
| D192        | Provisional natality (monthly)                                | 2023–present |
| D27/D10     | Natality (historical)                                         | 1995–2006    |
| D8          | VAERS vaccine adverse events                                  | 1990–present |
| D104        | Heat wave days by county                                      | 1981–2010    |
| D60/D80/D81 | NLDAS temperature, sunlight, precipitation                    | 1979–2011    |
| D73         | PM2.5 fine particulate matter                                 | 2003–2011    |
| D61         | MODIS land surface temperature                                | 2003–2008    |

## Public Health Questions You Can Answer

- How did opioid overdose deaths trend from 1999 to today, broken down by drug type?
- What is the racial gap in COVID-19 mortality?
- How does maternal mortality differ by race and state?
- Which states have the highest suicide rates by sex?
- How have birth rates changed by age of mother since 1995?
- Are tick-borne disease cases increasing?
- How do PM2.5 air quality levels correlate with where people live?
- What are the most common adverse events reported after COVID vaccines?

## Releasing

Releases are cut by pushing a tag. `publish.yml` (single workflow, one run
per tag) handles the rest as three sequential jobs:

1. Bump `version` in `pyproject.toml`, commit it.
2. `git tag vX.Y.Z && git push origin vX.Y.Z`
3. **`build`** builds the sdist/wheel, failing fast if the tag doesn't match
   `pyproject.toml`'s version.
4. **`release`** (needs `build`) creates the GitHub Release with the built
   artifacts attached, the source of truth for what shipped.
5. **`publish`** (needs `release`) publishes those same artifacts to PyPI
   (`pulse-code`) via trusted publishing (OIDC) against the `prod`
   environment, with no API tokens stored in the repo.

The `needs:` chain means a failure at any step blocks everything after it.
For example, a PyPI hiccup can't leave a GitHub Release around for a package that
isn't actually installable. If the `publish` job fails after `release`
succeeds, use "Re-run failed jobs" on that workflow run rather than
re-tagging. PyPI publishing is immutable: once a version is published it
can't be re-uploaded, so a bad release means bumping to a new version.

## Related projects

`pulse` is the exploration layer of a three-repo pipeline:

```bash
pulse-code  →  health  →  health-charts
(explore)      (archive)   (visualize)
```

- **[fartbagxp/health](https://github.com/fartbagxp/health)**, a collection of CDC data pipelines (WONDER, data.cdc.gov, NCHS, SEER, WISQARS, GRASP, NSSP, NIS, and more) and the CDC WONDER XML API client and LLM query builder this tool builds on. `pulse`'s SEER, CDC Open Data, WISQARS, GRASP, NSSP, and NIS clients are lightweight, standalone reimplementations of `health`'s equivalent modules — kept dependency-free (just `requests`) rather than depending on `health` directly, which also pulls in `pandas`/`playwright`/`lxml` for its archival pipelines. `pulse` now covers every source `health` does. Where `pulse` is for one-off, ad hoc exploration, `health` is where a query graduates once someone wants it archived on a recurring schedule: 23 of the 36 saved WONDER queries in `src/pulse/queries/` are also saved in `health`'s `src/wonder/queries/`, each wrapped there in a small `fetch_*.py` script that runs on a schedule and commits the result as a CSV under `data/raw/wonder/`. The other 13 (cancer incidence/mortality by site, fetal deaths, PM2.5, TB, STI cases, heat-wave days, etc.) are exploration-only for now, candidates for `health` if any of them turn into a recurring need.
- **[fartbagxp/health-charts](https://github.com/fartbagxp/health-charts)**, the dashboard at the end of the pipeline. It reads the CSVs `health` archives (including the ones seeded by `pulse`'s queries above) directly from GitHub and renders them as an interactive chart site.
