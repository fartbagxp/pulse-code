"""
Per-source dataset/URL/credit adapters — what `pulse source <source>` drills into.

Each function below is a thin view over an existing catalog module: no new
data is invented, just normalized into (key, title, url, years, credit) rows
so every source can be browsed the same way regardless of how its native
catalog is shaped. URLs are real, constructible endpoints already used
elsewhere in this codebase (e.g. wonder_client.BASE_URL, grasp_catalog's
per-dataset url, nis_catalog's per-year dat_url/format_url) — not guesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pulse.catalog import Catalog
from pulse.cdc_open_catalog import datasets as _cdc_open_datasets
from pulse.grasp_catalog import DATASETS as _GRASP_DATASETS
from pulse.nis_catalog import SURVEY_YEARS as _NIS_SURVEY_YEARS
from pulse.nssp_client import SIGNALS as _NSSP_SIGNALS
from pulse.seer_catalog import cancer_sites as _seer_cancer_sites
from pulse.wisqars_catalog import DATASETS as _WISQARS_DATASETS
from pulse.wonder_client import WonderClient


@dataclass(frozen=True)
class SourceDataset:
    key: str
    title: str
    url: str
    years: str
    credit: str
    notes: str = ""


def wonder_source_datasets() -> list[SourceDataset]:
    catalog = Catalog()
    return [
        SourceDataset(
            key=d.id,
            title=d.title,
            url=f"{WonderClient.BASE_URL}/{d.id}",
            years=d.year_range_label,
            credit="CDC/NCHS — CDC WONDER",
            notes=d.topic,
        )
        for d in catalog.datasets()
    ]


def seer_source_datasets() -> list[SourceDataset]:
    sites = _seer_cancer_sites()
    return [
        SourceDataset(
            key=code,
            title=label,
            url="https://seer.cancer.gov/statistics-network/explorer/",
            years="1975–present",
            credit="NCI — SEER Program",
        )
        for code, label in sorted(sites.items(), key=lambda kv: kv[1])
    ]


def cdc_open_source_datasets() -> list[SourceDataset]:
    return [
        SourceDataset(
            key=d.key,
            title=d.name,
            url=f"https://data.cdc.gov/d/{d.id}",
            years=d.years,
            credit="CDC — data.cdc.gov",
        )
        for d in _cdc_open_datasets()
    ]


def wisqars_source_datasets() -> list[SourceDataset]:
    return [
        SourceDataset(
            key=key,
            title=d.name,
            url=f"https://data.cdc.gov/d/{d.id}",
            years=d.years,
            credit="CDC/NCHS — WISQARS",
        )
        for key, d in _WISQARS_DATASETS.items()
    ]


def grasp_source_datasets() -> list[SourceDataset]:
    return [
        SourceDataset(
            key=key,
            title=d.name,
            url=d.url,
            years=d.years,
            credit="CDC/ATSDR — GRASP",
        )
        for key, d in _GRASP_DATASETS.items()
    ]


def nssp_source_datasets() -> list[SourceDataset]:
    return [
        SourceDataset(
            key=key,
            title=f"NSSP ED visit signal: {signal}",
            url=f"https://api.delphi.cmu.edu/epidata/covidcast/?signal=nssp:{signal}",
            years="2022–present",
            credit="CDC — NSSP (via CMU Delphi Epidata)",
        )
        for key, signal in _NSSP_SIGNALS.items()
    ]


def nis_source_datasets() -> list[SourceDataset]:
    rows: list[SourceDataset] = []
    for survey, years in _NIS_SURVEY_YEARS.items():
        for year, entry in sorted(years.items()):
            rows.append(
                SourceDataset(
                    key=f"{survey}-{year}",
                    title=f"NIS-{survey.capitalize()} {year} public-use file",
                    url=entry.dat_url,
                    years=str(year),
                    credit="CDC/NCHS — National Immunization Survey",
                    notes=f"format: {entry.format_type} ({entry.format_url})",
                )
            )
    return rows


SOURCE_DATASET_FNS: dict[str, Callable[[], list[SourceDataset]]] = {
    "wonder": wonder_source_datasets,
    "seer": seer_source_datasets,
    "cdc-open": cdc_open_source_datasets,
    "wisqars": wisqars_source_datasets,
    "grasp": grasp_source_datasets,
    "nssp": nssp_source_datasets,
    "nis": nis_source_datasets,
}
