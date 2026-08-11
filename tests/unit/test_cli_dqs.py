"""CLI + catalog tests for the `dqs` (NCHS Data Query System) source.

Catalog-backed commands (bare listing, `list`) read the in-module registry only,
no network. Live-query commands (`query`, `trend`) monkeypatch the SDK call so the
default test run stays offline; the real Socrata wiring is exercised manually.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

import pulse.cli as cli
from pulse.cli import app
from pulse.dqs_catalog import dataset, datasets, search, topics

runner = CliRunner()


# ── catalog ───────────────────────────────────────────────────────────────────


def test_catalog_has_28_datasets():
    assert len(datasets()) == 28


def test_catalog_lookup_by_key_and_id():
    by_key = dataset("drug-overdose-deaths")
    assert by_key is not None
    assert by_key.id == "rdjz-vn2n"
    # same dataset resolvable by Socrata ID
    assert dataset("rdjz-vn2n") is by_key


def test_catalog_search_matches_topic_and_name():
    hits = {d.key for d in search("cholesterol")}
    assert "cholesterol-adults" in hits
    hits2 = {d.key for d in search("long-term")}
    assert {"ltc-providers", "ltc-users"} <= hits2


def test_catalog_topics_are_relevance_ordered():
    ts = topics()
    assert ts[0] == "Mortality"
    assert "Long-Term Care" in ts


# ── list / bare listing ───────────────────────────────────────────────────────


def test_dqs_bare_lists_datasets():
    result = runner.invoke(app, ["source", "dqs"])
    assert result.exit_code == 0
    assert "data.cdc.gov" in result.stdout


def test_dqs_list_json_is_valid_and_complete():
    result = runner.invoke(app, ["source", "dqs", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 28
    row = next(d for d in data if d["key"] == "drug-overdose-deaths")
    assert row["id"] == "rdjz-vn2n"
    assert row["survey"] == "NVSS"
    assert "dimensions" in row


def test_dqs_list_topic_filter():
    result = runner.invoke(app, ["source", "dqs", "list", "--topic", "Chronic Disease", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    keys = {d["key"] for d in data}
    assert {"cholesterol-adults", "hypertension-adults", "chronic-conditions"} == keys


def test_dqs_list_search_filter():
    result = runner.invoke(app, ["source", "dqs", "list", "--search", "spending", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    keys = {d["key"] for d in data}
    assert {"national-health-spending", "personal-healthcare-spending"} == keys


# ── query / trend (SDK monkeypatched) ─────────────────────────────────────────


def test_dqs_query_calls_sdk_with_resolved_key(monkeypatch):
    captured = {}

    def fake_query(key_or_id, **kwargs):
        captured["key"] = key_or_id
        captured.update(kwargs)
        return [{"time_period": "2022", "estimate": "32.4"}]

    monkeypatch.setattr(cli, "dqs_query", fake_query)

    result = runner.invoke(
        app,
        ["source", "dqs", "query", "drug-overdose-deaths", "--where", "classification='Total'", "-f", "json"],
    )
    assert result.exit_code == 0
    assert captured["key"] == "drug-overdose-deaths"
    assert captured["where"] == "classification='Total'"
    assert json.loads(result.stdout) == [{"time_period": "2022", "estimate": "32.4"}]


def test_dqs_trend_calls_sdk_and_prints(monkeypatch):
    def fake_trend(key_or_id, estimate_type=None, limit=1000):
        return [{"time_period": "2018", "estimate": "20.7"}, {"time_period": "2024", "estimate": "23.3"}]

    monkeypatch.setattr(cli, "dqs_trend", fake_trend)

    result = runner.invoke(app, ["source", "dqs", "trend", "drug-overdose-deaths", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["time_period"] == "2018"
    assert data[-1]["estimate"] == "23.3"


def test_dqs_trend_empty_result_exits_nonzero(monkeypatch):
    monkeypatch.setattr(cli, "dqs_trend", lambda *a, **k: [])
    result = runner.invoke(app, ["source", "dqs", "trend", "oral-health"])
    assert result.exit_code == 1


def test_dqs_trend_list_measures(monkeypatch):
    monkeypatch.setattr(cli, "dqs_estimate_types", lambda *a, **k: ["mg/dL, age adjusted", "mg/dL, crude"])
    result = runner.invoke(app, ["source", "dqs", "trend", "cholesterol-adults", "--list-measures"])
    assert result.exit_code == 0
    assert "mg/dL, age adjusted" in result.stdout


# ── overview integration ──────────────────────────────────────────────────────


def test_dqs_appears_in_source_overview():
    result = runner.invoke(app, ["source", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    dqs = next(s for s in data if s["name"] == "DQS")
    assert dqs["count"] == 28
