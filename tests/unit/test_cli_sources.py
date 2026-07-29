"""CLI smoke tests for the `seer` and `cdc-open` sub-apps.

Catalog-backed commands (sites, list) hit bundled JSON only, no network.
Live-query commands (mortality, query) monkeypatch the SDK/client call so no
network access is required here either — network wiring itself is exercised
manually against the real APIs, not in the default test run.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

import pulse.cli as cli
from pulse.cli import app

runner = CliRunner()


# ── seer ──────────────────────────────────────────────────────────────────────


def test_seer_sites_lists_known_site():
    result = runner.invoke(app, ["seer", "sites"])
    assert result.exit_code == 0
    assert "Breast" in result.stdout


def test_seer_sites_search_filters():
    result = runner.invoke(app, ["seer", "sites", "--search", "breast"])
    assert result.exit_code == 0
    assert "Breast" in result.stdout


def test_seer_sites_json_output_is_valid():
    result = runner.invoke(app, ["seer", "sites", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(s["code"] == "55" for s in data)


def test_seer_mortality_calls_sdk_and_prints_json(monkeypatch):
    captured = {}

    def fake_get_mortality_trend(**kwargs):
        captured.update(kwargs)
        return [{"year": "2020", "rate": 26.6}]

    monkeypatch.setattr(cli, "get_mortality_trend", fake_get_mortality_trend)

    result = runner.invoke(app, ["seer", "mortality", "--site", "55", "-f", "json"])
    assert result.exit_code == 0
    assert captured["site"] == 55
    data = json.loads(result.stdout)
    assert data == [{"year": "2020", "rate": 26.6}]


# ── cdc-open ──────────────────────────────────────────────────────────────────


def test_cdc_open_list_shows_known_dataset():
    result = runner.invoke(app, ["cdc-open", "list"])
    assert result.exit_code == 0
    assert "leading_death" in result.stdout


def test_cdc_open_list_search_filters():
    result = runner.invoke(app, ["cdc-open", "list", "--search", "obesity"])
    assert result.exit_code == 0
    assert "obesity" in result.stdout.lower()


def test_cdc_open_query_resolves_registry_key_and_prints_json(monkeypatch):
    captured = {}

    def fake_get(self, **kwargs):
        captured.update(kwargs)
        return [{"year": "2015", "deaths": "2552"}]

    monkeypatch.setattr(cli.SodaClient, "get", fake_get)

    result = runner.invoke(app, ["cdc-open", "query", "leading_death", "-f", "json"])
    assert result.exit_code == 0
    assert captured["dataset_id"] == "bi63-dtpu"
    data = json.loads(result.stdout)
    assert data == [{"year": "2015", "deaths": "2552"}]


def test_cdc_open_query_passes_through_unknown_id_verbatim(monkeypatch):
    captured = {}

    def fake_get(self, **kwargs):
        captured.update(kwargs)
        return [{"x": 1}]

    monkeypatch.setattr(cli.SodaClient, "get", fake_get)

    result = runner.invoke(app, ["cdc-open", "query", "some-raw-id", "-f", "json"])
    assert result.exit_code == 0
    assert captured["dataset_id"] == "some-raw-id"
