"""
Cross-source topic taxonomy — the topic-first entry point for `pulse topics`.

CDC's own data is organized by *source* (WONDER, SEER, WISQARS, GRASP, NSSP,
NIS, CDC Open Data) — each with its own dataset IDs and query vocabulary.
Nobody outside CDC thinks in those terms; they think "mortality," "cancer,"
"vaccination coverage." This module is the topic-first index over all seven
source catalogs: each Topic lists every source that actually covers it, with
one marked `is_default` — the source to reach for absent any other reason to
pick a different one.

Ordering and source coverage are grounded in the real catalog data (not
invented): WONDER's own `topic` field in data/catalog.json, cdc_open's
~65-dataset catalog, and the wisqars/grasp/nis/seer catalogs. See
sources_registry.py for the per-source dataset/URL/credit detail that
`pulse source <source>` drills into.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicSource:
    source: str  # key into sources_registry.SOURCE_DATASET_FNS
    coverage: str  # what this source covers *for this topic*
    years: str
    command: str  # a real, working example invocation
    is_default: bool = False


@dataclass(frozen=True)
class Topic:
    key: str
    label: str
    description: str
    sources: tuple[TopicSource, ...]


TOPICS: list[Topic] = [
    Topic(
        key="mortality",
        label="Mortality",
        description="Deaths by cause, place, and demographic group — the broadest cross-cutting topic.",
        sources=(
            TopicSource("wonder", "Provisional & final multi-cause mortality (D176 and related)", "1968–present", "pulse source wonder datasets --topic Mortality", is_default=True),
            TopicSource("cdc-open", "Leading causes of death, weekly/monthly provisional counts, historical rates back to 1900", "1900–present", "pulse source cdc-open query leading_death"),
            TopicSource("dqs", "Age-adjusted death rates for heart disease and other leading causes (Health, United States)", "2018–2024", "pulse source dqs trend heart-disease-deaths"),
        ),
    ),
    Topic(
        key="infant-mortality",
        label="Infant Mortality",
        description="Deaths under age 1, linked to birth certificate detail.",
        sources=(
            TopicSource("wonder", "Linked birth/infant death files", "1995–present", "pulse source wonder datasets --topic 'Infant Mortality'", is_default=True),
            TopicSource("dqs", "Infant, neonatal, and postneonatal mortality rates by detailed race/Hispanic origin of mother", "2017–2024", "pulse source dqs trend infant-mortality"),
        ),
    ),
    Topic(
        key="fetal-deaths",
        label="Fetal Deaths",
        description="Stillbirths and fetal death reporting.",
        sources=(
            TopicSource("wonder", "Fetal death dataset(s)", "2005–present", "pulse source wonder datasets --topic 'Fetal Deaths'", is_default=True),
            TopicSource("dqs", "Fetal, late fetal, and perinatal mortality rates by detailed race/Hispanic origin of mother", "1995–2021", "pulse source dqs trend fetal-perinatal-mortality"),
        ),
    ),
    Topic(
        key="natality",
        label="Natality",
        description="Births — counts, rates, and maternal/newborn characteristics.",
        sources=(
            TopicSource("wonder", "Natality detail files", "1995–present", "pulse source wonder datasets --topic Natality", is_default=True),
            TopicSource("cdc-open", "Quarterly birth indicators", "current", "pulse source cdc-open query birth_indicators"),
            TopicSource("dqs", "Birth & fertility rates by age group/race; low birthweight live births by state", "2014–2024", "pulse source dqs trend birth-fertility-rates"),
        ),
    ),
    Topic(
        key="population",
        label="Population",
        description="Bridged-race population estimates used as denominators for rate calculations.",
        sources=(
            TopicSource("wonder", "Bridged-race population estimates", "1990–present", "pulse source wonder datasets --topic Population", is_default=True),
        ),
    ),
    Topic(
        key="cancer",
        label="Cancer",
        description="Incidence and mortality by cancer site, age, sex, and race.",
        sources=(
            TopicSource("seer", "Site-level incidence/mortality trends, age-adjusted, by sex/race", "1975–present", "pulse source seer mortality --site 55", is_default=True),
            TopicSource("wonder", "US Cancer Statistics (USCS) — official combined NPCR+SEER national aggregate", "1999–present", "pulse source wonder datasets --topic Cancer"),
            TopicSource("dqs", "Age-adjusted malignant-neoplasm death rates by sex/race (Health, United States)", "2018–2024", "pulse source dqs trend cancer-deaths"),
        ),
    ),
    Topic(
        key="injury",
        label="Injury & Overdose",
        description="Firearm, overdose, homicide, and suicide deaths, with geographic breakdowns.",
        sources=(
            TopicSource("wisqars", "Injury mortality by intent/mechanism — national, state, county, census-tract", "1999–present", "pulse source wisqars state --intent FA_Deaths --year 2023", is_default=True),
            TopicSource("cdc-open", "Provisional/county-level drug overdose deaths", "1999–present", "pulse source cdc-open query drug_overdose_vsrr"),
            TopicSource("wonder", "Drug/homicide/suicide detail via multi-cause mortality", "1999–present", "pulse source wonder datasets --topic Mortality"),
            TopicSource("dqs", "Age-adjusted suicide and drug-overdose death rates by drug type (Health, United States)", "2018–2024", "pulse source dqs trend drug-overdose-deaths"),
            TopicSource("sudors", "Specific drugs from postmortem toxicology (xylazine, nitazenes, carfentanil) plus death circumstances — 49 states + DC, not a national census", "2020–2024", "pulse source sudors drugs --detected -y 2024 -j Overall"),
        ),
    ),
    Topic(
        key="chronic-disease",
        label="Chronic Disease & Risk Factors",
        description="Measured prevalence of cardiovascular risk factors and chronic conditions from NHANES exams.",
        sources=(
            TopicSource("dqs", "Cholesterol, hypertension, and select chronic-condition prevalence in adults, by demographics", "1988–2023", "pulse source dqs list --topic 'Chronic Disease'", is_default=True),
        ),
    ),
    Topic(
        key="nutrition",
        label="Nutrition & Diet",
        description="Mean dietary intake estimates from NHANES 24-hour recall.",
        sources=(
            TopicSource("dqs", "Select mean dietary intake estimates by age, sex, race", "1999–2023", "pulse source dqs trend dietary-intake", is_default=True),
        ),
    ),
    Topic(
        key="oral-health",
        label="Oral Health",
        description="Dental caries, untreated decay, and other oral-health prevalence from NHANES.",
        sources=(
            TopicSource("dqs", "Select oral-health prevalence estimates by demographics", "1999–2018", "pulse source dqs trend oral-health", is_default=True),
        ),
    ),
    Topic(
        key="self-reported-health",
        label="Self-Reported Health",
        description="Adult and child summary health statistics from the National Health Interview Survey.",
        sources=(
            TopicSource("dqs", "NHIS adult & child summary statistics — health status, conditions, access, behaviors", "2019–2024", "pulse source dqs query nhis-adult --where \"classification='Total'\"", is_default=True),
        ),
    ),
    Topic(
        key="disability",
        label="Disability & Functioning",
        description="Functioning difficulties (vision, hearing, mobility, cognition) in adults, from NHIS.",
        sources=(
            TopicSource("dqs", "Functioning difficulties in adults age 18+, by selected characteristics", "2019–2024", "pulse source dqs trend functioning-difficulties", is_default=True),
        ),
    ),
    Topic(
        key="substance-use",
        label="Substance & Medication Use",
        description="Self-reported prescription and illicit substance use — distinct from overdose mortality.",
        sources=(
            TopicSource("dqs", "Prescription-medication use (NHANES) and substance use among 8th/10th/12th graders (MTF)", "1980–2023", "pulse source dqs trend prescription-drug-use", is_default=True),
        ),
    ),
    Topic(
        key="infectious-prevalence",
        label="Infectious Disease Prevalence",
        description="Serologic prevalence of select infectious diseases measured in NHANES.",
        sources=(
            TopicSource("dqs", "Select infectious-disease prevalence estimates by demographics", "1999–2018", "pulse source dqs trend infectious-prevalence", is_default=True),
        ),
    ),
    Topic(
        key="respiratory",
        label="Respiratory Illness",
        description="COVID/flu/RSV activity — ED visits, hospitalizations, and ILI, real-time and historical.",
        sources=(
            TopicSource("nssp", "Emergency department visit % for COVID/flu/RSV, by geography", "2022–present", "pulse source nssp hhs influenza --region 4", is_default=True),
            TopicSource("grasp", "FluView ILI/clinical labs, FluSurv-NET hospitalization rates", "1997–present", "pulse source grasp fluview ili data --region nat"),
            TopicSource("cdc-open", "COVID-NET/RESP-NET/RSV-NET hospitalizations, wastewater viral activity", "2017–present", "pulse source cdc-open query covid_net"),
        ),
    ),
    Topic(
        key="vaccination-coverage",
        label="Vaccination Coverage",
        description="What fraction of a population is vaccinated — by age group, vaccine, and geography.",
        sources=(
            TopicSource("nis", "Childhood (19-35mo) and teen (13-17yr) vaccination survey, UTD rates by state", "2011–present", "pulse source nis rates child 2022", is_default=True),
            TopicSource("cdc-open", "SchoolVaxView (kindergarten), adult, pregnant-women, nursing-home, HCP coverage", "2005–present", "pulse source cdc-open query schoolvaxview"),
        ),
    ),
    Topic(
        key="vaccine-safety",
        label="Vaccine Safety",
        description="Reported adverse events following vaccination (VAERS).",
        sources=(
            TopicSource("wonder", "VAERS — vaccine adverse event reports (D8)", "1990–present", "pulse source wonder datasets --topic 'Vaccine Safety'", is_default=True),
        ),
    ),
    Topic(
        key="measles",
        label="Measles",
        description="Current measles outbreak activity and its wastewater surveillance signal.",
        sources=(
            TopicSource("cdc-open", "NNDSS weekly measles cases; measles wastewater RNA signal", "2014–present", "pulse source cdc-open query nndss_measles", is_default=True),
            TopicSource("wonder", "NNDSS Annual Summary (historical, all notifiable diseases)", "1996–present", "pulse source wonder datasets --topic 'Infectious Disease'"),
        ),
    ),
    Topic(
        key="wastewater",
        label="Wastewater Surveillance",
        description="Pathogen RNA signal in municipal wastewater — an early-warning proxy for case counts.",
        sources=(
            TopicSource("cdc-open", "NWSS wastewater viral activity — SARS-CoV-2, flu A, RSV, measles, H5", "2020–present", "pulse source cdc-open query wastewater_covid", is_default=True),
        ),
    ),
    Topic(
        key="foodborne",
        label="Foodborne Disease",
        description="Enteric pathogen surveillance from CDC's BEAM dashboard.",
        sources=(
            TopicSource("cdc-open", "Monthly human isolate counts — Salmonella, STEC, Campylobacter, Shigella, Vibrio", "2018–present", "pulse source cdc-open query beam_report", is_default=True),
        ),
    ),
    Topic(
        key="tick-borne",
        label="Tick-borne Disease",
        description="Lyme disease and other tick-borne notifiable disease case counts.",
        sources=(
            TopicSource("wonder", "NNDSS Annual Summary Data (D130) — Lyme disease and other notifiable diseases", "1996–present", "pulse source wonder datasets --topic 'Infectious Disease'", is_default=True),
        ),
    ),
    Topic(
        key="sti",
        label="STI / Sexual Health",
        description="Chlamydia, gonorrhea, syphilis, and other sexually transmitted infection surveillance.",
        sources=(
            TopicSource("wonder", "STI-specific mortality/surveillance datasets", "varies", "pulse source wonder datasets --topic 'STI / Sexual Health'", is_default=True),
            TopicSource("cdc-open", "NNDSS weekly chlamydia, gonorrhea, syphilis tables", "2014–present", "pulse source cdc-open query nndss_sti_chlamydia"),
        ),
    ),
    Topic(
        key="tuberculosis",
        label="Tuberculosis",
        description="TB case counts and mortality.",
        sources=(
            TopicSource("wonder", "TB surveillance dataset", "varies", "pulse source wonder datasets --topic Tuberculosis", is_default=True),
        ),
    ),
    Topic(
        key="hiv-aids",
        label="HIV/AIDS",
        description="HIV/AIDS case counts and mortality.",
        sources=(
            TopicSource("wonder", "HIV/AIDS surveillance dataset", "varies", "pulse source wonder datasets --topic 'HIV/AIDS'", is_default=True),
        ),
    ),
    Topic(
        key="health-care-system",
        label="Health Care System",
        description="Capacity and utilization — hospital beds, emergency-department visits, admissions and length of stay.",
        sources=(
            TopicSource("dqs", "Community hospital beds, ED-visit estimates, and hospital admission/LOS/outpatient measures", "1975–2023", "pulse source dqs list --topic 'Health Care System'", is_default=True),
        ),
    ),
    Topic(
        key="health-care-workforce",
        label="Health Care Workforce",
        description="Supply and wages of health-care providers.",
        sources=(
            TopicSource("dqs", "Dentists by state; health-care employment and wages by occupation", "2000–2024", "pulse source dqs list --topic 'Health Care Workforce'", is_default=True),
        ),
    ),
    Topic(
        key="health-expenditure",
        label="Health Expenditure",
        description="National and personal health-care spending (CMS National Health Expenditure Accounts).",
        sources=(
            TopicSource("dqs", "National health spending and personal health-care spending series", "1960–2024", "pulse source dqs trend national-health-spending", is_default=True),
        ),
    ),
    Topic(
        key="long-term-care",
        label="Long-Term Care",
        description="Post-acute and long-term-care providers and the people they serve (NPALS).",
        sources=(
            TopicSource("dqs", "National post-acute and long-term-care providers and users", "2020–2022", "pulse source dqs list --topic 'Long-Term Care'", is_default=True),
        ),
    ),
    Topic(
        key="environment",
        label="Environment",
        description="Environmental exposure and hazard datasets (e.g. heat, air quality-linked mortality).",
        sources=(
            TopicSource("wonder", "Environmental datasets", "varies", "pulse source wonder datasets --topic Environment", is_default=True),
        ),
    ),
]


def find_topic(query: str) -> Topic | None:
    """Case-insensitive lookup by key or label (substring match, first hit wins)."""
    q = query.strip().lower()
    for t in TOPICS:
        if q == t.key or q == t.label.lower():
            return t
    for t in TOPICS:
        if q in t.key or q in t.label.lower():
            return t
    return None
