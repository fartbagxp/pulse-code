"""
CDC Open Data client — Socrata SODA API for data.cdc.gov

API docs: https://dev.socrata.com/foundry/data.cdc.gov/
No auth required; set CDC_DATA_APP_TOKEN env var for higher rate limits (1000 → 20000 req/hr).
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

BASE_URL = "https://data.cdc.gov/resource"
_CACHE_TTL = 24 * 3600  # 24 hours — CDC data updates slowly


class SodaClient:
    """HTTP client for the data.cdc.gov Socrata SODA API."""

    def __init__(self, app_token: str | None = None, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        token = app_token or os.environ.get("CDC_DATA_APP_TOKEN")
        if token:
            self.session.headers["X-App-Token"] = token
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    def get(
        self,
        dataset_id: str,
        where: str | None = None,
        select: str | None = None,
        group: str | None = None,
        order: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Execute a SODA query against a dataset.

        Args:
            dataset_id: Socrata dataset ID, e.g. "bi63-dtpu"
            where: SODA $where clause, e.g. "year = '2021' AND state = 'New York'"
            select: SODA $select clause, e.g. "year, state, deaths"
            group: SODA $group clause, e.g. "year, state"
            order: SODA $order clause, e.g. "year DESC"
            limit: Max rows to return (default 1000)

        Returns:
            List of row dicts

        Raises:
            requests.HTTPError: on non-2xx response
        """
        cache_key = f"{dataset_id}|{where}|{select}|{group}|{order}|{limit}"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if now - ts < _CACHE_TTL:
                return data

        params: dict[str, str | int] = {"$limit": limit}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        if group:
            params["$group"] = group
        if order:
            params["$order"] = order

        url = f"{BASE_URL}/{dataset_id}.json"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        self._cache[cache_key] = (now, data)
        return data

    def clear_cache(self) -> None:
        self._cache.clear()
