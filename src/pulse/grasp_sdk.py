"""
GRASP SDK — query functions for ATSDR/CDC GRASP disease APIs.

Data source: gis.cdc.gov/grasp (ATSDR Geographic Research, Analysis, and Services Program)
FluView/FluSurv data sourced via the CMU Delphi Epidata API (api.delphi.cmu.edu/epidata/).
No authentication required.

Example:
    from pulse.grasp_sdk import get_hantavirus_cases, summarize_hantavirus_by_year
    cases = get_hantavirus_cases(outcome="Dead")

    from pulse.grasp_sdk import get_fluview_ili, get_fluview_clinical
    ili = get_fluview_ili(regions=["nat", "ca"], epiweeks="202001-202026")
    lab = get_fluview_clinical(regions=["nat"], epiweeks="202001-202026")

    from pulse.grasp_sdk import get_flusurv_net, summarize_flusurv_by_season
    rows = get_flusurv_net(locations="network_all", season="2019-20")
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from pulse.grasp_client import clear_cache as _clear_cache
from pulse.grasp_client import fetch, fluview_clinical_fetch, fluview_fetch, flusurv_fetch
from pulse.grasp_catalog import DATASETS, FLUSURV_LOCATIONS, STATE_FIPS

# Full epiweek ranges covering all available data
_FLUSURV_ALL_EPIWEEKS = "200940-202660"
_FLUVIEW_ALL_EPIWEEKS = "199740-202660"
_FLUVIEW_CLINICAL_ALL_EPIWEEKS = "201640-202660"


def _parse_year(date_str: str) -> str | None:
    """Extract a 4-digit year from IllnessOnsetDate strings like 'Mar-1993'."""
    if not date_str or date_str in ("Unknown", "Before 1993"):
        return date_str or None
    m = re.search(r"\d{4}", date_str)
    return m.group() if m else None


def _normalize_regions(regions: list[str] | str | None, default: str) -> list[str]:
    if regions is None:
        return [default]
    if isinstance(regions, str):
        return [regions]
    return list(regions)


# ── Hantavirus ─────────────────────────────────────────────────────────────────


def get_hantavirus_cases(
    state_fips: str | None = None,
    state_name: str | None = None,
    outcome: str | None = None,
    year: int | str | None = None,
) -> list[dict[str, Any]]:
    """Return individual hantavirus case records from the GRASP Case View API.

    state_fips: two-digit FIPS code e.g. '35' (New Mexico), '06' (California)
    state_name: full state name e.g. 'New Mexico' (case-insensitive)
    outcome: 'Alive', 'Dead', or 'Unknown'
    year: 4-digit year int/str, or 'Before 1993' / 'Unknown'
    """
    records = fetch(DATASETS["hantavirus"].url)

    if state_fips:
        fips = state_fips.zfill(2)
        records = [r for r in records if r.get("StateFIPS") == fips]

    if state_name:
        name_upper = state_name.upper()
        matched_fips = {k for k, v in STATE_FIPS.items() if v.upper() == name_upper}
        if not matched_fips:
            matched_fips = {k for k, v in STATE_FIPS.items() if name_upper in v.upper()}
        records = [r for r in records if r.get("StateFIPS") in matched_fips]

    if outcome:
        records = [r for r in records if r.get("Outcome", "").lower() == outcome.lower()]

    if year is not None:
        year_str = str(year)
        records = [
            r for r in records if _parse_year(r.get("IllnessOnsetDate", "")) == year_str
        ]

    for r in records:
        r["StateName"] = STATE_FIPS.get(r.get("StateFIPS", ""), "Unknown")
        r["Year"] = _parse_year(r.get("IllnessOnsetDate", ""))

    return records


def summarize_hantavirus_by_year() -> list[dict[str, Any]]:
    """Aggregate hantavirus case counts and deaths by year (or 'Before 1993'/'Unknown')."""
    records = fetch(DATASETS["hantavirus"].url)
    counts: Counter = Counter()
    deaths: Counter = Counter()
    for r in records:
        yr = _parse_year(r.get("IllnessOnsetDate", "")) or "Unknown"
        counts[yr] += 1
        if r.get("Outcome") == "Dead":
            deaths[yr] += 1

    rows = []
    for yr in sorted(counts, key=lambda y: (y.isdigit(), y)):
        rows.append({"year": yr, "cases": counts[yr], "deaths": deaths[yr]})
    return rows


def summarize_hantavirus_by_state() -> list[dict[str, Any]]:
    """Aggregate hantavirus case counts and deaths by state."""
    records = fetch(DATASETS["hantavirus"].url)
    counts: Counter = Counter()
    deaths: Counter = Counter()
    for r in records:
        fips = r.get("StateFIPS", "Unknown")
        counts[fips] += 1
        if r.get("Outcome") == "Dead":
            deaths[fips] += 1

    rows = []
    for fips in sorted(counts, key=lambda f: STATE_FIPS.get(f, f)):
        rows.append(
            {
                "state_fips": fips,
                "state": STATE_FIPS.get(fips, "Unknown"),
                "cases": counts[fips],
                "deaths": deaths[fips],
                "case_fatality_pct": round(deaths[fips] / counts[fips] * 100, 1),
            }
        )
    return sorted(rows, key=lambda r: r["cases"], reverse=True)


# ── FluView ILINet ─────────────────────────────────────────────────────────────


def get_fluview_ili(
    regions: list[str] | str | None = None,
    epiweeks: str | None = None,
) -> list[dict[str, Any]]:
    """Weekly influenza-like illness (ILI) activity from CDC's ILINet network.

    Data sourced from CDC GRASP via the CMU Delphi Epidata API.

    regions: region code(s) — default 'nat' (national)
             'nat'               — national
             'hhs1'..'hhs10'     — HHS regions
             'cen1'..'cen9'      — census regions
             lowercase state codes: 'ca', 'tx', 'ny', etc.
             Pass a list for multiple: ['nat', 'ca', 'tx']
    epiweeks: YYYYWW range e.g. '202001-202526', single week '202001',
              or None for all available data (1997-98 to present).

    Key fields per record:
        wili  — weighted ILI % (adjusted for provider sampling)
        ili   — unweighted ILI %
        num_ili, num_patients, num_providers
        num_age_0..5  — age-stratified ILI counts
    """
    regions = _normalize_regions(regions, "nat")
    records = fluview_fetch(regions, epiweeks or _FLUVIEW_ALL_EPIWEEKS)
    return sorted(records, key=lambda r: (r.get("region", ""), r.get("epiweek", 0)))


def summarize_fluview_ili_by_region(
    epiweeks: str | None = None,
) -> list[dict[str, Any]]:
    """Peak and average weighted ILI % across all queried regions for a time window.

    epiweeks: restrict to a specific epiweek range e.g. '202001-202026'
              Defaults to the full historical record.
    Returns [{region, peak_wili, avg_wili, weeks}] sorted by peak_wili desc.
    """
    all_regions = ["nat"] + [f"hhs{i}" for i in range(1, 11)] + [f"cen{i}" for i in range(1, 10)]
    records = fluview_fetch(all_regions, epiweeks or _FLUVIEW_ALL_EPIWEEKS)

    by_region: dict[str, list[float]] = defaultdict(list)
    for r in records:
        wili = r.get("wili")
        if wili is not None:
            by_region[r["region"]].append(float(wili))

    rows = []
    for region, values in sorted(by_region.items()):
        rows.append(
            {
                "region": region,
                "peak_wili": round(max(values), 2),
                "avg_wili": round(sum(values) / len(values), 2),
                "weeks": len(values),
            }
        )
    return sorted(rows, key=lambda r: r["peak_wili"], reverse=True)


# ── FluView WHO/NREVSS Clinical Labs ──────────────────────────────────────────


def get_fluview_clinical(
    regions: list[str] | str | None = None,
    epiweeks: str | None = None,
) -> list[dict[str, Any]]:
    """Weekly WHO/NREVSS clinical laboratory flu test data.

    Data sourced from CDC GRASP via the CMU Delphi Epidata API.
    Coverage: 2016-17 to present (earlier data available via fluview_public endpoint).

    regions: region code(s) — default 'nat' (national)
             Same region types as get_fluview_ili.
    epiweeks: YYYYWW range or None for all available data (2016-17 to present).

    Key fields per record:
        total_specimens   — total specimens tested
        total_a, total_b  — positive flu A and B counts
        percent_positive  — % of specimens positive for flu
        percent_a         — % positive for flu A
        percent_b         — % positive for flu B
    """
    regions = _normalize_regions(regions, "nat")
    records = fluview_clinical_fetch(regions, epiweeks or _FLUVIEW_CLINICAL_ALL_EPIWEEKS)
    return sorted(records, key=lambda r: (r.get("region", ""), r.get("epiweek", 0)))


# ── FluSurv-NET ────────────────────────────────────────────────────────────────


def get_flusurv_net(
    locations: list[str] | str | None = None,
    epiweeks: str | None = None,
    season: str | None = None,
) -> list[dict[str, Any]]:
    """FluSurv-NET weekly lab-confirmed influenza hospitalization rates per 100k.

    Data sourced from CDC GRASP via the CMU Delphi Epidata API.

    locations: location code(s) — default 'network_all' (entire network)
               Networks: 'network_all', 'network_eip', 'network_ihsp'
               States:   'CA', 'CO', 'CT', 'GA', 'MD', 'MI', 'MN',
                         'NM', 'OH', 'OR', 'TN', 'UT'
               Pass a list for multiple: ['network_all', 'CA', 'OH']
    epiweeks: YYYYWW range e.g. '202001-202526', or None for all data.
    season: filter by season string e.g. '2019-20'

    Key rate fields per record:
        rate_overall                     — all ages combined
        rate_age_0..4                    — 0-4, 5-17, 18-49, 50-64, 65+
        rate_age_5..7                    — 65-74, 75-84, 85+
        rate_flu_a, rate_flu_b           — by flu type
        rate_sex_male, rate_sex_female
        rate_race_white/black/hisp/asian/natamer
    """
    locations = _normalize_regions(locations, "network_all")
    records = flusurv_fetch(locations, epiweeks or _FLUSURV_ALL_EPIWEEKS)

    if season:
        records = [r for r in records if r.get("season") == season]

    return sorted(records, key=lambda r: (r.get("location", ""), r.get("epiweek", 0)))


def summarize_flusurv_by_season(
    location: str = "network_all",
) -> list[dict[str, Any]]:
    """Peak and average weekly hospitalization rates by flu season.

    location: FluSurv-NET location code (default: 'network_all')
    Returns [{season, location, peak_rate, avg_rate, weeks}] sorted chronologically.
    """
    records = flusurv_fetch([location], _FLUSURV_ALL_EPIWEEKS)

    by_season: dict[str, list[float]] = defaultdict(list)
    for r in records:
        rate = r.get("rate_overall")
        if rate is not None:
            by_season[r["season"]].append(float(rate))

    rows = []
    for season in sorted(by_season):
        rates = by_season[season]
        rows.append(
            {
                "season": season,
                "location": location,
                "peak_rate": round(max(rates), 1),
                "avg_rate": round(sum(rates) / len(rates), 2),
                "weeks": len(rates),
            }
        )
    return rows


def summarize_flusurv_by_location(
    epiweeks: str | None = None,
    season: str | None = None,
) -> list[dict[str, Any]]:
    """Compare peak and average hospitalization rates across all FluSurv-NET locations.

    epiweeks: restrict to a specific epiweek range e.g. '201940-202026'
    season: filter by season string e.g. '2019-20'
    Returns [{location, name, peak_rate, avg_rate, weeks}] sorted by peak rate desc.
    """
    all_locs = list(FLUSURV_LOCATIONS.keys())
    records = flusurv_fetch(all_locs, epiweeks or _FLUSURV_ALL_EPIWEEKS)

    if season:
        records = [r for r in records if r.get("season") == season]

    by_loc: dict[str, list[float]] = defaultdict(list)
    for r in records:
        rate = r.get("rate_overall")
        if rate is not None:
            by_loc[r["location"]].append(float(rate))

    rows = []
    for loc, rates in sorted(by_loc.items()):
        rows.append(
            {
                "location": loc,
                "name": FLUSURV_LOCATIONS.get(loc, loc),
                "peak_rate": round(max(rates), 1),
                "avg_rate": round(sum(rates) / len(rates), 2),
                "weeks": len(rates),
            }
        )
    return sorted(rows, key=lambda r: r["peak_rate"], reverse=True)


def clear_cache() -> None:
    _clear_cache()
