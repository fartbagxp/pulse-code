"""
SEER*Explorer client — cancer incidence/mortality statistics from NCI SEER.

Data source: https://seer.cancer.gov/statistics-network/explorer/
No authentication required. This calls the same JSON endpoints the SEER*Explorer
web app uses to render its charts (undocumented, but public and unauthenticated).

Key endpoints:
    source/content_writers/get_var_formats.php  — variable label catalog (cancer
        sites, sex, race, age ranges, stage, rate types, ...)
    source/content_writers/render_region_5.php  — chart/trend data

Response bodies are JSON-encoded twice (a JSON string containing JSON) — `_get`
unwraps both layers.
"""

from __future__ import annotations

import json
import time
from typing import Any

import requests

BASE_URL = "https://seer.cancer.gov/statistics-network/explorer/source/content_writers/"
_CACHE_TTL = 24 * 3600  # 24 hours


class SeerClient:
    """HTTP client for the SEER*Explorer JSON endpoints."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        self._cache: dict[str, tuple[float, Any]] = {}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        cache_key = f"{path}|{json.dumps(params or {}, sort_keys=True)}"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if now - ts < _CACHE_TTL:
                return data

        resp = self.session.get(
            f"{BASE_URL}{path}", params=params, timeout=self.timeout
        )
        resp.raise_for_status()
        body = resp.json()
        # Some endpoints double-encode the JSON body as a string.
        if isinstance(body, str):
            body = json.loads(body)

        self._cache[cache_key] = (now, body)
        return body

    def get_var_formats(self) -> dict[str, Any]:
        """Fetch the full variable label catalog: cancer sites, sex, race, age
        ranges, stage, rate/data/graph types, year ranges, etc.

        Returns {"VariableFormats": {...}, "CancerSites": [...]}.
        """
        return self._get("get_var_formats.php")

    def get_chart_data(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch chart/trend data for a given parameter set.

        Returns {"info": {...}, "data": {<series-key>: {"data_series": [...], ...}}}.
        See pulse.seer_sdk for a higher-level interface.
        """
        return self._get("render_region_5.php", params=params)

    def clear_cache(self) -> None:
        self._cache.clear()
