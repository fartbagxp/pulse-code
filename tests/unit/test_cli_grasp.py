"""CLI smoke tests for the `grasp` sub-app (hantavirus/fluview/flusurv nested Typer apps).

`list` reads the static in-code registry, no network. Query commands
monkeypatch the SDK call so no network access is required here either.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

import pulse.cli as cli
from pulse.cli import app

runner = CliRunner()


def test_grasp_list_shows_known_dataset():
    result = runner.invoke(app, ["grasp", "list"])
    assert result.exit_code == 0
    assert "hantavirus" in result.stdout


def test_grasp_hantavirus_cases_calls_sdk(monkeypatch):
    captured = {}

    def fake_get_hantavirus_cases(**kwargs):
        captured.update(kwargs)
        return [{"Patient": 1, "Outcome": "Dead"}]

    monkeypatch.setattr(cli, "get_hantavirus_cases", fake_get_hantavirus_cases)

    result = runner.invoke(
        app, ["grasp", "hantavirus", "cases", "--outcome", "Dead", "-f", "json"]
    )
    assert result.exit_code == 0
    assert captured["outcome"] == "Dead"
    assert json.loads(result.stdout) == [{"Patient": 1, "Outcome": "Dead"}]


def test_grasp_hantavirus_by_year_calls_sdk(monkeypatch):
    monkeypatch.setattr(
        cli, "summarize_hantavirus_by_year", lambda: [{"year": "1993", "cases": 27}]
    )
    result = runner.invoke(app, ["grasp", "hantavirus", "by-year", "-f", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"year": "1993", "cases": 27}]


def test_grasp_fluview_ili_data_passes_region_and_epiweeks(monkeypatch):
    captured = {}

    def fake_get_fluview_ili(**kwargs):
        captured.update(kwargs)
        return [{"region": "nat", "wili": 2.1}]

    monkeypatch.setattr(cli, "get_fluview_ili", fake_get_fluview_ili)

    result = runner.invoke(
        app,
        [
            "grasp", "fluview", "ili-data",
            "--region", "nat", "--region", "ca",
            "--epiweeks", "202001-202026",
            "-f", "json",
        ],
    )
    assert result.exit_code == 0
    assert captured["regions"] == ["nat", "ca"]
    assert captured["epiweeks"] == "202001-202026"


def test_grasp_flusurv_data_calls_sdk(monkeypatch):
    captured = {}

    def fake_get_flusurv_net(**kwargs):
        captured.update(kwargs)
        return [{"location": "CA", "rate_overall": 3.2}]

    monkeypatch.setattr(cli, "get_flusurv_net", fake_get_flusurv_net)

    result = runner.invoke(
        app, ["grasp", "flusurv", "data", "--location", "CA", "--season", "2019-20", "-f", "json"]
    )
    assert result.exit_code == 0
    assert captured["locations"] == ["CA"]
    assert captured["season"] == "2019-20"
