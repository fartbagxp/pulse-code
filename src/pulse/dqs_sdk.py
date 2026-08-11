"""NCHS DQS SDK — thin high-level API over the shared DQS Socrata schema.

Every DQS dataset (see dqs_catalog.py) is queryable through the same Socrata
endpoint and shares one column layout, so a single generic `query()` covers all
of them. `trend()` is a convenience over that: it pulls the all-persons ("Total")
national series for a dataset, sorted by time period — the most common thing you
want from a "Health, United States" table.

All queries hit the live data.cdc.gov API via SodaClient; nothing is cached to
disk. Values come back as strings exactly as Socrata returns them.
"""

from __future__ import annotations

from typing import Any, Optional

from pulse.dqs_catalog import DqsDataset, dataset as _lookup
from pulse.soda_client import SodaClient

# The columns every DQS table shares — handy default projection for trends.
# `group` is a SoQL reserved word, so it must be backtick-quoted in a $select
# (Socrata returns a 400 "malformed" otherwise); the others are plain.
CORE_COLUMNS = [
    "topic",
    "subtopic",
    "classification",
    "`group`",
    "subgroup",
    "estimate_type",
    "time_period",
    "estimate",
    "standard_error",
    "estimate_lci",
    "estimate_uci",
]


def resolve(key_or_id: str) -> tuple[str, Optional[DqsDataset]]:
    """Resolve a registry key or Socrata ID to (socrata_id, dataset-or-None)."""
    ds = _lookup(key_or_id)
    return (ds.id if ds else key_or_id), ds


def query(
    key_or_id: str,
    where: Optional[str] = None,
    select: Optional[str] = None,
    group: Optional[str] = None,
    order: Optional[str] = None,
    limit: int = 1000,
    client: Optional[SodaClient] = None,
) -> list[dict[str, Any]]:
    """Run a raw SODA query against a DQS dataset (by key or Socrata ID)."""
    socrata_id, _ = resolve(key_or_id)
    client = client or SodaClient()
    return client.get(
        dataset_id=socrata_id,
        where=where,
        select=select,
        group=group,
        order=order,
        limit=limit,
    )


def trend(
    key_or_id: str,
    estimate_type: Optional[str] = None,
    limit: int = 1000,
    client: Optional[SodaClient] = None,
) -> list[dict[str, Any]]:
    """
    All-persons national trend for a DQS dataset, oldest→newest.

    Filters to the "Total" classification (the all-persons row, not a demographic
    cut) and projects the core columns. `estimate_type` optionally narrows to one
    measure when a dataset publishes several (e.g. crude vs. age-adjusted rates).
    """
    where = "classification = 'Total'"
    if estimate_type:
        safe = estimate_type.replace("'", "''")
        where += f" AND estimate_type = '{safe}'"
    return query(
        key_or_id,
        where=where,
        select=", ".join(CORE_COLUMNS),
        order="time_period ASC",
        limit=limit,
        client=client,
    )


def estimate_types(key_or_id: str, client: Optional[SodaClient] = None) -> list[str]:
    """Distinct estimate_type values published by a dataset (the measures it offers)."""
    rows = query(
        key_or_id,
        select="estimate_type",
        group="estimate_type",
        limit=200,
        client=client,
    )
    return sorted({r.get("estimate_type", "") for r in rows if r.get("estimate_type")})
