"""
ATSDR GRASP dataset registry.

GRASP (Geographic Research, Analysis, and Services Program) is a suite of
disease-specific REST APIs hosted at gis.cdc.gov/grasp/. Each application
exposes a GetData_JSON endpoint that returns patient-level or aggregate records.

No authentication is required. Datasets are fetched in full (no pagination).
FluView/FluSurv datasets are surfaced via the CMU Delphi Epidata API, which
pulls directly from CDC GRASP and provides a cleaner REST interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GraspDataset:
    url: str
    name: str
    description: str
    years: str
    key_columns: list[str] = field(default_factory=list)


_GRASP_BASE = "https://gis.cdc.gov/grasp"
_DELPHI_BASE = "https://api.delphi.cmu.edu/epidata"

DATASETS: dict[str, GraspDataset] = {
    "hantavirus": GraspDataset(
        url=f"{_GRASP_BASE}/HantavirusCaseViewAPI/GetData_JSON?appVersion=Public",
        name="Hantavirus Case View",
        description=(
            "Patient-level hantavirus cases reported to CDC's Viral Special Pathogens Branch "
            "and collected by NNDSS. Each record includes illness onset date, state FIPS code, "
            "and outcome (Alive/Dead/Unknown). Covers all confirmed US cases since before 1993."
        ),
        years="pre-1993–present",
        key_columns=["Patient", "IllnessOnsetDate", "StateFIPS", "Outcome"],
    ),
    "fluview_ili": GraspDataset(
        url=f"{_DELPHI_BASE}/fluview/",
        name="FluView ILINet — Influenza-Like Illness",
        description=(
            "Weekly influenza-like illness (ILI) activity from CDC's ILINet outpatient "
            "surveillance network. Sourced from CDC GRASP via the CMU Delphi Epidata API. "
            "Covers national, HHS region, census region, and all 50 state levels with "
            "weighted ILI percentage (wILI), raw ILI, patient counts, and provider counts."
        ),
        years="1997-98–present",
        key_columns=["region", "epiweek", "wili", "ili", "num_ili", "num_patients", "num_providers"],
    ),
    "fluview_clinical": GraspDataset(
        url=f"{_DELPHI_BASE}/fluview_clinical/",
        name="FluView WHO/NREVSS Clinical Labs",
        description=(
            "Weekly influenza testing data from WHO/NREVSS clinical laboratories. Sourced "
            "from CDC GRASP via the CMU Delphi Epidata API. Covers national, HHS region, "
            "census region, and state levels with specimen counts and percent positive for "
            "influenza A and B."
        ),
        years="2016-17–present",
        key_columns=[
            "region",
            "epiweek",
            "total_specimens",
            "total_a",
            "total_b",
            "percent_positive",
            "percent_a",
            "percent_b",
        ],
    ),
    "flusurv_net": GraspDataset(
        url=f"{_DELPHI_BASE}/flusurv/",
        name="FluSurv-NET Hospitalization Rates",
        description=(
            "Weekly lab-confirmed influenza hospitalization rates per 100,000 population from "
            "FluSurv-NET. Sourced from CDC GRASP via the CMU Delphi Epidata API. Covers 3 "
            "surveillance networks and 12 participating states, with rates stratified by age "
            "group (8 categories), race/ethnicity, sex, and flu type (A/B)."
        ),
        years="2009-10–present",
        key_columns=[
            "location",
            "season",
            "epiweek",
            "rate_overall",
            "rate_age_0",
            "rate_age_1",
            "rate_age_2",
            "rate_age_3",
            "rate_age_4",
            "rate_flu_a",
            "rate_flu_b",
            "rate_sex_male",
            "rate_sex_female",
        ],
    ),
}

# FIPS → state name lookup for display
STATE_FIPS: dict[str, str] = {
    "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas",
    "06": "California", "08": "Colorado", "09": "Connecticut", "10": "Delaware",
    "11": "District of Columbia", "12": "Florida", "13": "Georgia", "15": "Hawaii",
    "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa",
    "20": "Kansas", "21": "Kentucky", "22": "Louisiana", "23": "Maine",
    "24": "Maryland", "25": "Massachusetts", "26": "Michigan", "27": "Minnesota",
    "28": "Mississippi", "29": "Missouri", "30": "Montana", "31": "Nebraska",
    "32": "Nevada", "33": "New Hampshire", "34": "New Jersey", "35": "New Mexico",
    "36": "New York", "37": "North Carolina", "38": "North Dakota", "39": "Ohio",
    "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island",
    "45": "South Carolina", "46": "South Dakota", "47": "Tennessee", "48": "Texas",
    "49": "Utah", "50": "Vermont", "51": "Virginia", "53": "Washington",
    "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming",
}

# Valid FluSurv-NET location codes (3 networks + 12 participating states)
FLUSURV_LOCATIONS: dict[str, str] = {
    "network_all": "Entire FluSurv-NET Network",
    "network_eip": "Emerging Infections Program (EIP)",
    "network_ihsp": "Influenza Hospitalization Surveillance Project (IHSP)",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "GA": "Georgia",
    "MD": "Maryland",
    "MI": "Michigan",
    "MN": "Minnesota",
    "NM": "New Mexico",
    "OH": "Ohio",
    "OR": "Oregon",
    "TN": "Tennessee",
    "UT": "Utah",
}

# FluView region types and their valid values
# nat: national, hhs1-hhs10: HHS regions, cen1-cen9: census regions,
# state 2-letter codes (lowercase): al, ak, az, ar, ca, co, ct, de, fl, ga,
#   hi, id, il, in, ia, ks, ky, la, me, md, ma, mi, mn, ms, mo, mt, ne, nv,
#   nh, nj, nm, ny, nc, nd, oh, ok, or, pa, ri, sc, sd, tn, tx, ut, vt, va,
#   wa, wv, wi, wy
FLUVIEW_REGION_TYPES = ["nat", "hhs", "cen", "state"]
