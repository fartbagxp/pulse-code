"""Unit tests for the keyword/synonym matcher — pure functions, no network."""

from __future__ import annotations

from pulse.catalog import Catalog
from pulse.matcher import match_datasets, match_queries


def test_match_datasets_finds_opioid_dataset_for_synonym():
    catalog = Catalog()
    matches = match_datasets("opioid overdose deaths by state", catalog, top_n=5)
    assert matches
    assert matches[0].score > 0
    # top match should be a mortality dataset (D176 is the default recent one)
    assert any(m.dataset.topic == "Mortality" for m in matches)


def test_match_datasets_respects_top_n():
    catalog = Catalog()
    assert len(match_datasets("deaths", catalog, top_n=3)) <= 3
    assert len(match_datasets("deaths", catalog, top_n=10)) <= 10


def test_match_datasets_year_coverage_bonus_prefers_covering_dataset():
    catalog = Catalog()
    # D8 (VAERS, 1990-present) vs a query mentioning a year only D8 covers well
    matches = match_datasets("vaccine adverse events 1995", catalog, top_n=3)
    assert matches[0].dataset.id == "D8"


def test_match_datasets_empty_prompt_still_returns_ranked_list():
    catalog = Catalog()
    matches = match_datasets("", catalog, top_n=5)
    assert len(matches) == 5
    assert all(m.score == 0.0 for m in matches)


def test_match_queries_finds_relevant_bundled_query():
    catalog = Catalog()
    matches = match_queries("tuberculosis cases by year", catalog, top_n=3)
    assert matches
    assert matches[0].query.dataset_id == "D202"


def test_match_queries_scores_are_sorted_descending():
    catalog = Catalog()
    matches = match_queries("drug overdose deaths", catalog, top_n=10)
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)
