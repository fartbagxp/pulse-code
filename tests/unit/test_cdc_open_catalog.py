"""Unit tests for the CDC Open Data registry loader — reads bundled JSON, no network."""

from __future__ import annotations

from pulse.cdc_open_catalog import dataset, datasets, search


def test_loads_all_bundled_datasets():
    ds = datasets()
    assert len(ds) >= 60
    assert {d.key for d in ds} >= {"leading_death", "life_expectancy", "mortality_rates"}


def test_dataset_lookup_by_key():
    ds = dataset("leading_death")
    assert ds is not None
    assert ds.id == "bi63-dtpu"


def test_dataset_lookup_by_socrata_id():
    ds = dataset("bi63-dtpu")
    assert ds is not None
    assert ds.key == "leading_death"


def test_dataset_lookup_missing_returns_none():
    assert dataset("not-a-real-dataset") is None


def test_search_matches_name_and_description():
    results = search("obesity")
    assert any(d.key == "nhanes_obesity" for d in results)


def test_search_no_match_returns_empty():
    assert search("not-a-real-topic-xyz") == []
