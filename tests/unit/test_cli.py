"""CLI smoke tests for the commands that need no LLM/network access —
datasets, info, search, topics, list-queries. Uses Typer's CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from pulse.cli import app

runner = CliRunner()


def test_datasets_lists_known_dataset():
    result = runner.invoke(app, ["datasets"])
    assert result.exit_code == 0
    assert "D176" in result.stdout


def test_datasets_topic_filter():
    result = runner.invoke(app, ["datasets", "--topic", "Tuberculosis"])
    assert result.exit_code == 0
    assert "D202" in result.stdout


def test_datasets_json_output_is_valid():
    import json

    result = runner.invoke(app, ["datasets", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(d["id"] == "D176" for d in data)


def test_info_shows_dataset_detail():
    result = runner.invoke(app, ["info", "D202"])
    assert result.exit_code == 0
    assert "Tuberculosis" in result.stdout


def test_info_unknown_dataset_exits_nonzero():
    result = runner.invoke(app, ["info", "D999999"])
    assert result.exit_code != 0


def test_search_returns_matches():
    result = runner.invoke(app, ["search", "opioid overdose deaths"])
    assert result.exit_code == 0
    assert "D176" in result.stdout or "D77" in result.stdout


def test_search_surfaces_other_source_hits():
    import json

    result = runner.invoke(app, ["search", "measles", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(h["source"] == "cdc-open" for h in data["other_source_matches"])


def test_search_other_hits_empty_for_nonsense_query():
    import json

    result = runner.invoke(app, ["search", "zzzzznotarealtopiczzzz", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["other_source_matches"] == []


def test_sources_lists_all_seven():
    result = runner.invoke(app, ["sources"])
    assert result.exit_code == 0
    for name in ["WONDER", "SEER", "CDC Open Data", "WISQARS", "GRASP", "NSSP", "NIS"]:
        assert name in result.stdout


def test_sources_json_output_is_valid():
    import json

    result = runner.invoke(app, ["sources", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 7
    assert all("command" in s for s in data)


def test_topics_lists_categories():
    result = runner.invoke(app, ["topics"])
    assert result.exit_code == 0
    assert "Mortality" in result.stdout


def test_list_queries_shows_bundled_queries():
    import json

    result = runner.invoke(app, ["list-queries", "--json"])
    assert result.exit_code == 0
    filenames = {q["filename"] for q in json.loads(result.stdout)}
    assert "tb-cases-by-year-1993-2023-req.xml" in filenames


def test_list_queries_filtered_by_dataset():
    result = runner.invoke(app, ["list-queries", "--dataset", "D202"])
    assert result.exit_code == 0
    assert "D202" in result.stdout
