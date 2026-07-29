"""
WISQARS SDK — query functions for CDC injury mortality and violence data.

Data source: data.cdc.gov (Socrata), surfacing WISQARS / NCHS datasets.
Official portal: https://wisqars.cdc.gov/

Example:
    from pulse.wisqars_sdk import get_injury_mortality, get_injury_state
    rows = get_injury_mortality(intent="Suicide", mechanism="Firearm")
    rows = get_injury_state(intent="FA_Deaths", year="2023")
"""

from __future__ import annotations

from typing import Any

from pulse.soda_client import SodaClient
from pulse.wisqars_catalog import DATASETS

_client: SodaClient | None = None


def _get_client() -> SodaClient:
    global _client
    if _client is None:
        _client = SodaClient()
    return _client


def query_dataset(
    dataset_id: str,
    where: str | None = None,
    select: str | None = None,
    order: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Generic SODA query against a WISQARS dataset by Socrata ID."""
    return _get_client().get(
        dataset_id, where=where, select=select, order=order, limit=limit
    )


# ── Injury Mortality (1999–2016) ───────────────────────────────────────────────


def get_injury_mortality(
    intent: str | None = None,
    mechanism: str | None = None,
    sex: str | None = None,
    age: str | None = None,
    race: str | None = None,
    year: int | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Fatal injury counts and rates by intent, mechanism, demographics (1999–2016).

    intent: 'All Intentions', 'Unintentional', 'Suicide', 'Homicide',
            'Undetermined', 'Legal intervention/war'
    mechanism: 'All Mechanisms', 'Firearm', 'Poisoning', 'Fall',
               'Motor vehicle traffic', 'Suffocation', 'Drowning', 'Cut/pierce'
    sex: 'Both sexes', 'Male', 'Female'
    age: '< 15', '15–24', '25–34', '35–44', '45–54', '55–64', '65–74', '75+', 'All Ages'
    race: 'All races', 'White', 'Black', 'American Indian/Alaska Native', 'Asian/Pacific Islander'
    year: 1999–2016
    """
    clauses = []
    if intent:
        clauses.append(f"injury_intent = '{intent}'")
    if mechanism:
        clauses.append(f"injury_mechanism = '{mechanism}'")
    if sex:
        clauses.append(f"sex = '{sex}'")
    if age:
        clauses.append(f"age_years = '{age}'")
    if race:
        clauses.append(f"race = '{race}'")
    if year:
        clauses.append(f"year = '{year}'")
    return query_dataset(
        DATASETS["injury_mortality"].id,
        where=" AND ".join(clauses) if clauses else None,
        order="year DESC, deaths DESC",
        limit=limit,
    )


# ── Mapping datasets: national / state / county (2019–present) ────────────────


def get_injury_national(
    intent: str | None = None,
    period_type: str | None = None,
    year: str | None = None,
) -> list[dict[str, Any]]:
    """National injury/violence counts and rates — monthly, annual, or TTM (2019–present).

    intent: 'FA_Deaths', 'FA_Homicide', 'FA_Suicide', 'All_Homicide', 'All_Suicide', 'Drug_OD'
    period_type: 'year', 'month', 'TTM' (trailing twelve months)
    year: '2023', '2024'. For monthly data, period is 'YYYY-MM-DDT...' — filter by year substring.
    """
    clauses = []
    if intent:
        clauses.append(f"intent = '{intent}'")
    if period_type:
        clauses.append(f"type = '{period_type}'")
    if year and period_type == "year":
        clauses.append(f"period = '{year}'")
    elif year:
        clauses.append(f"period LIKE '%{year}%'")
    return query_dataset(
        DATASETS["injury_national"].id,
        where=" AND ".join(clauses) if clauses else None,
        order="period DESC",
        limit=500,
    )


def get_injury_state(
    state: str | None = None,
    intent: str | None = None,
    year: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """State-level injury/violence counts and rates — annual and TTM (2019–present).

    state: two-digit FIPS code e.g. '06' (California), '48' (Texas),
           or state name e.g. 'California'
    intent: 'FA_Deaths', 'FA_Homicide', 'FA_Suicide', 'All_Homicide', 'All_Suicide', 'Drug_OD'
    year: '2023', '2024', or 'TTM'
    """
    clauses = []
    if state:
        if state.isdigit():
            clauses.append(f"geoid = '{state.zfill(2)}'")
        else:
            clauses.append(f"upper(name) LIKE '%{state.upper()}%'")
    if intent:
        clauses.append(f"intent = '{intent}'")
    if year:
        clauses.append(f"period = '{year}'")
    return query_dataset(
        DATASETS["injury_state"].id,
        where=" AND ".join(clauses) if clauses else None,
        order="period DESC, rate DESC",
        limit=limit,
    )


def get_injury_county(
    state: str | None = None,
    county: str | None = None,
    intent: str | None = None,
    year: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """County-level injury/violence counts and rates — annual (2019–present).

    Low counts are suppressed per NCHS guidelines (count_sup = 'Suppressed').
    state: state name e.g. 'Texas', or two-digit FIPS e.g. '48'
    county: county name partial match e.g. 'Harris', 'Cook'
    intent: 'FA_Deaths', 'FA_Homicide', 'FA_Suicide', 'All_Homicide', 'All_Suicide', 'Drug_OD'
    year: '2023', '2024', or 'TTM'
    """
    clauses = []
    if state:
        if state.isdigit():
            clauses.append(f"st_geoid = '{state.zfill(2)}'")
        else:
            clauses.append(f"upper(st_name) LIKE '%{state.upper()}%'")
    if county:
        clauses.append(f"upper(name) LIKE '%{county.upper()}%'")
    if intent:
        clauses.append(f"intent = '{intent}'")
    if year:
        clauses.append(f"period = '{year}'")
    return query_dataset(
        DATASETS["injury_county"].id,
        where=" AND ".join(clauses) if clauses else None,
        order="period DESC, rate DESC",
        limit=limit,
    )


def get_injury_census_tract(
    state: str | None = None,
    tract: str | None = None,
    intent: str | None = None,
    year: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Census-tract-level injury/violence counts and rates using Bayesian estimation (2022–present).

    Finest geographic granularity in the WISQARS mapping series.
    Low counts are suppressed per NCHS guidelines (count_sup = 'Suppressed').
    state: state name e.g. 'Texas', or two-digit FIPS e.g. '48'
    tract: census tract GEOID partial match
    intent: 'All_Homicide', 'Drug_OD' (Bayesian estimation; not all intents available at tract level)
    year: '2022', '2023', etc.
    """
    clauses = []
    if state:
        if state.isdigit():
            clauses.append(f"st_geoid = '{state.zfill(2)}'")
        else:
            clauses.append(f"upper(st_name) LIKE '%{state.upper()}%'")
    if tract:
        clauses.append(f"name LIKE '%{tract}%'")
    if intent:
        clauses.append(f"intent = '{intent}'")
    if year:
        clauses.append(f"period = '{year}'")
    return query_dataset(
        DATASETS["injury_census_tract"].id,
        where=" AND ".join(clauses) if clauses else None,
        order="period DESC, rate DESC",
        limit=limit,
    )


def clear_cache() -> None:
    _get_client().clear_cache()
