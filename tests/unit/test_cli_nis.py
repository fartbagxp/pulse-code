"""CLI smoke tests for the `nis` sub-app — monkeypatches the SDK call, no network.

Note: as of this writing, CDC has moved NIS-Child/Teen DAT/SAS files off the
legacy FTP paths hardcoded in the bundled year registry (nis_catalog.py), so
live `pulse nis stream/rates/national` calls currently 404 — the same
pre-existing issue affects `health`'s own `nis` module. These tests only
exercise the CLI plumbing, not the live URLs.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

import pulse.cli as cli
from pulse.cli import app

runner = CliRunner()


def test_nis_list_shows_year_range():
    result = runner.invoke(app, ["source", "nis", "list", "child"])
    assert result.exit_code == 0
    assert "2011" in result.stdout
    assert "2022" in result.stdout


def test_nis_list_invalid_survey_exits_nonzero():
    result = runner.invoke(app, ["source", "nis", "list", "not-a-survey"])
    assert result.exit_code != 0


def test_nis_stream_calls_sdk_and_respects_limit(monkeypatch):
    captured = {}

    def fake_stream_records(survey, year, **kwargs):
        captured["survey"] = survey
        captured["year"] = year
        captured.update(kwargs)
        yield from [{"P_UTDMMX": "1"}, {"P_UTDMMX": "0"}, {"P_UTDMMX": "1"}]

    monkeypatch.setattr(cli, "stream_records", fake_stream_records)

    result = runner.invoke(app, ["source", "nis", "stream", "child", "2022", "--limit", "2", "-f", "json"])
    assert result.exit_code == 0
    assert captured["survey"] == "child"
    assert captured["year"] == 2022
    data = json.loads(result.stdout)
    assert len(data) == 2


def test_nis_rates_calls_sdk(monkeypatch):
    captured = {}

    def fake_get_vaccination_rates(survey, year, **kwargs):
        captured["survey"] = survey
        captured["year"] = year
        return [{"state_fips": "06", "state_name": "California", "P_UTDMMX_pct": 91.3}]

    monkeypatch.setattr(cli, "get_vaccination_rates", fake_get_vaccination_rates)

    result = runner.invoke(app, ["source", "nis", "rates", "child", "2022", "-f", "json"])
    assert result.exit_code == 0
    assert captured == {"survey": "child", "year": 2022}
    data = json.loads(result.stdout)
    assert data[0]["state_name"] == "California"


def test_nis_national_wraps_single_dict_in_list(monkeypatch):
    def fake_get_national_rates(survey, year, **kwargs):
        return {"state_fips": "00", "state_name": "National", "P_UTDMMX_pct": 90.1}

    monkeypatch.setattr(cli, "get_national_rates", fake_get_national_rates)

    result = runner.invoke(app, ["source", "nis", "national", "child", "2022", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data == [{"state_fips": "00", "state_name": "National", "P_UTDMMX_pct": 90.1}]


def test_nis_stream_value_error_exits_nonzero(monkeypatch):
    def fake_stream_records(survey, year, **kwargs):
        raise ValueError("Unknown state 'ZZ'.")
        yield  # pragma: no cover

    monkeypatch.setattr(cli, "stream_records", fake_stream_records)

    result = runner.invoke(app, ["source", "nis", "stream", "child", "2022", "--state", "ZZ"])
    assert result.exit_code != 0
