"""CLI smoke tests for the `nssp` sub-app — monkeypatches the SDK call, no network."""

from __future__ import annotations

import json

from typer.testing import CliRunner

import pulse.cli as cli
from pulse.cli import app

runner = CliRunner()


def test_nssp_query_calls_sdk_and_prints_json(monkeypatch):
    captured = {}

    def fake_get_ed_visits(**kwargs):
        captured.update(kwargs)
        return [{"geo_value": "ca", "time_value": 202501, "value": 1.2}]

    monkeypatch.setattr(cli, "get_ed_visits", fake_get_ed_visits)

    result = runner.invoke(
        app, ["nssp", "query", "covid", "--geo-type", "state", "--geo-value", "ca", "-f", "json"]
    )
    assert result.exit_code == 0
    assert captured["pathogen"] == "covid"
    assert captured["geo_type"] == "state"
    assert captured["geo_value"] == "ca"
    assert json.loads(result.stdout) == [{"geo_value": "ca", "time_value": 202501, "value": 1.2}]


def test_nssp_national_calls_sdk(monkeypatch):
    def fake_get_national_trends(**kwargs):
        return [{"pathogen": "covid", "time_value": 202501, "value": 0.5}]

    monkeypatch.setattr(cli, "get_national_trends", fake_get_national_trends)

    result = runner.invoke(app, ["nssp", "national", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["pathogen"] == "covid"


def test_nssp_hhs_calls_sdk_with_region(monkeypatch):
    captured = {}

    def fake_get_hhs_region_trends(**kwargs):
        captured.update(kwargs)
        return [{"geo_value": "4", "time_value": 202501, "value": 1.0}]

    monkeypatch.setattr(cli, "get_hhs_region_trends", fake_get_hhs_region_trends)

    result = runner.invoke(app, ["nssp", "hhs", "influenza", "--region", "4", "-f", "json"])
    assert result.exit_code == 0
    assert captured["pathogen"] == "influenza"
    assert captured["region"] == 4
