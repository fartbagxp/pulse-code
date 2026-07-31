"""CLI smoke tests for the commands that need no LLM/network access —
datasets, info, search, topics, sources, list-queries. Uses Typer's CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from pulse.cli import app

runner = CliRunner()


def test_datasets_lists_known_dataset():
    result = runner.invoke(app, ["source", "wonder", "datasets"])
    assert result.exit_code == 0
    assert "D176" in result.stdout


def test_datasets_topic_filter():
    result = runner.invoke(app, ["source", "wonder", "datasets", "--topic", "Tuberculosis"])
    assert result.exit_code == 0
    assert "D202" in result.stdout


def test_datasets_json_output_is_valid():
    import json

    result = runner.invoke(app, ["source", "wonder", "datasets", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(d["id"] == "D176" for d in data)


def test_info_shows_dataset_detail():
    result = runner.invoke(app, ["source", "wonder", "info", "D202"])
    assert result.exit_code == 0
    assert "Tuberculosis" in result.stdout


def test_info_unknown_dataset_exits_nonzero():
    result = runner.invoke(app, ["source", "wonder", "info", "D999999"])
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
    result = runner.invoke(app, ["source"])
    assert result.exit_code == 0
    for name in ["WONDER", "SEER", "CDC Open Data", "WISQARS", "GRASP", "NSSP", "NIS"]:
        assert name in result.stdout


def test_sources_json_output_is_valid():
    import json

    result = runner.invoke(app, ["source", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 7
    assert all("command" in s for s in data)


def test_topics_lists_categories():
    result = runner.invoke(app, ["topics"])
    assert result.exit_code == 0
    assert "Mortality" in result.stdout


def test_topics_mortality_is_first():
    import json

    result = runner.invoke(app, ["topics", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 18
    assert data[0]["label"] == "Mortality"


def test_topics_drill_down_shows_default_source():
    import json

    result = runner.invoke(app, ["topics", "mortality", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["label"] == "Mortality"
    assert any(s["source"] == "wonder" and s["is_default"] for s in data["sources"])


def test_topics_unknown_exits_nonzero():
    result = runner.invoke(app, ["topics", "zzzzznotarealtopiczzzz"])
    assert result.exit_code != 0


def test_sources_wonder_lists_datasets_with_url():
    import json

    result = runner.invoke(app, ["source", "wonder", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(d["key"] == "D176" and "wonder.cdc.gov/controller/datarequest" in d["url"] for d in data)


def test_sources_nis_lists_years_with_real_urls():
    import json

    result = runner.invoke(app, ["source", "nis", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any("VACCINES_NIS" in d["url"] for d in data)
    assert any("health_statistics/nchs/datasets/nis" in d["url"] for d in data)


def test_sources_unknown_exits_nonzero():
    result = runner.invoke(app, ["source", "bogus"])
    assert result.exit_code != 0


def test_sources_overview_unchanged_without_arg():
    result = runner.invoke(app, ["source"])
    assert result.exit_code == 0
    for name in ["WONDER", "SEER", "CDC Open Data", "WISQARS", "GRASP", "NSSP", "NIS"]:
        assert name in result.stdout


def test_source_bare_lists_source_datasets():
    result = runner.invoke(app, ["source", "seer"])
    assert result.exit_code == 0
    # SEER's bare listing shows cancer-site rows with the SEER Explorer URL.
    assert "seer.cancer.gov" in result.stdout


def test_source_wonder_bare_lists_datasets():
    import json

    result = runner.invoke(app, ["source", "wonder", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(d["key"] == "D176" for d in data)


def test_old_flat_paths_are_gone():
    # Clean break: the pre-restructure top-level commands no longer exist.
    for argv in (["datasets"], ["seer", "sites"], ["sources"]):
        result = runner.invoke(app, argv)
        assert result.exit_code != 0, f"{argv!r} should no longer be a valid command"


def test_list_queries_shows_bundled_queries():
    import json

    result = runner.invoke(app, ["source", "wonder", "list-queries", "--json"])
    assert result.exit_code == 0
    filenames = {q["filename"] for q in json.loads(result.stdout)}
    assert "tb-cases-by-year-1993-2023-req.xml" in filenames


def test_list_queries_filtered_by_dataset():
    result = runner.invoke(app, ["source", "wonder", "list-queries", "--dataset", "D202"])
    assert result.exit_code == 0
    assert "D202" in result.stdout
