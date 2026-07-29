"""CDC Open Data (data.cdc.gov) dataset registry — loaded from the bundled
snapshot at data/cdc_open_catalog.json.

Each entry describes a Socrata dataset: its ID, human-readable name,
description, date coverage, and key queryable columns. This is a reference
catalog for discovery (`pulse cdc-open list`) — actual queries go straight to
the live API via SodaClient, so the data itself is never stale even if a
dataset's metadata here drifts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_CATALOG_PATH = Path(__file__).parent / "data" / "cdc_open_catalog.json"


@dataclass(frozen=True)
class CdcOpenDataset:
    key: str
    id: str
    name: str
    description: str
    years: str
    key_columns: list[str]


_datasets: dict[str, CdcOpenDataset] | None = None


def _load() -> dict[str, CdcOpenDataset]:
    global _datasets
    if _datasets is None:
        raw = json.loads(_CATALOG_PATH.read_text())
        _datasets = {
            d["key"]: CdcOpenDataset(
                key=d["key"],
                id=d["id"],
                name=d["name"],
                description=d["description"],
                years=d["years"],
                key_columns=d.get("key_columns", []),
            )
            for d in raw["datasets"]
        }
    return _datasets


def datasets() -> list[CdcOpenDataset]:
    return list(_load().values())


def dataset(key_or_id: str) -> Optional[CdcOpenDataset]:
    """Look up by registry key (e.g. 'leading_death') or Socrata ID (e.g. 'bi63-dtpu')."""
    by_key = _load()
    if key_or_id in by_key:
        return by_key[key_or_id]
    for ds in by_key.values():
        if ds.id == key_or_id:
            return ds
    return None


def search(query: str) -> list[CdcOpenDataset]:
    """Case-insensitive substring search over name/description/key."""
    q = query.lower()
    return [
        ds
        for ds in datasets()
        if q in ds.name.lower() or q in ds.description.lower() or q in ds.key.lower()
    ]
