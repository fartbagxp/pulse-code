"""
SUDORS SDK — read the dashboard's own payloads and reshape them to flat rows.

There is no SUDORS API. The public dashboard is a static React bundle that reads
per-section JSON from an unversioned path, and CDC publishes the same release as
a workbook. Both are plain unauthenticated GETs, so this module needs nothing but
`requests` and the standard library.

Every dashboard JSON is nested `{year: {jurisdiction: ...}}`. Each `get_*` here
flattens one to a list of dicts with `year` and `jurisdiction` leading, so the
CLI can print, filter, and CSV them the same way it does every other source.

Suppression: the dashboard carries a global `9999` sentinel and renders it as an
asterisk. It comes back as `None` here, so a consumer never mistakes it for a
count. CDC suppresses any rate built on 1-19 deaths.

The workbook is only fetched by `get_trend`, `get_trend_statistics`, and
`get_data_dictionary` — the three things the JSON does not carry. Payloads are
memoized per process so a session that filters the same slice repeatedly pays one
download.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Callable, Iterator
from functools import cache
from io import BytesIO
from typing import Any

import requests

from pulse.sudors_catalog import AGE_BANDS, BASE_URL, SUPPRESSED, XLSX_NAME

_TIMEOUT = 60
USER_AGENT = "pulse-code (+https://github.com/fartbagxp/pulse-code)"


class SudorsError(RuntimeError):
    """A SUDORS payload could not be fetched or parsed."""


@cache
def _fetch(name: str) -> bytes:
    try:
        resp = requests.get(
            f"{BASE_URL}/{name}", headers={"User-Agent": USER_AGENT}, timeout=_TIMEOUT
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise SudorsError(
            f"could not fetch {name} from the SUDORS dashboard: {exc}"
        ) from exc
    return resp.content


def fetch_json(name: str) -> dict:
    try:
        return json.loads(_fetch(name))
    except json.JSONDecodeError as exc:
        raise SudorsError(f"{name} was not valid JSON: {exc}") from exc


def _num(value: Any) -> float | None:
    """Numeric cell, with the suppression sentinel and nulls collapsed to None."""
    if value is None or value == SUPPRESSED:
        return None
    return value


def _walk(payload: dict) -> Iterator[tuple[str, str, Any]]:
    """Yield (year, jurisdiction, value) over the standard two-level nesting."""
    for year in sorted(payload, key=int):
        for jurisdiction in sorted(payload[year]):
            yield year, jurisdiction, payload[year][jurisdiction]


def filter_rows(
    rows: list[dict],
    year: int | str | None = None,
    jurisdiction: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Apply the shared --year / --jurisdiction / --limit narrowing."""
    if year is not None:
        rows = [r for r in rows if r.get("year") == str(year)]
    if jurisdiction:
        want = jurisdiction.strip().lower()
        rows = [r for r in rows if (r.get("jurisdiction") or "").lower() == want]
    return rows[:limit] if limit else rows


# ── Annual view ───────────────────────────────────────────────────────────────


def get_totals() -> list[dict]:
    """Total overdose deaths per jurisdiction-year — the denominator behind every percent."""
    return [
        {"year": y, "jurisdiction": j, "deaths": _num(v.get("count"))}
        for y, j, v in _walk(fetch_json("totals_for_filter.json"))
    ]


def get_drugs_involved() -> list[dict]:
    """
    Drug classes a medical examiner or coroner ruled as causing the death.

    The `*_to_latest` columns are not year-over-year: on a row for year Y they
    carry the change from Y to the newest data year in the release, which is
    exactly the "Y to <latest>" row of `get_trend_statistics`. The newest year's
    own rows are therefore empty.
    """
    return [
        {
            "year": y,
            "jurisdiction": j,
            "drug": e.get("drug"),
            "deaths": _num(e.get("count")),
            "rate": _num(e.get("rate")),
            "percent": _num(e.get("percent")),
            "deaths_relchange_to_latest": _num(e.get("countChange")),
            "rate_relchange_to_latest": _num(e.get("rateChange")),
            "percent_abschange_to_latest": _num(e.get("percentChange")),
        }
        for y, j, entries in _walk(fetch_json("drugs-involved.json"))
        for e in entries
    ]


def get_drugs_detected() -> list[dict]:
    """
    Drugs of interest found on postmortem toxicology, ruled a cause of death or not.

    The cut with no ICD-10 counterpart: xylazine, nitazene analogs, bromazolam,
    carfentanil and para-fluorofentanyl all fall inside T40.4 or have no code.
    Only jurisdictions with toxicology on >=75% of deaths report here.
    """
    return [
        {
            "year": y,
            "jurisdiction": j,
            "drug": e.get("drug"),
            "deaths": _num(e.get("count")),
            "percent": _num(e.get("percent")),
        }
        for y, j, entries in _walk(fetch_json("drugs-detected.json"))
        for e in entries
    ]


def get_demographics() -> list[dict]:
    """
    Sex, age band, and race/ethnicity stacked into one shape, keyed by `dimension`.

    Age-band rates are crude; sex and race/ethnicity rates are age-standardized to
    the 2010 U.S. Census population.
    """
    rows: list[dict] = []
    for dimension, name, key in (
        ("sex", "demographics-by-sex.json", "sex"),
        ("age", "demographics-by-age.json", "age"),
        ("race_ethnicity", "demographics-by-race-ethnicity.json", "race"),
    ):
        for y, j, entries in _walk(fetch_json(name)):
            for e in entries:
                label = e.get(key)
                if dimension == "age":
                    label = AGE_BANDS.get(str(label), label)
                rows.append(
                    {
                        "year": y,
                        "jurisdiction": j,
                        "dimension": dimension,
                        "group": label,
                        "deaths": _num(e.get("count")),
                        "rate": _num(e.get("rate")),
                        "percent": _num(e.get("percent")),
                        "deaths_relchange_to_latest": _num(e.get("countChange")),
                        "rate_relchange_to_latest": _num(e.get("rateChange")),
                        "percent_abschange_to_latest": _num(e.get("percentChange")),
                    }
                )
    return rows


def get_demographics_by_sex_age() -> list[dict]:
    """Age band crossed with sex."""
    return [
        {
            "year": y,
            "jurisdiction": j,
            "sex": sex,
            "age_group": AGE_BANDS.get(str(e.get("age")), e.get("age")),
            "deaths": _num(e.get("count")),
            "rate": _num(e.get("rate")),
            "percent": _num(e.get("percent")),
        }
        for y, j, by_sex in _walk(fetch_json("demographics-by-sex-age.json"))
        for sex in sorted(by_sex)
        for e in by_sex[sex]
    ]


def get_deaths_by_month() -> list[dict]:
    """
    Monthly counts per drug class — SUDORS' only sub-annual cut.

    `month_date` is a YYYY-MM string so a chart can parse one column. The
    quarterly series the dashboard also ships is these twelve values summed and is
    not returned.
    """
    return [
        {
            "year": y,
            "month": e.get("month"),
            "month_date": f"{y}-{int(e.get('month')):02d}",
            "jurisdiction": j,
            "drug": drug,
            "deaths": _num(e.get("count")),
        }
        for y, j, by_drug in _walk(fetch_json("deaths-by-month.json"))
        for drug in by_drug
        for e in by_drug[drug].get("month", [])
    ]


def get_circumstances() -> list[dict]:
    """
    Circumstances surrounding the death, across the dashboard's nine sections.

    Percentages are among decedents with known information for that circumstance,
    not among all deaths, so they will not reconcile against `get_totals`. They
    are floor estimates: a circumstance is recorded only where the investigator
    had evidence of it.
    """
    return [
        {
            "year": y,
            "jurisdiction": j,
            "section": section,
            "circumstance": e.get("circumstance"),
            "deaths": _num(e.get("count")),
            "percent": _num(e.get("percent")),
            "percent_abschange_to_latest": _num(e.get("percentChange")),
        }
        for y, j, sections in _walk(fetch_json("circumstances.json"))
        for section in sections
        for e in sections[section]
    ]


def get_drug_combinations() -> list[dict]:
    """
    Drug-pair co-involvement: of the deaths involving `drug`, how many also
    involved `combined_with`.

    `percent_all` is out of all overdose deaths; `percent_drug` is out of deaths
    involving `drug`. Pairs a jurisdiction did not qualify to report are dropped
    rather than returned empty.
    """
    return [
        {
            "year": y,
            "jurisdiction": j,
            "drug": drug,
            "combined_with": e.get("drug"),
            "deaths": _num(e.get("count")),
            "percent_all": _num(e.get("percentAll")),
            "percent_drug": _num(e.get("percentDrug")),
        }
        for y, j, by_drug in _walk(fetch_json("drugs-involved-combos-lollipops.json"))
        for drug in by_drug
        for e in by_drug[drug]
        if e.get("count") is not None or e.get("percentAll") is not None
    ]


# The dashboard packs the four opioid x stimulant cells into one flat object,
# a name/count/percent triple per prefix.
_OPIOID_STIMULANT_CELLS = (
    ("os", "opioids_and_stimulants"),
    ("o", "opioids_only"),
    ("s", "stimulants_only"),
    ("n", "neither"),
)


def get_opioid_stimulant() -> list[dict]:
    """The four-way opioid x stimulant split — polysubstance involvement at a glance."""
    return [
        {
            "year": y,
            "jurisdiction": j,
            "category": category,
            "label": cells.get(f"{prefix}Name"),
            "deaths": _num(cells.get(f"{prefix}Count")),
            "percent": _num(cells.get(f"{prefix}Percent")),
        }
        for y, j, cells in _walk(
            fetch_json("drugs-involved-opioid-stimulant-combo.json")
        )
        for prefix, category in _OPIOID_STIMULANT_CELLS
    ]


def get_top_combinations() -> list[dict]:
    """
    The five most common exact drug combinations per jurisdiction-year.

    `top5_percent_total` is the share of all overdose deaths the five together
    account for, repeated per row so each row carries its own context.
    """
    return [
        {
            "year": y,
            "jurisdiction": j,
            "rank": rank,
            "combination": e.get("drugCombination"),
            "deaths": _num(e.get("count")),
            "percent": _num(e.get("percent")),
            "top5_percent_total": _num(entry.get("total")),
        }
        for y, j, entry in _walk(fetch_json("drugs-involved-top-five-combo.json"))
        for rank, e in enumerate(entry.get("combinations", []), start=1)
    ]


def get_release() -> dict:
    """The release stamp CDC embeds in the dashboard footnotes."""
    payload = fetch_json("footnotes-text.json")
    return {
        "data_entry_cutoff": payload.get("dataset_date"),
        "latest_data_year": payload.get("upper_year"),
        "pct_deaths_in_residence_jurisdiction": payload.get("occurrent_percent"),
        "pct_imf_deaths_toxicology_confirmed": payload.get("fentanyl_percent"),
    }


def jurisdictions(year: int | str | None = None) -> list[str]:
    """
    Jurisdictions reporting for a year (or every jurisdiction ever, if no year).

    `Overall` is included: it is how the dashboard labels the combined row for the
    jurisdictions that qualified that year.
    """
    payload = fetch_json("totals_for_filter.json")
    if year is not None:
        return sorted(payload.get(str(year), {}))
    return sorted({j for y in payload for j in payload[y]})


def years() -> list[str]:
    """Data years on the annual view, oldest first."""
    return sorted(fetch_json("totals_for_filter.json"), key=int)


# ── Trend view + dictionary: the workbook ─────────────────────────────────────


@cache
def _sheet_rows(sheet_name: str) -> tuple[tuple, ...]:
    """
    Materialize one workbook sheet's rows.

    openpyxl's read-only mode parses lazily and raises its unparseable
    header/footer warning on first cell access, not on load — so the rows are
    pulled inside the filter rather than handing a live worksheet back out. The
    workbook carries an Excel header/footer nothing here reads.
    """
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - openpyxl is a hard dependency
        raise SudorsError(
            "the SUDORS trend tables live in CDC's Excel workbook; install openpyxl to read them"
        ) from exc

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Cannot parse header or footer")
        workbook = openpyxl.load_workbook(BytesIO(_fetch(XLSX_NAME)), read_only=True)
        try:
            return tuple(
                tuple(row) for row in workbook[sheet_name].iter_rows(values_only=True)
            )
        finally:
            workbook.close()


def _melt_sheet(sheet_name: str, id_columns: list[str]) -> list[dict]:
    """
    Melt one wide workbook sheet to long (id columns + measure/value).

    The trend sheets are 200-300 columns wide, one per (drug x metric) pair.
    Melting keeps every measure without hard-coding CDC's column naming, and
    `measure` joins straight against `get_data_dictionary`. Blank and suppressed
    cells are dropped. Continuation rows leave the id columns blank (they are
    visually merged in Excel), so ids are carried forward.
    """
    raw = _sheet_rows(sheet_name)
    header = [str(c).strip() if c is not None else "" for c in raw[0]]
    index = {name: i for i, name in enumerate(header)}
    measures = [
        (name, i) for i, name in enumerate(header) if name and name not in id_columns
    ]

    out: list[dict] = []
    carried: dict[str, str] = {}
    for row in raw[1:]:
        if all(c is None or str(c).strip() == "" for c in row):
            continue
        ids = {}
        for name in id_columns:
            cell = row[index[name]] if name in index else None
            value = "" if cell is None else str(cell).strip()
            if value:
                carried[name] = value
            ids[name] = carried.get(name, "")
        for name, i in measures:
            cell = row[i]
            if cell is None or cell == SUPPRESSED or str(cell).strip() == "":
                continue
            out.append({**ids, "measure": name, "value": cell})
    return out


# The trend sheets carry two aggregates per range. The line/bar views use the
# strict one (jurisdictions present in *every* year); the map views relax that to
# the first and last year only, and CDC prefixes those rows "Map data only:".
_MAP_ONLY_PREFIX = "Map data only:"


def _add_scope(rows: list[dict]) -> list[dict]:
    """
    Tag each trend row `chart` or `map`, keeping the label as CDC wrote it.

    Without this a consumer has to filter on the jurisdiction label itself —
    "Map data only: Overall (33 jurisdictions; drugs of interest detected: 31
    jurisdictions)" — which embeds a count that shifts every release. The two
    aggregates are not interchangeable: the map one includes jurisdictions
    missing from intermediate years, so plotting it as a line would draw a series
    whose composition changes mid-range.
    """
    for row in rows:
        row["scope"] = (
            "map"
            if row.get("jurisdiction", "").startswith(_MAP_ONLY_PREFIX)
            else "chart"
        )
    return rows


def get_trend() -> list[dict]:
    """
    The jurisdiction-constant series, per trend range.

    This is the only cross-year-comparable table SUDORS publishes: each range
    restricts to jurisdictions present in *every* year of it, which is what the
    annual `Overall` row does not do.
    """
    return _add_scope(
        _melt_sheet("Overall Trend Data", ["jurisdiction", "trend_range", "data_year"])
    )


def get_trend_statistics() -> list[dict]:
    """
    Change between the first and last year of each range, by jurisdiction.

    Counts and rates change relatively (percent); percents change absolutely
    (percentage points). Not significance-tested: SUDORS is a census of the
    included jurisdictions, not a sample.
    """
    return _add_scope(_melt_sheet("Trend Statistics", ["jurisdiction", "trend_range"]))


def get_data_dictionary() -> list[dict]:
    """
    CDC's variable definitions, with the sheet's section banners promoted to a
    `section` column instead of left as bodiless rows.
    """
    out: list[dict] = []
    section = ""
    for row in _sheet_rows("Data Dictionary")[1:]:
        cells = [
            ("" if c is None else str(c).strip()) for c in (list(row) + [""] * 4)[:4]
        ]
        variable, description, fmt, corresponding = cells
        if not variable:
            continue
        if not description and not fmt:  # a section banner, not a variable
            section = variable
            continue
        out.append(
            {
                "section": section,
                "variable": variable,
                "description": description,
                "format": fmt,
                "corresponding_variable": corresponding,
            }
        )
    return out


# Registry key -> loader, for the CLI's generic `get`/`show` routing.
LOADERS: dict[str, Callable[[], list[dict]]] = {
    "drugs-involved": get_drugs_involved,
    "drugs-detected": get_drugs_detected,
    "circumstances": get_circumstances,
    "demographics": get_demographics,
    "demographics-by-sex-age": get_demographics_by_sex_age,
    "deaths-by-month": get_deaths_by_month,
    "opioid-stimulant": get_opioid_stimulant,
    "drug-combinations": get_drug_combinations,
    "top-combinations": get_top_combinations,
    "totals": get_totals,
    "overall-trend": get_trend,
    "trend-statistics": get_trend_statistics,
    "data-dictionary": get_data_dictionary,
}
