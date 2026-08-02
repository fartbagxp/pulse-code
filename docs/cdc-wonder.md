# CDC WONDER

[CDC WONDER](https://wonder.cdc.gov/) (Wide-ranging ONline Data for
Epidemiologic Research) is the federal government's main interface for public
health statistics: drug overdose deaths, maternal mortality, birth rates,
COVID deaths by race, suicide trends, vaccine adverse events, and much more.
Its XML API is powerful but opaque. `pulse source wonder` wraps it with
bundled, validated queries you can run directly, plus Claude-backed commands
that write new XML queries from plain English.

## `pulse source wonder datasets`: What's Available

```bash
pulse source wonder datasets                    # all datasets
pulse source wonder datasets --topic Mortality  # filter by topic
pulse source wonder datasets --json             # JSON output
```

Shows all 26+ CDC WONDER datasets with topic, year range, what the data
covers, the number of bundled example queries, and whether age-adjusted rates
are available.

Topics: Mortality, Infant Mortality, Natality, Environment, Vaccine Safety,
Infectious Disease.

## `pulse source wonder info <ID>`: Deep Dive on a Dataset

```bash
pulse source wonder info D176    # Provisional Mortality (2018-present)
pulse source wonder info D66     # Natality / birth data
pulse source wonder info D8      # VAERS vaccine adverse events
```

Shows the subject description, available measures, the main grouping
dimensions, and all bundled example queries for that dataset.

## `pulse source wonder list-queries`: All Bundled Example Queries

```bash
pulse source wonder list-queries
pulse source wonder list-queries --dataset D176   # filter by dataset
```

36 working XML queries across 21 datasets, covering drug/opioid/fentanyl
deaths, maternal mortality, births, COVID deaths by race, suicide, tick-borne
diseases, the racial mortality gap, infant mortality, heart disease vs.
cancer, and more.

## `pulse source wonder run <query>`: Execute a Query

```bash
# Run a bundled query by filename (no path needed)
pulse source wonder run drug-deaths-by-year-2018-2024-req.xml

# Output formats
pulse source wonder run opioid-overdose-deaths-2018-2024-req.xml -f csv
pulse source wonder run mortality-by-year-cause-2021-2024-req.xml -f json
pulse source wonder run births-by-year-2007-2024-req.xml -f table -o births.csv

# Run your own query file
pulse source wonder run /path/to/my-query.xml
```

Hits the live CDC WONDER API. No login required; CDC requires a ~2-minute
cooldown between queries.

## `pulse source wonder build "<description>"`: Build a Query With Claude

```bash
# Requires an LLM key, see llm-providers.md
pulse source wonder build "drug overdose deaths by state and year 2018-2023"
pulse source wonder build "maternal mortality by race, 2018-2023" -o maternal-race.xml
pulse source wonder build "birth rates by age of mother 2010 to 2024" --no-suggest
```

Suggests the closest existing queries first, then calls Claude to build a new
XML query. The LLM selects the right dataset and generates overrides merged
onto a validated base template.

## `pulse source wonder query "<description>"`: Build and Run in One Step

```bash
pulse source wonder query "fentanyl deaths by state 2020-2024" -f csv
pulse source wonder query "infant mortality by race 2018-2023" --save-xml infant-race.xml
```

## `pulse source wonder refine <file> "<feedback>"`: Iterate on a Query

```bash
pulse source wonder refine opioid-overdose-deaths-2018-2024-req.xml "break it down by state"
pulse source wonder refine drug-deaths-by-year-2018-2024-req.xml "add sex breakdown" -o drug-sex.xml
pulse source wonder refine drug-deaths-by-year-2018-2024-req.xml "show monthly not yearly" --run -f csv
```

## Bundled Datasets (with base templates)

| ID          | Subject                                                       | Years        |
| ----------- | ------------------------------------------------------------- | ------------ |
| D176        | Provisional mortality: opioids, COVID, suicide, heart disease | 2018-present |
| D157        | Final mortality, single race (MCD+UCD)                        | 2018-2023    |
| D158        | Underlying cause of death, single race: maternal mortality    | 2018-2023    |
| D77         | Multiple cause of death: drug deaths (historical)             | 1999-2020    |
| D76         | Underlying cause of death: suicide, cancer (historical)       | 1999-2020    |
| D141        | MCD with US-Mexico border regions                             | 1999-2020    |
| D140        | Compressed mortality ICD-10                                   | 1999-2016    |
| D16         | Compressed mortality ICD-9                                    | 1979-1998    |
| D74         | Compressed mortality ICD-8                                    | 1968-1978    |
| D69         | Linked birth/infant death records                             | 2007-2023    |
| D159        | Linked birth/infant death, expanded race                      | 2017-2023    |
| D31/D18/D23 | Linked birth/infant death (historical)                        | 1995-2006    |
| D66         | Natality: birth rates, birth outcomes                         | 2007-2024    |
| D149        | Natality, expanded race detail                                | 2016-2024    |
| D192        | Provisional natality (monthly)                                | 2023-present |
| D27/D10     | Natality (historical)                                         | 1995-2006    |
| D8          | VAERS vaccine adverse events                                  | 1990-present |
| D104        | Heat wave days by county                                      | 1981-2010    |
| D60/D80/D81 | NLDAS temperature, sunlight, precipitation                    | 1979-2011    |
| D73         | PM2.5 fine particulate matter                                 | 2003-2011    |
| D61         | MODIS land surface temperature                                | 2003-2008    |

## Public Health Questions You Can Answer

- How did opioid overdose deaths trend from 1999 to today, broken down by drug type?
- What is the racial gap in COVID-19 mortality?
- How does maternal mortality differ by race and state?
- Which states have the highest suicide rates by sex?
- How have birth rates changed by age of mother since 1995?
- Are tick-borne disease cases increasing?
- How do PM2.5 air quality levels correlate with where people live?
- What are the most common adverse events reported after COVID vaccines?

## Writing XML Queries by Hand

For datasets with no bundled template, see
[building-xml-queries.md](building-xml-queries.md): the XML parameter
structure, the radio-button trap behind most HTTP 500s, finder-stage
variables, and rate limits.
