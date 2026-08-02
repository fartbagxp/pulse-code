# Pulse

[![PyPI](https://img.shields.io/pypi/v/pulse-code?style=for-the-badge)](https://pypi.org/project/pulse-code/)
[![Python versions](https://img.shields.io/badge/python-3.14%2B-blue?style=for-the-badge)](https://pypi.org/project/pulse-code/)
[![Publish](https://img.shields.io/github/actions/workflow/status/fartbagxp/pulse-code/publish.yml?style=for-the-badge&label=publish)](https://github.com/fartbagxp/pulse-code/actions/workflows/publish.yml)
[![Pages](https://img.shields.io/github/actions/workflow/status/fartbagxp/pulse-code/pages.yml?style=for-the-badge&label=pages)](https://fartbagxp.github.io/pulse-code/)
[![License](https://img.shields.io/badge/license-CC0--1.0-blue?style=for-the-badge)](LICENSE)

`pulse` is a command line tool for querying public health data. It covers
seven live sources: CDC WONDER, NCI SEER cancer statistics, CDC Open Data,
WISQARS injury data, ATSDR GRASP disease surveillance, NSSP ED visits, and NIS
vaccination surveys. Browse them by topic, run bundled queries, and get CSV,
JSON, or a table back.

![pulse-code demo](docs/demo/pulse-demo.gif)

## Setup

```bash
# From PyPI (requires Python 3.14+)
pip install pulse-code

# Or from source
uv sync
```

Querying any of the seven sources needs no API key or login. The `build`,
`query`, `refine`, `compare`, and `chat` commands call an LLM to write CDC
WONDER XML for you, so those need a key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Azure OpenAI and proxied connections work too; see
[docs/llm-providers.md](docs/llm-providers.md).

## Usage

Five top level commands. `topics` browses by subject across all sources,
`source` browses and queries one source, `search` is free text find, `doctor`
checks credentials and source reachability, and `generate` writes a
health-style `fetch_*.py` starter script from a saved query.

Start with a subject if you don't know which source holds what you want:

```bash
pulse topics                      # every subject across all seven sources
pulse topics mortality            # drill into one
pulse search "opioid overdose deaths by state"
pulse search "tick-borne disease cases" --queries    # queries only
pulse search "recent COVID deaths" --datasets        # datasets only
```

Or go straight at a source. Each one nests the same way:

```bash
pulse source                      # what sources exist
pulse source seer                 # what that source offers
pulse source seer mortality       # query it
```

### `pulse source wonder`: CDC WONDER

```bash
pulse source wonder datasets                          # 26+ datasets
pulse source wonder info D176                         # provisional mortality
pulse source wonder run drug-deaths-by-year-2018-2024-req.xml -f csv
pulse source wonder query "fentanyl deaths by state 2020-2024" -f csv
```

Mortality, natality, VAERS, and environmental datasets going back to 1968,
with 23 bundled XML queries and LLM-backed commands that write new ones. CDC
requires a ~2 minute cooldown between queries. Full command reference and the
dataset table: [docs/cdc-wonder.md](docs/cdc-wonder.md).

### `pulse source seer`: NCI SEER cancer statistics

```bash
pulse source seer sites --search breast              # look up a cancer site code
pulse source seer mortality --site 55 --sex female -f csv
pulse source seer mortality --site 47 --compare-by race -f csv
pulse source seer incidence --site 55 --stage 104 -f csv
pulse source seer by-age --site 1 -f csv
pulse source seer compare-sites 55 47 66 -f csv       # breast vs. lung vs. melanoma
```

Cancer incidence and U.S. mortality rates and counts by site, sex, race, and
age group, back to 1975. Calls the same unauthenticated JSON endpoints
[SEER\*Explorer](https://seer.cancer.gov/statistics-network/explorer/) itself
uses.

### `pulse source cdc-open`: CDC Open Data (data.cdc.gov)

```bash
pulse source cdc-open list                            # 60+ datasets: mortality, vaccination, wastewater, NNDSS, HAI, and more
pulse source cdc-open list --search wastewater
pulse source cdc-open query leading_death --where "year='2015'" -f csv
pulse source cdc-open query bi63-dtpu --where "state='California'" --limit 500 -f json
```

Raw [SODA](https://dev.socrata.com/) queries (`--where`, `--select`,
`--group`, `--order`) against any registered Socrata dataset, by registry key
or Socrata ID. Set `CDC_DATA_APP_TOKEN` for a higher rate limit.

### `pulse source wisqars`: injury and violence data

```bash
pulse source wisqars list
pulse source wisqars mortality --intent Suicide --mechanism Firearm -f csv       # 1999-2016
pulse source wisqars national --intent FA_Deaths --type year -f csv             # 2019-present
pulse source wisqars state --intent Drug_OD --year 2023 -f table
pulse source wisqars county --state Texas --intent FA_Deaths --year 2023
pulse source wisqars tract --state Texas --intent All_Homicide --year 2022      # census-tract granularity
pulse source wisqars query t6u2-f84c --where "intent='Drug_OD' AND type='year'"
```

Fatal firearm, suicide, homicide, and drug overdose data from
[WISQARS](https://wisqars.cdc.gov/) at national, state, county, and census
tract granularity, backed by the same Socrata client as `cdc-open`.

### `pulse source grasp`: ATSDR GRASP disease surveillance

```bash
pulse source grasp list
pulse source grasp hantavirus cases --outcome Dead -f table              # pre-1993-present
pulse source grasp hantavirus by-year -f table
pulse source grasp hantavirus by-state -f table
pulse source grasp fluview ili-data --region nat --region ca --region tx --epiweeks 202001-202026
pulse source grasp fluview ili-by-region --epiweeks 201940-202020 -f table
pulse source grasp fluview clinical-data --region nat --epiweeks 202001-202026
pulse source grasp flusurv data --location CA --location OH --epiweeks 202001-202020 -f csv
pulse source grasp flusurv by-season --location CA -f table
pulse source grasp flusurv by-location --season 2019-20 -f table
```

Hantavirus cases, FluView ILINet influenza-like-illness activity, WHO/NREVSS
clinical lab flu positivity, and FluSurv-NET hospitalization rates, from
[gis.cdc.gov/grasp](https://gis.cdc.gov/grasp/) and the CMU Delphi Epidata
API. Repeatable options like `--region` and `--location` take one value per
flag (`--region nat --region ca`), unlike `health`'s argparse CLI, which
accepts a space separated list after a single flag.

### `pulse source nssp`: emergency department visit surveillance

```bash
pulse source nssp query covid --geo-type state --geo-value ca -f csv
pulse source nssp query influenza --geo-type nation --geo-value us
pulse source nssp national --start 202401 -f csv                # all 4 pathogens, national
pulse source nssp hhs rsv --region 4 -f table
```

Weekly percentage of ED visits attributed to COVID, flu, and RSV from the
[National Syndromic Surveillance Program](https://www.cdc.gov/nssp/), via the
CMU Delphi Epidata API. Time values use epiweek format (`YYYYWW`, so `202518`
is week 18 of 2025).

### `pulse source nis`: National Immunization Survey

```bash
pulse source nis list child                                       # available years, 2011-2022
pulse source nis stream child 2022 --limit 10 -f json              # raw respondent microdata
pulse source nis rates child 2022 -f table                         # state-level UTD rates
pulse source nis rates teen 2022 --vaccines P_UTDHPV13 -f csv
pulse source nis national child 2022                                # national UTD summary
```

Childhood (19-35mo) and teen (13-17yr) vaccination coverage from CDC's annual
random-digit-dial survey. The source files are large fixed-width `.dat` files
(50-200MB), and `pulse` streams them straight through without writing
anything to disk.

Known issue: CDC restructured its NIS file hosting after this registry's URLs
were last verified, so live `stream`, `rates`, and `national` calls currently
404 for at least the 2015+ years. Some years now live under
`www.cdc.gov/nis/media/files/...` or `ftp.cdc.gov/pub/Vaccines_NIS/` rather
than the legacy path baked into `nis_catalog.py`. `health` has the same gap.
The CLI plumbing and DAT-streaming parser are unit tested and correct; only
the hardcoded per-year URLs need refreshing.

## Testing

```bash
uv run pytest                  # unit tests only, fast, no network (default)
uv run pytest -m integration   # + integration tests
```

## Docs

- [cdc-wonder.md](docs/cdc-wonder.md), the full `wonder` command reference and
  bundled dataset table
- [building-xml-queries.md](docs/building-xml-queries.md), how to write WONDER
  XML for a dataset with no template
- [llm-providers.md](docs/llm-providers.md), Anthropic, Azure OpenAI, and
  proxy configuration
- [testing.md](docs/testing.md), what's covered and how the integration tests
  are split
- [release.md](docs/release.md), how a release is cut and what to do when one
  half-fails

## Related projects

`pulse` is the exploration layer of various projects:

```bash
pulse-code  →  health  →  health-charts
(explore)      (archive)   (visualize)
```

[fartbagxp/health](https://github.com/fartbagxp/health) archives the same
sources on a schedule and commits the results as CSVs. It's also home to the
CDC WONDER XML API client and LLM query builder this tool builds on. `pulse`
is where a query starts; `health` is where it graduates once someone wants it
on a cron. 23 of the 36 saved WONDER queries in `src/pulse/queries/` are also
in `health`, each wrapped in a `fetch_*.py` script. The other 13 (cancer
incidence and mortality by site, fetal deaths, PM2.5, TB, STI cases, heat wave
days, and others) are exploration only for now. `pulse`'s source clients are
standalone reimplementations of `health`'s modules, kept to just `requests`
instead of pulling in the `pandas`/`playwright`/`lxml` stack that `health`'s
pipelines need.

[fartbagxp/health-charts](https://github.com/fartbagxp/health-charts) reads
those archived CSVs from GitHub and renders them as an interactive chart site.
