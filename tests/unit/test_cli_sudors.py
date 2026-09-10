"""
CLI + catalog + reshaping tests for the `sudors` source.

SUDORS has no API — every command reads the public dashboard's JSON payloads —
so the reshaping tests feed the SDK miniature payloads shaped exactly like the
real ones and assert on the flat rows that come back. Nothing here touches the
network; `_fetch` is monkeypatched at the module boundary and its `lru_cache` is
cleared so a stubbed payload never leaks between tests.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import pulse.sudors_sdk as sdk
from pulse.cli import app
from pulse.sudors_catalog import AGE_BANDS, SUPPRESSED, dataset, datasets, search

runner = CliRunner()


@pytest.fixture
def stub_payloads(monkeypatch):
    """Serve canned dashboard payloads by filename, bypassing the network."""
    payloads: dict[str, dict] = {}

    def fake_fetch(name: str) -> bytes:
        if name not in payloads:
            raise AssertionError(f"unexpected fetch for {name}")
        return json.dumps(payloads[name]).encode()

    # Hold the real cached function: by teardown `sdk._fetch` is still the stub,
    # and monkeypatch only restores it after this fixture finalizes.
    cached = sdk._fetch
    cached.cache_clear()
    monkeypatch.setattr(sdk, "_fetch", fake_fetch)
    yield payloads
    cached.cache_clear()


# ── catalog ───────────────────────────────────────────────────────────────────


def test_catalog_has_13_slices():
    assert len(datasets()) == 13


def test_every_slice_has_a_loader():
    # `pulse source sudors get <key>` routes through LOADERS; a registry entry
    # without one would list but not fetch.
    assert {d.key for d in datasets()} == set(sdk.LOADERS)


def test_workbook_slices_are_the_trend_tables_and_dictionary():
    # Only these three are absent from the dashboard JSON.
    assert {d.key for d in datasets() if d.workbook} == {
        "overall-trend",
        "trend-statistics",
        "data-dictionary",
    }


def test_lookup_and_search():
    assert dataset("drugs-detected").name.startswith("Drugs of interest")
    assert dataset("nope") is None
    assert {d.key for d in search("toxicology")} >= {"drugs-detected"}


# ── reshaping ─────────────────────────────────────────────────────────────────


def test_drugs_involved_flattens_year_and_jurisdiction(stub_payloads):
    stub_payloads["drugs-involved.json"] = {
        "2024": {
            "Ohio": [
                {"drug": "All", "count": 3135, "rate": 27.1, "percent": 100},
                {"drug": "Heroin", "count": 103, "rate": SUPPRESSED, "percent": 3.3},
            ]
        }
    }
    rows = sdk.get_drugs_involved()
    assert [r["drug"] for r in rows] == ["All", "Heroin"]
    assert rows[0] == {
        "year": "2024",
        "jurisdiction": "Ohio",
        "drug": "All",
        "deaths": 3135,
        "rate": 27.1,
        "percent": 100,
        "deaths_relchange_to_latest": None,
        "rate_relchange_to_latest": None,
        "percent_abschange_to_latest": None,
    }


def test_suppression_sentinel_becomes_none(stub_payloads):
    # 9999 must never survive as a number — it would read as a plausible rate.
    stub_payloads["drugs-involved.json"] = {
        "2024": {
            "Ohio": [{"drug": "Heroin", "count": 3, "rate": SUPPRESSED, "percent": 0.1}]
        }
    }
    assert sdk.get_drugs_involved()[0]["rate"] is None


def test_years_sort_numerically_not_lexically(stub_payloads):
    stub_payloads["totals_for_filter.json"] = {
        "2024": {"Ohio": {"count": 3}},
        "2020": {"Ohio": {"count": 1}},
        "2021": {"Ohio": {"count": 2}},
    }
    # Plain dict order would give 2024 first; string sort would too once a year
    # crosses a digit boundary. Years are sorted with int().
    assert [r["year"] for r in sdk.get_totals()] == ["2020", "2021", "2024"]


def test_demographics_stacks_three_payloads_and_labels_age_bands(stub_payloads):
    stub_payloads["demographics-by-sex.json"] = {
        "2024": {
            "Ohio": [{"sex": "Male", "count": 2139, "rate": 37.2, "percent": 68.2}]
        }
    }
    stub_payloads["demographics-by-age.json"] = {
        "2024": {"Ohio": [{"age": "2", "count": 500, "rate": 20.0, "percent": 16.0}]}
    }
    stub_payloads["demographics-by-race-ethnicity.json"] = {
        "2024": {
            "Ohio": [{"race": "Hispanic", "count": 108, "rate": 20.6, "percent": 3.5}]
        }
    }
    rows = sdk.get_demographics()
    assert [r["dimension"] for r in rows] == ["sex", "age", "race_ethnicity"]
    # Age arrives as an ordinal code and must be rendered as the band it means.
    assert rows[1]["group"] == AGE_BANDS["2"] == "25-34"


def test_deaths_by_month_builds_a_parseable_date(stub_payloads):
    stub_payloads["deaths-by-month.json"] = {
        "2024": {
            "Ohio": {
                "All": {
                    "month": [{"month": 1, "count": 12}, {"month": 11, "count": 18}],
                    "quarter": [{"quarter": 1, "count": 30}],
                }
            }
        }
    }
    rows = sdk.get_deaths_by_month()
    # The quarterly series is these months summed and is deliberately not returned.
    assert len(rows) == 2
    assert [r["month_date"] for r in rows] == ["2024-01", "2024-11"]


def test_drug_combinations_drops_wholly_absent_pairs(stub_payloads):
    stub_payloads["drugs-involved-combos-lollipops.json"] = {
        "2024": {
            "Ohio": {
                "Any opioids": [
                    {
                        "drug": "Cocaine",
                        "count": 100,
                        "percentAll": 3.2,
                        "percentDrug": 4.3,
                    },
                    {
                        "drug": "Heroin",
                        "count": None,
                        "percentAll": None,
                        "percentDrug": None,
                    },
                ]
            }
        }
    }
    rows = sdk.get_drug_combinations()
    assert len(rows) == 1
    assert rows[0]["combined_with"] == "Cocaine"


def test_opioid_stimulant_unpacks_the_four_cells(stub_payloads):
    stub_payloads["drugs-involved-opioid-stimulant-combo.json"] = {
        "2024": {
            "Ohio": {
                "osName": "Opioids and stimulants",
                "osCount": 1420,
                "osPercent": 45.3,
                "oName": "Opioids and no stimulants",
                "oCount": 923,
                "oPercent": 29.4,
                "sName": "Stimulants and no opioids",
                "sCount": 651,
                "sPercent": 20.8,
                "nName": "Neither opioids nor stimulants",
                "nCount": 141,
                "nPercent": 4.5,
            }
        }
    }
    rows = sdk.get_opioid_stimulant()
    assert [r["category"] for r in rows] == [
        "opioids_and_stimulants",
        "opioids_only",
        "stimulants_only",
        "neither",
    ]
    assert sum(r["percent"] for r in rows) == pytest.approx(100.0, abs=0.1)


def test_trend_scope_separates_the_two_aggregates():
    # CDC ships two aggregates per range; only the strict one is a plottable
    # series. Filtering on the label itself would mean matching a jurisdiction
    # count that shifts every release.
    rows = sdk._add_scope(
        [
            {
                "jurisdiction": "Overall (27 jurisdictions; drugs of interest detected: 26 jurisdictions)"
            },
            {"jurisdiction": "Map data only: Overall (33 jurisdictions)"},
        ]
    )
    assert [r["scope"] for r in rows] == ["chart", "map"]


def test_filter_rows_narrows_by_year_jurisdiction_and_limit():
    rows = [
        {"year": "2023", "jurisdiction": "Ohio"},
        {"year": "2024", "jurisdiction": "Ohio"},
        {"year": "2024", "jurisdiction": "Alaska"},
    ]
    assert sdk.filter_rows(rows, year=2024) == rows[1:]
    assert sdk.filter_rows(rows, jurisdiction="ohio") == rows[:2]  # case-insensitive
    assert sdk.filter_rows(rows, limit=1) == rows[:1]


def test_jurisdictions_for_a_year_and_across_the_release(stub_payloads):
    stub_payloads["totals_for_filter.json"] = {
        "2020": {"Overall": {"count": 9}, "Alaska": {"count": 1}},
        "2024": {"Overall": {"count": 9}, "Ohio": {"count": 2}},
    }
    assert sdk.jurisdictions(2020) == ["Alaska", "Overall"]
    assert sdk.jurisdictions() == ["Alaska", "Ohio", "Overall"]


# ── CLI ───────────────────────────────────────────────────────────────────────


def test_bare_source_sudors_lists_datasets():
    result = runner.invoke(app, ["source", "sudors", "--json"])
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) == 13


def test_list_search_narrows():
    result = runner.invoke(
        app, ["source", "sudors", "list", "--search", "circumstances", "--json"]
    )
    assert result.exit_code == 0
    assert [d["key"] for d in json.loads(result.stdout)] == ["circumstances"]


def test_get_rejects_an_unknown_slice():
    result = runner.invoke(app, ["source", "sudors", "get", "nope"])
    assert result.exit_code == 1


def test_drugs_reports_a_fetch_failure_instead_of_traceback(monkeypatch):
    def boom(name):
        raise sdk.SudorsError("dashboard moved")

    sdk._fetch.cache_clear()
    monkeypatch.setattr(sdk, "fetch_json", boom)
    result = runner.invoke(app, ["source", "sudors", "drugs"])
    assert result.exit_code == 1
    sdk._fetch.cache_clear()


def test_empty_filter_points_at_the_jurisdiction_list(stub_payloads):
    stub_payloads["drugs-involved.json"] = {
        "2024": {"Ohio": [{"drug": "All", "count": 1}]}
    }
    result = runner.invoke(app, ["source", "sudors", "drugs", "-j", "Wyoming"])
    assert result.exit_code == 1
