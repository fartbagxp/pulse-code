"""NCHS Data Query System (DQS) dataset registry.

DQS is CDC/NCHS's unified query layer over the "Health, United States" report
family — it draws from the national surveys (NHANES, NHIS, NHAMCS, NVSS, NPALS,
NHCS) and publishes each topic as a plain Socrata dataset on data.cdc.gov with a
`DQS ...` title. Every one of them shares the *same* tidy schema:

    topic · subtopic · taxonomy · classification · group · subgroup
          · estimate_type · time_period · estimate · standard_error
          · estimate_lci · estimate_uci · footnote_id_list

Because the schema is uniform, one generic query verb (`pulse source dqs query`)
covers every dataset, and `classification`/`group`/`subgroup` are the demographic
breakdown the estimate is cut by ("Total" is the all-persons row).

This module is a curated snapshot of the 28 *current* (non-archived, non-footnote)
DQS data tables. Queries go straight to the live Socrata API via SodaClient, so
the numbers are never stale even if this metadata drifts. Year ranges reflect the
min/max `time_period` observed at registration time.

Reference: https://www.cdc.gov/nchs/dqs/  (data at https://data.cdc.gov, search "DQS")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DqsDataset:
    key: str  # stable registry key, e.g. "drug-overdose-deaths"
    id: str  # Socrata 4x4 ID, e.g. "rdjz-vn2n"
    name: str  # human-readable title
    topic: str  # pulse topic bucket this rolls up to
    survey: str  # source survey/system feeding the estimates
    years: str  # observed time_period coverage
    dimensions: list[str] = field(default_factory=list)  # available `classification` cuts


# Ordered roughly by topic relevance (mortality/natality first), matching the
# topic-first ordering used elsewhere in pulse. `topic` values line up with
# labels in topics_registry.py so `pulse source dqs list --topic <t>` filters cleanly.
_DATASETS: list[DqsDataset] = [
    # ── Mortality / cause-of-death (NVSS, mirrors CDC WONDER) ──────────────────
    DqsDataset("heart-disease-deaths", "7aq9-prdf", "Death rates for heart disease, by sex, race, Hispanic origin, and age", "Mortality", "NVSS", "2018–2024", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    DqsDataset("cancer-deaths", "h3hw-hzvg", "Death rates for malignant neoplasms, by sex, race, Hispanic origin, and age", "Cancer", "NVSS", "2018–2024", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    DqsDataset("suicide-deaths", "w26f-tf3h", "Death rates for suicide, by sex, race, Hispanic origin, and age", "Injury & Overdose", "NVSS", "2018–2024", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    DqsDataset("drug-overdose-deaths", "rdjz-vn2n", "Drug overdose death rates, by drug type, sex, age, race, and Hispanic origin", "Injury & Overdose", "NVSS", "2018–2024", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    # ── Birth / infant / fetal (NVSS) ─────────────────────────────────────────
    DqsDataset("infant-mortality", "j7ym-uwqy", "Infant, neonatal, and postneonatal mortality rates, by detailed race and Hispanic origin of mother", "Infant Mortality", "NVSS", "2017–2024", ["Total", "Demographic Characteristic"]),
    DqsDataset("fetal-perinatal-mortality", "wd75-kcmv", "Fetal, late fetal, and perinatal mortality rates, by detailed race and Hispanic origin of mother", "Fetal Deaths", "NVSS", "1995–2021", ["Total", "Demographic Characteristic"]),
    DqsDataset("birth-fertility-rates", "daba-4vfq", "Birth and fertility rates, by age group, race, and Hispanic origin of mother", "Natality", "NVSS", "2016–2024", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    DqsDataset("low-birthweight", "ga7k-kycn", "Low birthweight live births, by state", "Natality", "NVSS", "2014–2023", ["Total", "Geographic Characteristic"]),
    # ── Chronic disease & risk factors (NHANES) ───────────────────────────────
    DqsDataset("cholesterol-adults", "6tn6-vc33", "Cholesterol in adults age 20 and older, by selected characteristics", "Chronic Disease & Risk Factors", "NHANES", "1988–2020", ["Total", "Demographic Characteristic", "Socioeconomic Characteristic", "Multiple Characteristics"]),
    DqsDataset("hypertension-adults", "va5e-efw9", "Hypertension in adults age 20 and older, by selected characteristics", "Chronic Disease & Risk Factors", "NHANES", "1988–2020", ["Total", "Demographic Characteristic", "Socioeconomic Characteristic", "Multiple Characteristics"]),
    DqsDataset("chronic-conditions", "6rvp-rahv", "Select chronic conditions prevalence estimates", "Chronic Disease & Risk Factors", "NHANES", "1999–2023", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    # ── Nutrition, oral health, infectious prevalence (NHANES) ─────────────────
    DqsDataset("dietary-intake", "8ekv-ep3s", "Select mean dietary intake estimates", "Nutrition & Diet", "NHANES", "1999–2023", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    DqsDataset("oral-health", "36ue-xht5", "Select oral health prevalence estimates", "Oral Health", "NHANES", "1999–2018", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    DqsDataset("infectious-prevalence", "v7tk-n6v3", "Select infectious diseases prevalence estimates", "Infectious Disease Prevalence", "NHANES", "1999–2018", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    # ── Self-reported health & disability (NHIS) ──────────────────────────────
    DqsDataset("nhis-adult", "gj3i-hsbz", "NHIS adult summary health statistics", "Self-Reported Health", "NHIS", "2019–2024", ["Total", "Demographic Characteristic", "Geographic Characteristic", "Socioeconomic Characteristic"]),
    DqsDataset("nhis-child", "7ctq-myvs", "NHIS child summary health statistics", "Self-Reported Health", "NHIS", "2019–2024", ["Total", "Demographic Characteristic", "Geographic Characteristic", "Socioeconomic Characteristic"]),
    DqsDataset("functioning-difficulties", "btv3-srcc", "Functioning difficulties in adults age 18 and older, by selected characteristics", "Disability & Functioning", "NHIS", "2019–2024", ["Total", "Demographic Characteristic", "Geographic Characteristic", "Socioeconomic Characteristic"]),
    # ── Substance & medication use (NHANES / MTF) ─────────────────────────────
    DqsDataset("prescription-drug-use", "kusj-ex57", "Prescription medication use in the past 30 days, by sex, race and Hispanic origin, and age group", "Substance & Medication Use", "NHANES", "1988–2023", ["Total", "Demographic Characteristic", "Multiple Characteristics"]),
    DqsDataset("substance-use", "mtgp-t7vw", "Use of selected substances in the past 30 days among 8th, 10th, and 12th graders, by sex and race", "Substance & Medication Use", "MTF", "1980–2024", ["Total", "Socioeconomic Characteristic", "Multiple Characteristics"]),
    # ── Health-care system: capacity & utilization (NHAMCS / NHCS) ─────────────
    DqsDataset("hospital-beds", "8miz-siyd", "Community hospital beds, by state", "Health Care System", "NHCS", "1980–2023", ["Total", "Geographic Characteristic"]),
    DqsDataset("ed-visits", "e4ec-z5aa", "Estimate of emergency department visits in the United States", "Health Care System", "NHAMCS", "2016–2022", ["Total", "Demographic Characteristic", "Geographic Characteristic", "Socioeconomic Characteristic"]),
    DqsDataset("hospital-utilization", "4q35-rqzk", "Hospital admission, average length of stay, outpatient visits, and outpatient surgery, by ownership and size", "Health Care System", "NHCS", "1975–2023", ["Total", "Other Characteristic"]),
    # ── Health-care workforce ─────────────────────────────────────────────────
    DqsDataset("dentists", "yib5-h3pw", "Dentists, by state", "Health Care Workforce", "NCHS", "2001–2024", ["Total", "Geographic Characteristic"]),
    DqsDataset("healthcare-employment", "7siw-u4fz", "Health care employment and wages, by selected occupations", "Health Care Workforce", "BLS/NCHS", "2000–2024", ["Other Characteristic"]),
    # ── Health expenditure (CMS NHEA) ─────────────────────────────────────────
    DqsDataset("national-health-spending", "s57w-7gbe", "National health spending", "Health Expenditure", "CMS/NHEA", "1960–2024", ["Total", "Other Characteristic"]),
    DqsDataset("personal-healthcare-spending", "gu48-2cs8", "Personal healthcare spending", "Health Expenditure", "CMS/NHEA", "1960–2024", ["Total", "Other Characteristic"]),
    # ── Long-term care (NPALS) ────────────────────────────────────────────────
    DqsDataset("ltc-providers", "sz5x-j2c3", "National post-acute and long-term care providers", "Long-Term Care", "NPALS", "2020–2022", ["Total", "Geographic Characteristic", "Other Characteristic"]),
    DqsDataset("ltc-users", "6pdm-py4x", "National post-acute and long-term care users", "Long-Term Care", "NPALS", "2020–2022", ["Total", "Demographic Characteristic", "Socioeconomic Characteristic", "Other Characteristic"]),
]

_BY_KEY: dict[str, DqsDataset] = {d.key: d for d in _DATASETS}
_BY_ID: dict[str, DqsDataset] = {d.id: d for d in _DATASETS}


def datasets() -> list[DqsDataset]:
    """All registered DQS datasets, in topic-relevance order."""
    return list(_DATASETS)


def dataset(key_or_id: str) -> Optional[DqsDataset]:
    """Look up by registry key (e.g. 'drug-overdose-deaths') or Socrata ID ('rdjz-vn2n')."""
    return _BY_KEY.get(key_or_id) or _BY_ID.get(key_or_id)


def search(term: str) -> list[DqsDataset]:
    """Case-insensitive substring match over key, name, topic, and survey."""
    q = term.strip().lower()
    if not q:
        return list(_DATASETS)
    return [
        d
        for d in _DATASETS
        if q in d.key or q in d.name.lower() or q in d.topic.lower() or q in d.survey.lower()
    ]


def topics() -> list[str]:
    """Distinct topic buckets, preserving first-seen (relevance) order."""
    seen: dict[str, None] = {}
    for d in _DATASETS:
        seen.setdefault(d.topic, None)
    return list(seen)
