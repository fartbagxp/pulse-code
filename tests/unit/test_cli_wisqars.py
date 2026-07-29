"""CLI smoke tests for the `wisqars` sub-app.

`list` reads the static in-code registry, no network. The query commands
monkeypatch the SDK call so no network access is required here either.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

import pulse.cli as cli
from pulse.cli import app

runner = CliRunner()


def test_wisqars_list_shows_known_dataset():
    result = runner.invoke(app, ["wisqars", "list"])
    assert result.exit_code == 0
    assert "injury_mortality" in result.stdout


def test_wisqars_list_json_output_is_valid():
    result = runner.invoke(app, ["wisqars", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(d["key"] == "injury_mortality" for d in data)


def test_wisqars_mortality_calls_sdk_and_prints_json(monkeypatch):
    captured = {}

    def fake_get_injury_mortality(**kwargs):
        captured.update(kwargs)
        return [{"year": "2016", "deaths": 100}]

    monkeypatch.setattr(cli, "get_injury_mortality", fake_get_injury_mortality)

    result = runner.invoke(
        app, ["wisqars", "mortality", "--intent", "Suicide", "--mechanism", "Firearm", "-f", "json"]
    )
    assert result.exit_code == 0
    assert captured["intent"] == "Suicide"
    assert captured["mechanism"] == "Firearm"
    assert json.loads(result.stdout) == [{"year": "2016", "deaths": 100}]


def test_wisqars_state_calls_sdk(monkeypatch):
    captured = {}

    def fake_get_injury_state(**kwargs):
        captured.update(kwargs)
        return [{"geoid": "06", "rate": 8.1}]

    monkeypatch.setattr(cli, "get_injury_state", fake_get_injury_state)

    result = runner.invoke(app, ["wisqars", "state", "--state", "California", "-f", "json"])
    assert result.exit_code == 0
    assert captured["state"] == "California"


def test_wisqars_query_resolves_registry_key(monkeypatch):
    captured = {}

    def fake_query_dataset(dataset_id, **kwargs):
        captured["dataset_id"] = dataset_id
        return [{"x": 1}]

    monkeypatch.setattr(cli, "wisqars_query_dataset", fake_query_dataset)

    result = runner.invoke(app, ["wisqars", "query", "injury_mortality", "-f", "json"])
    assert result.exit_code == 0
    assert captured["dataset_id"] == "nt65-c7a7"
