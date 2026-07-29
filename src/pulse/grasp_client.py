"""
Low-level HTTP client for ATSDR GRASP APIs at gis.cdc.gov/grasp/ and the
CMU Delphi Epidata API at api.delphi.cmu.edu/epidata/.

GRASP endpoints return a JSON object with a top-level "Data" array.
The Delphi Epidata API wraps GRASP's FluView/FluSurv data with a cleaner REST interface.
No authentication or API key is required for either.
"""

from __future__ import annotations

import time
from typing import Any

import requests

_SESSION: requests.Session | None = None
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 86_400  # 24 hours

_DELPHI_BASE = "https://api.delphi.cmu.edu/epidata"


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({"Accept": "application/json"})
    return _SESSION


def fetch(url: str) -> list[dict[str, Any]]:
    """Fetch a GRASP endpoint and return the records from the top-level Data array."""
    now = time.time()
    if url in _CACHE:
        ts, data = _CACHE[url]
        if now - ts < _CACHE_TTL:
            return data

    resp = _get_session().get(url, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    # All known GRASP endpoints wrap records under a "Data" key
    data = payload.get("Data", payload) if isinstance(payload, dict) else payload
    _CACHE[url] = (now, data)
    return data


def _delphi_get(
    endpoint: str,
    params: dict[str, str],
    cache_key: str,
) -> list[dict[str, Any]]:
    """Generic Delphi Epidata GET with caching and error handling."""
    now = time.time()
    if cache_key in _CACHE:
        ts, data = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    resp = _get_session().get(f"{_DELPHI_BASE}/{endpoint}/", params=params, timeout=60)
    resp.raise_for_status()
    body = resp.json()

    if body.get("result") not in (1, 2):
        raise ValueError(f"Delphi {endpoint} API error: {body.get('message', 'unknown')}")

    data = body.get("epidata", [])
    _CACHE[cache_key] = (now, data)
    return data


def flusurv_fetch(locations: list[str], epiweeks: str) -> list[dict[str, Any]]:
    """Fetch FluSurv-NET records from the CMU Delphi Epidata API.

    locations: list of FluSurv location codes e.g. ['network_all', 'CA', 'OH']
    epiweeks: epiweek range string e.g. '200940-202626' or single week '202001'

    Returns weekly hospitalization rate records with fields:
    location, season, epiweek, issue, lag, rate_overall, rate_age_0..7,
    rate_race_*, rate_sex_*, rate_flu_a, rate_flu_b
    """
    cache_key = f"flusurv:{','.join(sorted(loc.lower() for loc in locations))}:{epiweeks}"
    return _delphi_get(
        "flusurv", {"locations": ",".join(locations), "epiweeks": epiweeks}, cache_key
    )


def fluview_fetch(regions: list[str], epiweeks: str) -> list[dict[str, Any]]:
    """Fetch ILINet influenza-like illness records from the CMU Delphi Epidata API.

    regions: list of region codes — 'nat', 'hhs1'..'hhs10', 'cen1'..'cen9',
             or lowercase 2-letter state codes e.g. ['nat', 'ca', 'tx']
    epiweeks: epiweek range string e.g. '199740-202626' or single week '202001'

    Returns weekly ILI records with fields:
    region, epiweek, wili (weighted ILI %), ili, num_ili, num_patients,
    num_providers, num_age_0..5
    """
    cache_key = f"fluview:{','.join(sorted(r.lower() for r in regions))}:{epiweeks}"
    return _delphi_get(
        "fluview", {"regions": ",".join(regions), "epiweeks": epiweeks}, cache_key
    )


def fluview_clinical_fetch(regions: list[str], epiweeks: str) -> list[dict[str, Any]]:
    """Fetch WHO/NREVSS clinical lab data from the CMU Delphi Epidata API.

    regions: list of region codes — same set as fluview_fetch
    epiweeks: epiweek range string e.g. '201640-202626' or single week '202001'

    Returns weekly lab records with fields:
    region, epiweek, total_specimens, total_a, total_b,
    percent_positive, percent_a, percent_b
    """
    cache_key = f"fluview_clinical:{','.join(sorted(r.lower() for r in regions))}:{epiweeks}"
    return _delphi_get(
        "fluview_clinical", {"regions": ",".join(regions), "epiweeks": epiweeks}, cache_key
    )


def clear_cache() -> None:
    _CACHE.clear()
