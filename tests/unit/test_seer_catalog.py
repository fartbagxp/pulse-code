"""Unit tests for the SEER variable catalog loader — reads bundled JSON, no network."""

from __future__ import annotations

from pulse.seer_catalog import AGE_RANGE, RACE, cancer_sites, find_site, variable_formats


def test_loads_variable_formats():
    formats = variable_formats()
    assert "site" in formats
    assert "sex" in formats


def test_cancer_sites_include_common_sites():
    sites = cancer_sites()
    assert sites["55"] == "Breast"
    assert "47" in sites  # Lung and Bronchus


def test_find_site_is_case_insensitive_substring():
    matches = find_site("BREAST")
    assert ("55", "Breast") in matches


def test_find_site_no_match_returns_empty():
    assert find_site("not-a-real-cancer-site-xyz") == []


def test_race_and_age_range_catalogs_are_static_dicts():
    assert RACE["1"] == "All Races / Ethnicities"
    assert AGE_RANGE["1"] == "All Ages"
