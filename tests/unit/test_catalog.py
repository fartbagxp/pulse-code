"""Unit tests for the dataset/query catalog loader — reads bundled JSON, no network."""

from __future__ import annotations

from pulse.catalog import Catalog


def test_loads_all_bundled_datasets():
    catalog = Catalog()
    datasets = catalog.datasets()
    assert len(datasets) >= 38
    assert {d.id for d in datasets} >= {"D176", "D202", "D204", "D178", "D117", "D128"}


def test_dataset_lookup_is_case_insensitive():
    catalog = Catalog()
    assert catalog.dataset("d176") is not None
    assert catalog.dataset("D176") is not None
    assert catalog.dataset("d176").id == "D176"


def test_dataset_lookup_missing_returns_none():
    assert Catalog().dataset("D99999") is None


def test_queries_for_dataset_filters_correctly():
    catalog = Catalog()
    queries = catalog.queries_for_dataset("D176")
    assert queries
    assert all(q.dataset_id == "D176" for q in queries)


def test_queries_for_dataset_no_matches_returns_empty_list():
    catalog = Catalog()
    assert catalog.queries_for_dataset("D99999") == []


def test_topics_are_deduplicated_and_ordered():
    catalog = Catalog()
    topics = catalog.topics()
    assert len(topics) == len(set(topics))
    assert "Mortality" in topics


def test_d202_has_measures_but_no_base_template():
    """D202 (Tuberculosis) has no `-base.xml` template file — llm_builder
    falls back to merging onto a bundled query instead (see
    test_llm_builder.py::test_finalize_request_falls_back_to_bundled_query)."""
    ds = Catalog().dataset("D202")
    assert ds.has_template is False
    codes = {m.code for m in ds.measures}
    assert "D202.M1" in codes


def test_previously_unsupported_datasets_now_resolve_a_template():
    """Sanity check the 4 datasets that previously had neither a template
    nor a bundled query (D204/D178/D117/D128) now resolve one or the other."""
    catalog = Catalog()
    for ds_id in ("D204", "D178", "D117", "D128"):
        ds = catalog.dataset(ds_id)
        has_bundled_query = bool(catalog.queries_for_dataset(ds_id))
        assert ds.has_template or has_bundled_query, ds_id
