"""
WISQARS dataset registry — Web-based Injury Statistics Query and Reporting System.

Data sourced from data.cdc.gov (Socrata). Official WISQARS portal: https://wisqars.cdc.gov/
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dataset:
    id: str
    name: str
    description: str
    years: str
    key_columns: list[str] = field(default_factory=list)


DATASETS: dict[str, Dataset] = {
    "injury_mortality": Dataset(
        id="nt65-c7a7",
        name="NCHS Injury Mortality: United States",
        description=(
            "Fatal injury counts, population, and age-specific rates by year, sex, age group, "
            "race, injury intent, and injury mechanism. Source: NCHS Vital Statistics System."
        ),
        years="1999–2016",
        key_columns=[
            "year",
            "sex",
            "age_years",
            "race",
            "injury_mechanism",
            "injury_intent",
            "deaths",
            "population",
            "age_specific_rate",
            "age_specific_rate_standard_error",
            "age_specific_rate_lower_confidence_limit",
            "age_specific_rate_upper_confidence_limit",
        ],
    ),
    "injury_national": Dataset(
        id="t6u2-f84c",
        name="Mapping Injury, Overdose & Violence — National",
        description=(
            "National monthly, annual, and trailing-twelve-month (TTM) counts and rates for "
            "firearm deaths, firearm homicide, firearm suicide, all homicide, all suicide, "
            "and drug overdose. Source: WISQARS / NCHS."
        ),
        years="2019–present",
        key_columns=["geoid", "intent", "period", "type", "count", "rate", "data_as_of"],
    ),
    "injury_state": Dataset(
        id="fpsi-y8tj",
        name="Mapping Injury, Overdose & Violence — State",
        description=(
            "State-level annual and TTM counts and rates for firearm deaths, firearm homicide, "
            "firearm suicide, all homicide, all suicide, and drug overdose. Source: WISQARS / NCHS."
        ),
        years="2019–present",
        key_columns=["geoid", "name", "intent", "period", "count_sup", "rate", "data_as_of"],
    ),
    "injury_county": Dataset(
        id="psx4-wq38",
        name="Mapping Injury, Overdose & Violence — County",
        description=(
            "County-level annual counts and rates for firearm deaths, firearm homicide, "
            "firearm suicide, all homicide, all suicide, and drug overdose. "
            "Low-count values are suppressed per NCHS guidelines. Source: WISQARS / NCHS."
        ),
        years="2019–present",
        key_columns=[
            "geoid",
            "name",
            "st_geoid",
            "st_name",
            "intent",
            "period",
            "count_sup",
            "rate",
            "rate_m",
            "data_as_of",
        ],
    ),
    "injury_census_tract": Dataset(
        id="4day-mt2f",
        name="Mapping Injury, Overdose & Violence — Census Tract",
        description=(
            "Census-tract-level annual counts and rates for homicide and drug overdose "
            "using Bayesian small-area estimation. Finest geographic granularity in the "
            "WISQARS mapping series. Low counts are suppressed per NCHS guidelines. "
            "Source: WISQARS / NCHS."
        ),
        years="2022–present",
        key_columns=[
            "geoid",
            "name",
            "st_geoid",
            "st_name",
            "intent",
            "period",
            "count_sup",
            "rate",
            "rate_m",
            "data_as_of",
        ],
    ),
}

# ── Reference: valid filter values ────────────────────────────────────────────

# injury_mortality dataset
INJURY_INTENTS = [
    "All Intentions",
    "Unintentional",
    "Suicide",
    "Homicide",
    "Undetermined",
    "Legal intervention/war",
]

INJURY_MECHANISMS = [
    "All Mechanisms",
    "Firearm",
    "Poisoning",
    "Fall",
    "Motor vehicle traffic",
    "Suffocation",
    "Drowning",
    "Cut/pierce",
    "Fire/hot object or substance",
    "All Other Transport",
    "All Other Specified",
    "Unspecified",
]

# Mapping datasets (injury_national / injury_state / injury_county)
MAPPING_INTENTS = [
    "FA_Deaths",  # All firearm deaths
    "FA_Homicide",  # Firearm homicides
    "FA_Suicide",  # Firearm suicides
    "All_Homicide",  # All homicides (any mechanism)
    "All_Suicide",  # All suicides (any mechanism)
    "Drug_OD",  # Drug overdose deaths
]

MAPPING_PERIOD_TYPES = ["year", "month", "TTM"]  # TTM = trailing twelve months
