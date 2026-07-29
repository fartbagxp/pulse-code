"""
SEER SDK — high-level query functions for NCI SEER cancer incidence/mortality
statistics (https://seer.cancer.gov/statistics-network/explorer/).

Example:
    from pulse.seer_sdk import get_mortality_trend, search_cancer_sites
    search_cancer_sites("breast")
    rows = get_mortality_trend(site=55, sex="both", compare_by="race")
"""

from __future__ import annotations

from typing import Any

from pulse.seer_catalog import cancer_sites, find_site, variable_formats
from pulse.seer_client import SeerClient

_client: SeerClient | None = None

_SEX_CODES = {"both": "1", "male": "2", "female": "3", "1": "1", "2": "2", "3": "3"}
_RATE_TYPE_FOR_DATA_TYPE = {
    "1": "1",
    "2": "3",
}  # incidence -> observed, mortality -> US mortality
_DATA_TYPE_CODES = {"incidence": "1", "mortality": "2"}
_GRAPH_TYPE_CODES = {
    "recent-trends": "2",
    "long-term-trends": "1",
    "rates-by-age": "3",
}


def _get_client() -> SeerClient:
    global _client
    if _client is None:
        _client = SeerClient()
    return _client


def list_cancer_sites() -> list[dict[str, str]]:
    """All cancer sites in the SEER*Explorer catalog, as [{"code": ..., "name": ...}, ...]."""
    return [{"code": code, "name": name} for code, name in cancer_sites().items()]


def search_cancer_sites(query: str) -> list[dict[str, str]]:
    """Case-insensitive substring search over cancer site names."""
    return [{"code": code, "name": name} for code, name in find_site(query)]


def _resolve_sex(sex: str | int) -> str:
    code = _SEX_CODES.get(str(sex).lower())
    if code is None:
        raise ValueError(f"Unknown sex {sex!r}. Use: both, male, female")
    return code


def _parse_response(resp: dict[str, Any]) -> list[dict[str, Any]]:
    info = resp["info"]
    key_order: list[str] = info["key-order"]
    data_fields: list[str] = info["data-fields"]
    labels = variable_formats()

    rows: list[dict[str, Any]] = []
    for series_key, series in resp["data"].items():
        dims = dict(zip(key_order, series_key.split("_")))
        dim_row = {}
        for field, code in dims.items():
            dim_row[field] = code
            field_labels = labels.get(field)
            if field_labels:
                dim_row[f"{field}_label"] = field_labels.get(code, code)
        for point in series["data_series"]:
            row = dict(dim_row)
            row.update(zip(data_fields, point))
            rows.append(row)
    return rows


def get_trend(
    site: int | str,
    data_type: str = "mortality",
    graph_type: str = "recent-trends",
    sex: str | int = "both",
    race: str | int = "1",
    age_range: str | int = "1",
    stage: str | int = "101",
    rate_type: str | int | None = None,
    year_range: str | int | None = None,
    compare_by: str | None = None,
    compare_sites: list[int | str] | None = None,
) -> list[dict[str, Any]]:
    """Cancer statistics trend from SEER*Explorer.

    site: cancer site code, e.g. 55 = Breast, 47 = Lung and Bronchus (see
          list_cancer_sites() / search_cancer_sites()).
    data_type: 'incidence' or 'mortality' (default; U.S. Mortality Rate).
    graph_type: 'recent-trends' (2000-present, default), 'long-term-trends'
                (1975-present), or 'rates-by-age' (rate by age group instead
                of by year).
    sex: 'both' (default), 'male', 'female'.
    race: race/ethnicity code (default '1' = All Races/Ethnicities).
    age_range: age range code (default '1' = All Ages). Ignored when
               graph_type='rates-by-age'.
    stage: cancer stage code (default '101' = All Stages). Only meaningful
           for incidence.
    rate_type: rate type code. Defaults to the type matching data_type
               (observed SEER incidence rate, or U.S. mortality rate).
    year_range: year range code for graph_type='rates-by-age' (which years'
                data to pool for the age-specific rates). Omit for the
                server default (most recent full window).
    compare_by: 'sex', 'race', 'age_range', 'site', or 'year_range' — return
                one series per value of that variable instead of a single
                fixed value (the corresponding sex/race/age_range/site
                argument still supplies the default/base value).
    compare_sites: additional site codes to include when compare_by='site'.

    Returns a flat list of rows: one row per (dimension combo, x-axis point),
    with `<field>` codes and `<field>_label` human-readable labels for every
    compared/fixed dimension, plus x-axis (year or age_range) and rate/count
    fields.
    """
    dtype = _DATA_TYPE_CODES.get(data_type, str(data_type))
    gtype = _GRAPH_TYPE_CODES.get(graph_type, str(graph_type))
    rtype = (
        str(rate_type)
        if rate_type is not None
        else _RATE_TYPE_FOR_DATA_TYPE.get(dtype, "3")
    )

    params: dict[str, Any] = {
        "site": site,
        "data_type": dtype,
        "graph_type": gtype,
        "sex": _resolve_sex(sex),
        "race": race,
        "rate_type": rtype,
        "hdn_stage": stage,
    }
    if graph_type != "rates-by-age":
        params["age_range"] = age_range
    elif year_range is not None:
        params["year_range"] = year_range

    if compare_by:
        if compare_by not in {"sex", "race", "age_range", "site", "year_range"}:
            raise ValueError(f"Unknown compare_by {compare_by!r}")
        params["compareBy"] = compare_by
        if compare_by == "site":
            for extra in compare_sites or []:
                params[f"chk_site_{extra}"] = extra
        else:
            # SEER*Explorer's compare view returns one series per *checked*
            # checkbox (chk_<field>_<code>=<code>). The base field param must
            # be dropped entirely when comparing over it — if present, the
            # server ignores the checkboxes and returns only that one value
            # (which for sex-specific sites like Breast/Prostate/Ovary means
            # "1" = Both Sexes, which has no data at all). Check every
            # cataloged code for the field to get the full breakdown.
            params.pop(compare_by, None)
            for code in variable_formats()[compare_by]:
                params[f"chk_{compare_by}_{code}"] = code

    resp = _get_client().get_chart_data(params)
    return _parse_response(resp)


def get_mortality_trend(
    site: int | str,
    sex: str | int = "both",
    race: str | int = "1",
    age_range: str | int = "1",
    compare_by: str | None = None,
    long_term: bool = False,
) -> list[dict[str, Any]]:
    """U.S. mortality rate/count by year for a cancer site (SEER's default view).

    long_term: use 'Long-Term Trends' (1975-present) instead of 'Recent
               Trends' (2000-present, default).
    """
    return get_trend(
        site=site,
        data_type="mortality",
        graph_type="long-term-trends" if long_term else "recent-trends",
        sex=sex,
        race=race,
        age_range=age_range,
        compare_by=compare_by,
    )


def get_incidence_trend(
    site: int | str,
    sex: str | int = "both",
    race: str | int = "1",
    age_range: str | int = "1",
    stage: str | int = "101",
    compare_by: str | None = None,
    long_term: bool = False,
) -> list[dict[str, Any]]:
    """SEER incidence rate/count by year for a cancer site."""
    return get_trend(
        site=site,
        data_type="incidence",
        graph_type="long-term-trends" if long_term else "recent-trends",
        sex=sex,
        race=race,
        age_range=age_range,
        stage=stage,
        compare_by=compare_by,
    )


def get_mortality_by_age(
    site: int | str,
    sex: str | int = "both",
    race: str | int = "1",
    compare_by: str | None = None,
) -> list[dict[str, Any]]:
    """U.S. mortality rate/count by age group for a cancer site."""
    return get_trend(
        site=site,
        data_type="mortality",
        graph_type="rates-by-age",
        sex=sex,
        race=race,
        compare_by=compare_by,
    )


def compare_sites_mortality(
    sites: list[int | str],
    sex: str | int = "both",
    race: str | int = "1",
    age_range: str | int = "1",
) -> list[dict[str, Any]]:
    """Compare U.S. mortality trends across multiple cancer sites."""
    base, *rest = sites
    return get_trend(
        site=base,
        data_type="mortality",
        sex=sex,
        race=race,
        age_range=age_range,
        compare_by="site",
        compare_sites=rest,
    )


def clear_cache() -> None:
    _get_client().clear_cache()
