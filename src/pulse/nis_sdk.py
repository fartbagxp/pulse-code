"""
NIS SDK — high-level Python API for CDC National Immunization Survey data.

All functions stream the source DAT file without saving to disk.
The SAS codebook is fetched first (small) to derive column positions,
then the DAT file is streamed and parsed on the fly.

Geographic scope
----------------
NIS public-use files contain state and national identifiers only.
County-level identifiers are suppressed; county data requires CDC RDC access.

Survey weights
--------------
PROVWT_D (child) and PROVWT_C (teen) should be applied when computing
nationally representative estimates. The aggregate functions here return
both unweighted counts and weighted estimates where weights are available.

Examples
--------
    from pulse.nis_sdk import list_years, stream_records, get_vaccination_rates

    # Available years for each survey
    print(list_years("child"))

    # Stream raw respondent records (dicts) — no storage
    for rec in stream_records("child", 2022, state="California"):
        print(rec["P_UTDMMX"], rec["RETEILI"])

    # Aggregate UTD rates by state
    rows = get_vaccination_rates("child", 2022)
    for r in rows[:5]:
        print(r)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterator

import requests

from pulse.nis_catalog import (
    FIPS_TO_STATE,
    NISYear,
    STATE_TO_FIPS,
    SURVEY_COLS,
    SURVEY_VAX_COLS,
    SURVEY_YEARS,
)
from pulse.nis_parser import parse_r_columns, parse_sas_columns, stream_dat

# ── Internals ──────────────────────────────────────────────────────────────────


def _get_year(survey: str, year: int) -> NISYear:
    years = SURVEY_YEARS.get(survey)
    if years is None:
        raise ValueError(f"Unknown survey {survey!r}. Use 'child' or 'teen'.")
    entry = years.get(year)
    if entry is None:
        available = sorted(years)
        raise ValueError(
            f"Year {year} not in registry for '{survey}' survey. "
            f"Available: {available[0]}–{available[-1]}"
        )
    return entry


def _fetch_columns(entry: NISYear, select: set[str]) -> dict[str, tuple[int, int]]:
    """Fetch the format sidecar (SAS or R, per entry.format_type) and return only the column positions we need."""
    resp = requests.get(entry.format_url, timeout=60)
    resp.raise_for_status()
    parse = parse_sas_columns if entry.format_type == "sas" else parse_r_columns
    all_cols = parse(resp.text)
    return {k: v for k, v in all_cols.items() if k in select}


def _geo_key(record: dict[str, str], survey: str) -> str:
    """Return the state FIPS code for a record (or '' if unavailable)."""
    # NIS-Teen uses STATE; NIS-Child uses RETEILI which may encode local areas.
    # For child, state FIPS are padded to 2 digits and values > 78 are local-area
    # subsets of states; we map those back to the parent state FIPS.
    raw = (record.get("STATE") or record.get("RETEILI") or "").strip()
    if not raw:
        return ""
    # Normalize to 2-digit zero-padded string
    try:
        code = f"{int(raw):02d}"
    except ValueError:
        return ""
    # Local-area codes in RETEILI can go above 78; the parent state FIPS
    # is the value minus the local-area offset (varies by year and area).
    # For public-use files, codes 1–78 are direct FIPS values.
    if int(code) <= 78:
        return code
    return ""


# ── Public API ─────────────────────────────────────────────────────────────────


def list_years(survey: str) -> list[int]:
    """Return the list of available years for the given survey ('child' or 'teen')."""
    years = SURVEY_YEARS.get(survey)
    if years is None:
        raise ValueError(f"Unknown survey {survey!r}. Use 'child' or 'teen'.")
    return sorted(years)


def stream_records(
    survey: str,
    year: int,
    state: str | None = None,
    columns: set[str] | None = None,
) -> Iterator[dict[str, str]]:
    """
    Stream individual NIS survey records for one year without saving to disk.

    survey:   'child' (19–35 months) or 'teen' (13–17 years)
    year:     Survey year, e.g. 2022
    state:    Filter to a single state — accepts 2-digit FIPS ('06'),
              postal abbreviation ('CA'), or full name ('California').
              None returns all states (national).
    columns:  Set of UPPERCASE column names to include.
              Defaults to all vaccination + geo + hesitancy columns.

    Yields one dict per respondent. All values are raw strings;
    see the NIS codebook PDF for numeric code meanings.
    """
    entry = _get_year(survey, year)
    select = columns if columns is not None else SURVEY_COLS[survey]
    col_map = _fetch_columns(entry, select)

    if not col_map:
        raise RuntimeError(
            f"No matching columns found in {entry.format_type.upper()} codebook at {entry.format_url}. "
            "The file may use an unrecognised format — check the URL and try again."
        )

    # Resolve state filter to a 2-digit FIPS string
    fips_filter: str | None = None
    if state is not None:
        s = state.strip()
        if s.isdigit():
            fips_filter = f"{int(s):02d}"
        elif len(s) == 2 and s.isalpha():
            # Try postal abbreviation via known state names
            for name, fips in STATE_TO_FIPS.items():
                if name[:2] == s.upper():
                    fips_filter = fips
                    break
            if fips_filter is None:
                raise ValueError(f"Could not resolve postal code {s!r} to a FIPS code.")
        else:
            fips_filter = STATE_TO_FIPS.get(s.upper())
            if fips_filter is None:
                raise ValueError(f"Unknown state {s!r}.")

    for rec in stream_dat(entry.dat_url, col_map, select=None):
        if fips_filter is not None:
            rec_fips = _geo_key(rec, survey)
            if rec_fips != fips_filter:
                continue
        yield rec


def get_vaccination_rates(
    survey: str,
    year: int,
    state: str | None = None,
    vaccines: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Aggregate provider-verified UTD rates by state (or nationally).

    survey:   'child' or 'teen'
    year:     Survey year, e.g. 2022
    state:    Limit to one state (FIPS / postal / full name); None = all states.
    vaccines: List of UTD column names to include, e.g. ['P_UTDMMX', 'P_UTDDTP4'].
              Defaults to all known UTD columns for the survey.

    Returns a list of dicts, one per geographic unit, with keys:
      state_fips, state_name, year, survey,
      {vaccine}_pct, {vaccine}_n, {vaccine}_denominator,
      hesitancy_pct, hesitancy_n, n_respondents

    UTD percentages are unweighted; for weighted estimates apply PROVWT_D/PROVWT_C.
    Records with blank UTD values are excluded from that vaccine's denominator.
    """
    vax_cols = set(vaccines) if vaccines else SURVEY_VAX_COLS[survey]
    weight_col = "PROVWT_D" if survey == "child" else "PROVWT_C"
    geo_col = "STATE" if survey == "teen" else "RETEILI"

    wanted = vax_cols | {"SHOT_HES", "NOT_SURE_VACC", weight_col, geo_col, "STATE", "RETEILI"}
    records = list(stream_records(survey, year, state=state, columns=wanted))

    # Accumulate by state FIPS
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for rec in records:
        fips = _geo_key(rec, survey)
        buckets[fips].append(rec)

    rows: list[dict[str, Any]] = []
    for fips, recs in sorted(buckets.items()):
        row: dict[str, Any] = {
            "state_fips": fips,
            "state_name": FIPS_TO_STATE.get(fips, f"FIPS {fips}"),
            "year": year,
            "survey": survey,
            "n_respondents": len(recs),
        }

        for col in sorted(vax_cols):
            values = [r[col] for r in recs if r.get(col) in ("0", "1")]
            n_utd = sum(1 for v in values if v == "1")
            denom = len(values)
            row[f"{col}_pct"] = round(100 * n_utd / denom, 1) if denom else None
            row[f"{col}_n"] = n_utd
            row[f"{col}_denominator"] = denom

        # Hesitancy: coded 1=hesitant in either SHOT_HES or NOT_SURE_VACC
        hesi_vals = []
        for rec in recs:
            h = rec.get("SHOT_HES") or rec.get("NOT_SURE_VACC") or ""
            if h in ("0", "1"):
                hesi_vals.append(int(h))
        row["hesitancy_pct"] = round(100 * sum(hesi_vals) / len(hesi_vals), 1) if hesi_vals else None
        row["hesitancy_n"] = sum(hesi_vals)

        rows.append(row)

    return rows


def get_national_rates(
    survey: str,
    year: int,
    vaccines: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compute national-level UTD rates across all states for one year.

    Returns a single dict with the same structure as get_vaccination_rates()
    but with state_fips='00' and state_name='National'.
    """
    state_rows = get_vaccination_rates(survey, year, vaccines=vaccines)
    if not state_rows:
        return {}

    vax_cols = set(vaccines) if vaccines else SURVEY_VAX_COLS[survey]
    national: dict[str, Any] = {
        "state_fips": "00",
        "state_name": "National",
        "year": year,
        "survey": survey,
        "n_respondents": sum(r["n_respondents"] for r in state_rows),
    }

    for col in sorted(vax_cols):
        total_n = sum(r.get(f"{col}_n") or 0 for r in state_rows)
        total_d = sum(r.get(f"{col}_denominator") or 0 for r in state_rows)
        national[f"{col}_pct"] = round(100 * total_n / total_d, 1) if total_d else None
        national[f"{col}_n"] = total_n
        national[f"{col}_denominator"] = total_d

    total_hesi_n = sum(r.get("hesitancy_n") or 0 for r in state_rows)
    total_hesi_d = sum(r["n_respondents"] for r in state_rows if r.get("hesitancy_pct") is not None)
    national["hesitancy_pct"] = round(100 * total_hesi_n / total_hesi_d, 1) if total_hesi_d else None
    national["hesitancy_n"] = total_hesi_n

    return national
