"""Fuzzy keyword matching for finding the best CDC WONDER dataset or query."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pulse.catalog import BundledQuery, Catalog, Dataset

# Synonym groups — any word in a group matches any other word in that group
_SYNONYMS: list[set[str]] = [
    {"opioid", "opioids", "opiate", "opiates"},
    {"fentanyl", "synthetic opioid", "synthetic narcotic"},
    {"heroin"},
    {"drug", "drugs", "narcotic", "narcotics", "overdose"},
    {"cocaine", "coke"},
    {"meth", "methamphetamine", "amphetamine", "stimulant", "psychostimulant"},
    {
        "death",
        "deaths",
        "mortality",
        "die",
        "dying",
        "fatal",
        "fatality",
        "fatalities",
        "kill",
    },
    {"birth", "births", "natality", "born", "fertility", "fertilit"},
    {"infant", "neonatal", "neonate", "baby", "babies", "newborn", "SIDS"},
    {"maternal", "mother", "pregnancy", "pregnant", "childbirth", "obstetric"},
    {"suicide", "suicidal", "self-harm", "self harm"},
    {"cancer", "tumor", "neoplasm", "oncology"},
    {"heart", "cardiac", "cardiovascular", "coronary"},
    {"race", "racial", "ethnicity", "ethnic", "disparity", "disparities", "equity"},
    {"vaccine", "vaccination", "immunization", "vaers", "adverse event"},
    {"covid", "COVID", "COVID-19", "coronavirus", "pandemic"},
    {"tick", "lyme", "lyme disease", "rocky mountain", "anaplasmosis", "ehrlichiosis"},
    {
        "environment",
        "environmental",
        "climate",
        "temperature",
        "heat",
        "air quality",
        "pollution",
        "PM2.5",
        "precipitation",
        "rain",
    },
    {
        "cancer",
        "tumor",
        "neoplasm",
        "oncology",
        "malignant",
        "carcinoma",
        "leukemia",
        "lymphoma",
        "breast cancer",
        "lung cancer",
        "colorectal",
        "prostate",
    },
    {
        "STD",
        "STI",
        "chlamydia",
        "gonorrhea",
        "syphilis",
        "sexually transmitted",
        "sexual health",
    },
    {"tuberculosis", "TB", "OTIS", "MDR-TB", "drug-resistant TB"},
    {"fetal death", "stillbirth", "fetal", "stillborn"},
    {"AIDS", "HIV", "epidemic"},
    {"population", "census", "demographics", "projections", "estimates", "denominator"},
    {"sex", "gender", "male", "female"},
    {"state", "states", "county", "counties", "geographic", "geography", "region"},
    {"year", "annual", "yearly", "trend", "trends"},
    {"month", "monthly", "seasonal"},
    {"age", "ages", "age group", "elderly", "children", "young"},
    {"provisional", "recent", "latest", "current"},
    {"historical", "history", "long-term"},
]

# Build reverse lookup: word -> synonym set index
_WORD_TO_GROUP: dict[str, int] = {}
for _i, _group in enumerate(_SYNONYMS):
    for _word in _group:
        _WORD_TO_GROUP[_word.lower()] = _i


def _tokenize(text: str) -> set[str]:
    """Extract tokens and expand synonyms into group IDs."""
    raw_tokens = set(re.findall(r"[a-zA-Z0-9.]+", text.lower()))
    expanded: set[str] = set(raw_tokens)
    for token in raw_tokens:
        idx = _WORD_TO_GROUP.get(token)
        if idx is not None:
            expanded.add(f"__group_{idx}__")
    return expanded


def _score(prompt_tokens: set[str], item_tokens: set[str]) -> float:
    """Jaccard-like overlap score, weighted by token count."""
    if not item_tokens:
        return 0.0
    intersection = prompt_tokens & item_tokens
    union = prompt_tokens | item_tokens
    return len(intersection) / len(union)


@dataclass
class DatasetMatch:
    dataset: Dataset
    score: float
    reason: str


@dataclass
class QueryMatch:
    query: BundledQuery
    score: float


def _year_coverage_bonus(prompt: str, ds: "Dataset") -> float:
    """Boost score if the dataset's year range covers years mentioned in the prompt."""
    import re as _re

    years = [int(y) for y in _re.findall(r"\b(19\d{2}|20\d{2})\b", prompt)]
    if not years:
        return 0.0
    year_end = ds.year_end or 2026
    covered = sum(1 for y in years if ds.year_start <= y <= year_end)
    return 0.15 * covered / len(years)


def match_datasets(prompt: str, catalog: Catalog, top_n: int = 5) -> list[DatasetMatch]:
    """Return top-N datasets matching the prompt, scored by keyword overlap."""
    prompt_tokens = _tokenize(prompt)
    results: list[DatasetMatch] = []

    for ds in catalog.datasets():
        item_tokens = _tokenize(
            " ".join([ds.title, ds.topic, ds.subject, ds.year_range_label] + ds.tags)
        )
        score = _score(prompt_tokens, item_tokens) + _year_coverage_bonus(prompt, ds)
        reason = _build_reason(prompt_tokens, item_tokens, ds)
        results.append(DatasetMatch(dataset=ds, score=score, reason=reason))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_n]


def match_queries(prompt: str, catalog: Catalog, top_n: int = 5) -> list[QueryMatch]:
    """Return top-N bundled queries matching the prompt."""
    prompt_tokens = _tokenize(prompt)
    results: list[QueryMatch] = []

    for q in catalog.queries():
        item_tokens = _tokenize(
            " ".join(
                [q.description, q.topic, q.year_range, q.dataset_id]
                + q.tags
                + q.groupings
            )
        )
        score = _score(prompt_tokens, item_tokens)
        results.append(QueryMatch(query=q, score=score))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_n]


def _build_reason(prompt_tokens: set[str], item_tokens: set[str], ds: Dataset) -> str:
    matched = [t for t in ds.tags if _tokenize(t) & prompt_tokens]
    if matched:
        return f"Matched: {', '.join(matched[:4])}"
    return f"{ds.year_range_label} | {ds.topic}"
