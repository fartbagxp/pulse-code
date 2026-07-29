"""
SEER*Explorer variable catalog — cancer sites and classification vocabularies.

Loads the bundled snapshot at data/seer_var_formats.json. Refresh by fetching
SeerClient().get_var_formats() and overwriting that file if SEER adds/renames
sites.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).parent / "data" / "seer_var_formats.json"

_catalog: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _catalog
    if _catalog is None:
        if _CATALOG_PATH.exists():
            _catalog = json.loads(_CATALOG_PATH.read_text())
        else:
            from pulse.seer_client import SeerClient

            _catalog = SeerClient().get_var_formats()
    return _catalog


def variable_formats() -> dict[str, dict[str, str]]:
    """All label vocabularies keyed by field name (site, sex, race, age_range,
    stage, rate_type, data_type, graph_type, year_range, ...)."""
    return _load()["VariableFormats"]


def cancer_sites() -> dict[str, str]:
    """Map of site code (str) -> cancer site label, e.g. {"55": "Breast"}."""
    return variable_formats()["site"]


def find_site(query: str) -> list[tuple[str, str]]:
    """Case-insensitive substring search over cancer site names.

    Returns a list of (code, label) pairs.
    """
    q = query.lower()
    return [
        (code, label) for code, label in cancer_sites().items() if q in label.lower()
    ]


SEX = {"1": "Both Sexes", "2": "Male", "3": "Female"}
RACE = {
    "1": "All Races / Ethnicities",
    "2": "White (includes Hispanic)",
    "3": "Black (includes Hispanic)",
    "4": "Non-Hispanic Asian / Pacific Islander",
    "5": "Non-Hispanic American Indian / Alaska Native",
    "6": "Hispanic (any race)",
    "8": "Non-Hispanic White",
    "9": "Non-Hispanic Black",
}
DATA_TYPE = {
    "1": "SEER Incidence",
    "2": "U.S. Mortality",
    "3": "Preliminary Incidence Rates",
    "4": "Survival",
    "5": "Prevalence",
    "6": "Risk of Diagnosis/Dying",
    "9": "Incidence and Mortality Comparison",
}
RATE_TYPE = {
    "1": "Observed SEER Incidence Rate",
    "2": "Delay-adjusted SEER Incidence Rate",
    "3": "U.S. Mortality Rate",
}
GRAPH_TYPE = {
    "1": "Long-Term Trends",
    "2": "Recent Trends",
    "3": "Rates by Age",
    "10": "Recent Rates",
}
STAGE = {
    "101": "All Stages",
    "102": "In Situ",
    "103": "All Invasive Stages",
    "104": "Localized",
    "105": "Regional",
    "106": "Distant",
    "107": "Unstaged",
}
AGE_RANGE = {
    "1": "All Ages",
    "9": "Ages < 50",
    "6": "Ages < 65",
    "141": "Ages 50-64",
    "157": "Ages 65+",
    "16": "Ages <15",
    "11": "Ages <40",
    "62": "Ages 15-39",
    "122": "Ages 40-64",
    "160": "Ages 65-74",
    "166": "Ages 75+",
}
COMPARE_BY = {"sex", "race", "age_range", "site", "year_range"}
