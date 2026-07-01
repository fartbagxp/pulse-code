"""Dataset and query catalog loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent / "data"


@dataclass
class Measure:
    code: str
    label: str


@dataclass
class Dataset:
    id: str
    title: str
    topic: str
    subject: str
    year_start: int
    year_end: Optional[int]
    year_range_label: str
    tags: list[str]
    measures: list[Measure]
    key_groupings: list[str]
    has_template: bool
    has_aar: bool
    notes: str = ""

    @property
    def year_end_label(self) -> str:
        return str(self.year_end) if self.year_end else "present"


@dataclass
class BundledQuery:
    filename: str
    dataset_id: str
    description: str
    topic: str
    tags: list[str]
    groupings: list[str]
    year_range: str

    @property
    def stem(self) -> str:
        return self.filename.removesuffix("-req.xml")


class Catalog:
    def __init__(self) -> None:
        raw = json.loads((_DATA_DIR / "catalog.json").read_text())
        self._datasets: dict[str, Dataset] = {}
        for d in raw["datasets"]:
            measures = [Measure(**m) for m in d.get("measures", [])]
            ds = Dataset(
                id=d["id"],
                title=d["title"],
                topic=d["topic"],
                subject=d["subject"],
                year_start=d["year_start"],
                year_end=d.get("year_end"),
                year_range_label=d["year_range_label"],
                tags=d.get("tags", []),
                measures=measures,
                key_groupings=d.get("key_groupings", []),
                has_template=d.get("has_template", False),
                has_aar=d.get("has_aar", False),
                notes=d.get("notes", ""),
            )
            self._datasets[ds.id] = ds

        raw_q = json.loads((_DATA_DIR / "queries_index.json").read_text())
        self._queries: list[BundledQuery] = [
            BundledQuery(**q) for q in raw_q["queries"]
        ]

    def datasets(self) -> list[Dataset]:
        return list(self._datasets.values())

    def dataset(self, dataset_id: str) -> Optional[Dataset]:
        return self._datasets.get(dataset_id.upper())

    def queries(self) -> list[BundledQuery]:
        return self._queries

    def queries_for_dataset(self, dataset_id: str) -> list[BundledQuery]:
        return [q for q in self._queries if q.dataset_id == dataset_id.upper()]

    def topics(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for ds in self._datasets.values():
            if ds.topic not in seen:
                seen.add(ds.topic)
                result.append(ds.topic)
        return result
