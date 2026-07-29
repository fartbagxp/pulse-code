"""
NSSP SDK — high-level query functions for NSSP emergency department visit signals.

Data source: CMU Delphi Epidata API (https://api.delphi.cmu.edu/epidata/)
Underlying surveillance: CDC National Syndromic Surveillance Program (NSSP)

Signals track the percentage of ED visits attributed to each respiratory pathogen,
smoothed with a 7-day trailing average. Updated weekly (epiweeks).

Example:
    from pulse.nssp_sdk import get_ed_visits
    rows = get_ed_visits(pathogen="covid", geo_type="state", geo_value="ca")
"""

from __future__ import annotations

from typing import Any

from pulse.nssp_client import DelphiClient, GEO_TYPES, SIGNALS, _current_epiweek

_client: DelphiClient | None = None


def _get_client() -> DelphiClient:
    global _client
    if _client is None:
        _client = DelphiClient()
    return _client


def get_ed_visits(
    pathogen: str = "covid",
    geo_type: str = "state",
    geo_value: str = "*",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Weekly % of ED visits for a respiratory pathogen from NSSP (2022–present).

    pathogen: 'covid', 'influenza', 'rsv', 'combined'
    geo_type: 'nation', 'state', 'county', 'hhs' (HHS regions 1–10)
    geo_value: '*' for all, or specific value:
               state → two-letter lowercase e.g. 'ca', 'ny'
               county → 5-digit FIPS e.g. '06037'
               hhs → region number string e.g. '4'
               nation → 'us'
    start_date / end_date: epiweek YYYYWW e.g. '202501' (week 1 of 2025). Defaults to last 52 weeks.

    Key columns returned:
        geo_value    — geographic identifier
        time_value   — epiweek as YYYYMMDD (Saturday end-of-week)
        value        — % ED visits for the pathogen
        stderr       — standard error of the estimate
        sample_size  — number of ED visits in the denominator
        direction    — trend: 1 (increasing), 0 (stable), -1 (decreasing), None
    """
    signal = SIGNALS.get(pathogen)
    if signal is None:
        raise ValueError(f"Unknown pathogen {pathogen!r}. Use: {list(SIGNALS)}")
    if geo_type not in GEO_TYPES:
        raise ValueError(f"Unknown geo_type {geo_type!r}. Use: {sorted(GEO_TYPES)}")

    time_values = None
    if start_date and end_date:
        time_values = f"{start_date}-{end_date}"
    elif start_date:
        time_values = f"{start_date}-{_current_epiweek()}"
    elif end_date:
        time_values = f"202239-{end_date}"

    return _get_client().get(
        signal=signal, geo_type=geo_type, geo_value=geo_value, time_values=time_values
    )


def get_national_trends(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Weekly national % ED visits for all four pathogens (covid, influenza, rsv, combined).

    Returns rows tagged with a 'pathogen' field added for convenience.
    start_date / end_date: 'YYYYWW'
    """
    results = []
    for name in SIGNALS:
        rows = get_ed_visits(
            pathogen=name,
            geo_type="nation",
            geo_value="us",
            start_date=start_date,
            end_date=end_date,
        )
        for row in rows:
            results.append({**row, "pathogen": name})
    return results


def get_state_snapshot(
    pathogen: str = "covid",
    week: str | None = None,
) -> list[dict[str, Any]]:
    """% ED visits for a pathogen across all states for a given week (or latest if omitted).

    pathogen: 'covid', 'influenza', 'rsv', 'combined'
    week: epiweek 'YYYYWW', e.g. '202501'. Omit for most recent.
    """
    return get_ed_visits(pathogen=pathogen, geo_type="state", geo_value="*", start_date=week, end_date=week)


def get_hhs_region_trends(
    pathogen: str = "covid",
    region: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Weekly % ED visits by HHS region (1–10).

    pathogen: 'covid', 'influenza', 'rsv', 'combined'
    region: 1–10. Omit for all regions.
    start_date / end_date: 'YYYYWW'
    """
    geo_value = str(region) if region is not None else "*"
    return get_ed_visits(
        pathogen=pathogen, geo_type="hhs", geo_value=geo_value, start_date=start_date, end_date=end_date
    )


def clear_cache() -> None:
    _get_client().clear_cache()
