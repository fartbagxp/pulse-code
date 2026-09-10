"""
SUDORS dataset registry — CDC's State Unintentional Drug Overdose Reporting System.

SUDORS is death-investigation surveillance for *unintentional and undetermined
intent* drug overdose deaths, funded through Overdose Data to Action in States
(OD2A-S). 49 states and the District of Columbia participate. For each death it
abstracts more than 600 elements from three documents: the death certificate, the
medical examiner or coroner report, and postmortem toxicology.

Why it sits next to WONDER rather than replacing it
---------------------------------------------------
WONDER reports the ICD-10 codes a certifier wrote on the death certificate.
ICD-10 was not designed for a drug supply that turns over yearly: `T40.4`
("other synthetic narcotics") holds illegally-made fentanyls, carfentanil, and
nitazene analogs in one bucket, and xylazine, medetomidine and bromazolam have no
code at all. SUDORS names each of them, because toxicology found them — and it
records circumstances a death certificate never carries: whether a bystander was
present, whether naloxone was given, prior overdose, recent institutional
release, route of use.

Two constraints that shape every query
--------------------------------------
* **`Overall` is not a time series.** A jurisdiction counts toward a year only if
  it reported every overdose death that year *and* had circumstance data on >=75%
  of them. That set changes annually (34 jurisdictions in 2020, 43 in 2024), so
  the annual `Overall` row moves with coverage as much as with mortality. Use
  `pulse source sudors trend` for anything crossing years — it holds the
  jurisdiction set fixed across the range.
* **SUDORS will not reconcile with WONDER.** Its case definition is an ICD-10
  underlying cause in X40-X44 / Y10-Y14 *and/or* literal cause-of-death text
  indicating acute overdose ("overdose", "toxicity", "intoxication"). It also
  counts occurrent deaths (those occurring in the jurisdiction, resident or not).

Access
------
There is no Socrata dataset and no API. The public dashboard is a static React
bundle reading per-section JSON from a fixed path, and CDC publishes the same
release as a workbook carrying the trend tables and a variable dictionary. Both
are unauthenticated and are what this module reads. Restricted-access microdata
goes through CDC's own researcher process; pulse does not touch it.

Reference: https://www.cdc.gov/overdose-prevention/data-research/facts-stats/about-sudors.html
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_URL = (
    "https://www.cdc.gov/overdose-prevention/data-dashboards/sudors-dashboard/data"
)
DASHBOARD_URL = "https://www.cdc.gov/overdose-prevention/data-research/facts-stats/sudors-dashboard-fatal-overdose-data.html"
ABOUT_URL = "https://www.cdc.gov/overdose-prevention/data-research/facts-stats/about-sudors.html"
CODING_MANUAL_URL = "https://www.cdc.gov/overdose-prevention/media/pdfs/2025/02/SUDORS_Coding_Manual_OD2A_v6.3b_Feb2025.pdf"
XLSX_NAME = "SUDORS-Fatal-Overdose-Data.xlsx"

# The dashboard's global sentinel for "suppressed or not available". Any rate
# built on 1-19 deaths is suppressed, as is a whole section a jurisdiction did
# not qualify to report.
SUPPRESSED = 9999

# Age bands are stored as ordinal codes and rendered from this map.
AGE_BANDS = {
    "0": "<15",
    "1": "15-24",
    "2": "25-34",
    "3": "35-44",
    "4": "45-54",
    "5": "55-64",
    "6": "65+",
}

# Data years on the annual view. `pulse source sudors release` reads the live
# cutoff rather than trusting this.
YEARS = "2020–2024"


@dataclass(frozen=True)
class SudorsDataset:
    key: str  # stable registry key, e.g. "drugs-detected"
    name: str
    topic: str  # pulse topic bucket this rolls up to
    grain: str  # what one row is
    sources: tuple[str, ...]  # dashboard JSON filenames, or workbook sheet names
    description: str
    workbook: bool = False  # True if it comes from the .xlsx rather than the JSON


_DATASETS: list[SudorsDataset] = [
    SudorsDataset(
        "drugs-involved",
        "Drugs involved in overdose deaths",
        "Injury & Overdose",
        "year x jurisdiction x drug class",
        ("drugs-involved.json",),
        "Deaths, age-standardized rate, and percent for the ten drug classes a medical "
        "examiner or coroner ruled as causing death.",
    ),
    SudorsDataset(
        "drugs-detected",
        "Drugs of interest detected on toxicology",
        "Injury & Overdose",
        "year x jurisdiction x drug",
        ("drugs-detected.json",),
        "Xylazine, nitazene analogs, carfentanil, para-fluorofentanyl, bromazolam, gabapentin, "
        "kratom and more — found on postmortem toxicology whether or not ruled a cause of death. "
        "This is the cut with no ICD-10 equivalent. Restricted to jurisdictions with toxicology "
        "on >=75% of deaths.",
    ),
    SudorsDataset(
        "circumstances",
        "Circumstances surrounding the death",
        "Injury & Overdose",
        "year x jurisdiction x section x circumstance",
        ("circumstances.json",),
        "Nine sections: intervention opportunities, bystanders, drug-use history, mental health, "
        "overdose response, routes of use, scene evidence, SUD treatment, other. Percentages are "
        "among decedents with known information and are floor estimates.",
    ),
    SudorsDataset(
        "demographics",
        "Deaths by sex, age band, and race/ethnicity",
        "Injury & Overdose",
        "year x jurisdiction x dimension x group",
        (
            "demographics-by-sex.json",
            "demographics-by-age.json",
            "demographics-by-race-ethnicity.json",
        ),
        "All three demographic cuts stacked into one shape. Sex and race/ethnicity rates are "
        "age-standardized to the 2010 U.S. Census; age-band rates are crude.",
    ),
    SudorsDataset(
        "demographics-by-sex-age",
        "Deaths by sex crossed with age band",
        "Injury & Overdose",
        "year x jurisdiction x sex x age band",
        ("demographics-by-sex-age.json",),
        "Age band within sex.",
    ),
    SudorsDataset(
        "deaths-by-month",
        "Monthly deaths by drug class",
        "Injury & Overdose",
        "year x month x jurisdiction x drug class",
        ("deaths-by-month.json",),
        "The only sub-annual cut SUDORS publishes.",
    ),
    SudorsDataset(
        "opioid-stimulant",
        "Opioid x stimulant involvement",
        "Injury & Overdose",
        "year x jurisdiction x 4-way split",
        ("drugs-involved-opioid-stimulant-combo.json",),
        "The four-way split — both, opioids only, stimulants only, neither — that summarizes "
        "polysubstance involvement in one row set.",
    ),
    SudorsDataset(
        "drug-combinations",
        "Drug-pair co-involvement",
        "Injury & Overdose",
        "year x jurisdiction x drug x co-involved drug",
        ("drugs-involved-combos-lollipops.json",),
        "For each drug, how many of its deaths also involved each other drug.",
    ),
    SudorsDataset(
        "top-combinations",
        "Five most common drug combinations",
        "Injury & Overdose",
        "year x jurisdiction x rank 1-5",
        ("drugs-involved-top-five-combo.json",),
        "The exact combinations that account for the largest share of deaths.",
    ),
    SudorsDataset(
        "totals",
        "Total overdose deaths",
        "Injury & Overdose",
        "year x jurisdiction",
        ("totals_for_filter.json",),
        "The denominator behind every percent on the annual view.",
    ),
    SudorsDataset(
        "overall-trend",
        "Jurisdiction-constant trend series",
        "Injury & Overdose",
        "trend range x year x measure",
        ("Overall Trend Data",),
        "The only cross-year-comparable table: each range holds its constituent jurisdictions "
        "fixed across every year in it. Reached through `pulse source sudors trend`.",
        workbook=True,
    ),
    SudorsDataset(
        "trend-statistics",
        "Change between the first and last year of a range",
        "Injury & Overdose",
        "jurisdiction x trend range x measure",
        ("Trend Statistics",),
        "Relative change for counts and rates, absolute (percentage-point) change for percents. "
        "Not significance-tested — SUDORS is a census of included jurisdictions, not a sample.",
        workbook=True,
    ),
    SudorsDataset(
        "data-dictionary",
        "Variable dictionary",
        "Injury & Overdose",
        "variable",
        ("Data Dictionary",),
        "CDC's own definition of the ~1,000 variables in the workbook. `measure` values from the "
        "trend tables join against it.",
        workbook=True,
    ),
]

_BY_KEY: dict[str, SudorsDataset] = {d.key: d for d in _DATASETS}


def datasets() -> list[SudorsDataset]:
    """All registered SUDORS slices, dashboard order."""
    return list(_DATASETS)


def dataset(key: str) -> SudorsDataset | None:
    return _BY_KEY.get(key)


def search(term: str) -> list[SudorsDataset]:
    """Case-insensitive substring match over key, name, grain, and description."""
    q = term.strip().lower()
    if not q:
        return list(_DATASETS)
    return [
        d
        for d in _DATASETS
        if q in d.key
        or q in d.name.lower()
        or q in d.grain.lower()
        or q in d.description.lower()
    ]
