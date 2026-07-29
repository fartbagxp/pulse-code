"""
NSSP client — Delphi Epidata API for NSSP emergency department visit signals.

API docs: https://cmu-delphi.github.io/delphi-epidata/api/covidcast-signals/nssp.html
No authentication required. Time values use epiweek format: YYYYWW (e.g. 202501 = week 1 of 2025).
"""

from __future__ import annotations

import datetime
import time
from typing import Any

import requests

BASE_URL = "https://api.delphi.cmu.edu/epidata/covidcast/"
_CACHE_TTL = 24 * 3600  # 24 hours

SIGNALS = {
    "covid": "pct_ed_visits_covid",
    "influenza": "pct_ed_visits_influenza",
    "rsv": "pct_ed_visits_rsv",
    "combined": "pct_ed_visits_combined",
}

GEO_TYPES = {"nation", "state", "county", "msa", "hrr", "hhs"}


def _current_epiweek() -> int:
    """Approximate current MMWR epiweek as YYYYWW using ISO week (close enough for defaults)."""
    today = datetime.date.today()
    iso = today.isocalendar()
    return iso.year * 100 + iso.week


def _epiweeks_ago(n: int) -> int:
    """Return approximate epiweek N weeks before today."""
    past = datetime.date.today() - datetime.timedelta(weeks=n)
    iso = past.isocalendar()
    return iso.year * 100 + iso.week


class DelphiClient:
    """HTTP client for the CMU Delphi Epidata COVIDcast API."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    def get(
        self,
        signal: str,
        geo_type: str = "state",
        geo_value: str = "*",
        time_values: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query a COVIDcast NSSP signal.

        Args:
            signal: Signal name e.g. 'pct_ed_visits_covid'
            geo_type: Geographic resolution — 'nation', 'state', 'county', 'hhs'
            geo_value: '*' for all, or specific e.g. 'ca' (state), '06' (FIPS), '1'-'10' (HHS), 'us' (nation)
            time_values: Epiweek range YYYYWW e.g. '202501-202520', or single week '202518'.
                         Defaults to the last 52 weeks if omitted.

        Returns:
            List of row dicts: geo_value, time_value (YYYYWW), value, direction, issue, lag
        """
        if time_values is None:
            time_values = f"{_epiweeks_ago(52)}-{_current_epiweek()}"

        cache_key = f"{signal}|{geo_type}|{geo_value}|{time_values}"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if now - ts < _CACHE_TTL:
                return data

        params: dict[str, str] = {
            "data_source": "nssp",
            "signal": signal,
            "time_type": "week",
            "geo_type": geo_type,
            "geo_value": geo_value,
            "time_values": time_values,
        }

        resp = self.session.get(BASE_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()

        if body.get("result") != 1:
            raise ValueError(f"Delphi API error: {body.get('message', 'unknown error')}")

        data = body.get("epidata", [])
        self._cache[cache_key] = (now, data)
        return data

    def clear_cache(self) -> None:
        self._cache.clear()
