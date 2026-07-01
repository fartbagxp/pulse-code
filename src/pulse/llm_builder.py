"""LLM-powered CDC WONDER query builder using Anthropic Claude."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Age variables — AAR is incompatible when grouping by these
_AGE_VARS = {
    "D176.V5",
    "D176.V51",
    "D176.V52",
    "D176.V6",
    "D157.V5",
    "D157.V51",
    "D157.V52",
    "D157.V6",
    "D158.V5",
    "D158.V51",
    "D158.V52",
    "D158.V6",
    "D141.V5",
    "D141.V51",
    "D141.V52",
    "D141.V6",
    "D77.V5",
    "D77.V51",
    "D77.V52",
    "D77.V6",
    "D76.V5",
    "D76.V51",
    "D76.V52",
    "D76.V6",
    "D74.V5",
    "D74.V6",
    "D16.V5",
    "D16.V6",
    "D140.V5",
    "D140.V6",
}

_SYSTEM_PROMPT = """\
You are a CDC WONDER query builder. Convert natural language into WONDER API XML queries.

## Dataset Selection Guide

### Mortality — Recent/Provisional (use for current trends)
- D176: Provisional Mortality 2018–present (weekly updates; default for recent mortality)
- D157: Final MCD+UCD Single Race 2018–2023 (finalized; single-race detail)
- D158: Final UCD Single Race 2018–2023 (no MCD filters; use for maternal mortality)

### Mortality — Historical ICD-10 (1999–2020)
- D77: Multiple Cause of Death 1999–2020 (drug overdose deaths; MCD filters)
- D76: Underlying Cause of Death 1999–2020 (suicide, cause-specific; no MCD)
- D141: MCD with US-Mexico Border 1999–2020 (adds border/metro geography)

### Mortality — Older ICD
- D140: Compressed Mortality 1999–2016 (simpler; no MCD)
- D16: Compressed Mortality 1979–1998 (ICD-9)
- D74: Compressed Mortality 1968–1978 (ICD-8)

### Infant Mortality (Linked Birth/Death)
- D69: Linked Birth/Infant Death 2007–2023 (default for infant mortality)
- D159: Linked Birth/Infant Death Expanded 2017–2023 (more race/ethnicity detail)
- D31: Linked Birth/Infant Death 2003–2006
- D18: Linked Birth/Infant Death 1999–2002
- D23: Linked Birth/Infant Death 1995–1998

### Natality (Live Births)
- D66: Natality 2007–2024 (default for birth data)
- D149: Natality Expanded 2016–2024 (single-race detail)
- D192: Provisional Natality 2023–present (latest; limited groupings)
- D27: Natality 2003–2006
- D10: Natality 1995–2002

### Environmental / Climate
- D104: Heat Wave Days 1981–2010 (annual county-level)
- D60: NLDAS Air Temperatures/Heat Index 1979–2011
- D80: NLDAS Daily Sunlight 1979–2011
- D81: NLDAS Daily Precipitation 1979–2011
- D61: MODIS Land Surface Temperature 2003–2008
- D73: Fine Particulate Matter PM2.5 2003–2011

### Vaccine Safety
- D8: VAERS 1990–present (adverse event reports, not incidence)

## Group-By Variables (B_1 through B_5)

### D176 (Provisional Mortality) — key B_ values
  D176.V1-level1    Year
  D176.V1-level2    Month
  D176.V9-level1    Residence State
  D176.V9-level2    Residence County
  D176.V10-level1   Census Region
  D176.V27-level1   HHS Region
  D176.V19          2013 Urbanization
  D176.V2-level1    ICD-10 Chapter (cause of death)
  D176.V2-level2    ICD-10 Subcategory
  D176.V13-level3   MCD Drug/Alcohol Cause Code
  D176.V5           Ten-Year Age Groups
  D176.V51          Five-Year Age Groups
  D176.V6           Infant Age Groups
  D176.V7           Gender/Sex
  D176.V42          Race/Ethnicity (bridged)
  D176.V43          Single Race (Hispanic origin)
  D176.V44          Hispanic Origin

### D77 / D76 (Historical Mortality 1999–2020) — key B_ values
  D77.V1-level1     Year           D76.V1-level1    Year
  D77.V1-level2     Month          D76.V1-level2    Month
  D77.V9-level1     State          D76.V9-level1    State
  D77.V2-level1     ICD Chapter    D76.V2-level1    ICD Chapter
  D77.V13-level3    MCD Drug Code
  D77.V5            Ten-Year Age   D76.V5           Ten-Year Age
  D77.V7            Gender/Sex     D76.V7           Gender/Sex
  D77.V8            Race (bridged) D76.V8           Race (bridged)

### D158 (UCD Single Race 2018–2023) — key B_ values
  D158.V1-level1    Year
  D158.V1-level2    Month
  D158.V9-level1    State
  D158.V2-level1    ICD Chapter
  D158.V2-level2    ICD Subcategory
  D158.V5           Ten-Year Age
  D158.V7           Gender/Sex
  D158.V42          Single Race

### D66 (Natality 2007–2024) — key B_ values
  D66.V6-level1     Year
  D66.V6-level2     Month
  D66.V9-level1     State
  D66.V2            Mother's Age
  D66.V7            Race/Hispanic origin (4-category)
  D66.V13           Gestational age (weekly)
  D66.V14           Birth weight (grams)
  D66.V5            Delivery method

### D69 (Infant Mortality 2007–2023) — key B_ values
  D69.V1-level1     Year
  D69.V9-level1     State
  D69.V2-level1     ICD Chapter (cause of death)
  D69.V4            Age at death (neonatal/post-neonatal)
  D69.V7            Gender
  D69.V8            Race (bridged)

### D8 (VAERS) — key B_ values
  D8.V14-level1     Vaccine Type
  D8.V14-level2     Vaccine (specific product)
  D8.V13-level2     Symptom
  D8.V2-level1      Year Received
  D8.V1             Age Group
  D8.V5             Sex
  D8.V11            Event Category (Death, Hospitalized, Life Threatening)

## Filters (F_* and V_*)

### Common filter patterns (D176):
  F_D176.V1 = *All* (or year codes like "2020","2021")
  F_D176.V9 = *All* (state FIPS codes for specific states)
  F_D176.V2 = *All* (all ICD chapters; or specific chapter codes)
  F_D176.V13 = *All* (all drug codes; V_D176.V13 for specific ICD codes)
  V_D176.V13 = T40.1\\nT40.2\\nT40.3\\nT40.4  (specific opioid codes — newline separated)
  V_D176.V7 = M or F  (sex filter)
  V_D176.V42 = *All*  (all races)

### Drug ICD-10 codes (for V_*.V13 in D176/D77):
  T40.1  Heroin
  T40.2  Other opioids (oxycodone, hydrocodone, etc.)
  T40.3  Methadone
  T40.4  Other synthetic narcotics (fentanyl)
  T40.5  Cocaine
  T40.7  Cannabis
  T43.6  Psychostimulants (meth, amphetamines, MDMA)

### Suicide ICD-10 codes (for F_*.V2 underlying cause):
  X60-X84  Intentional self-harm (ICD-10 chapter for suicide)

### Maternal mortality (D158):
  Underlying cause filter: O00-O99 (pregnancy/childbirth chapter)

## Mode Selectors (must match active filter/groupby)
  O_ucd = D{N}.V2   when filtering by ICD chapter
  O_ucd = D{N}.V25  when filtering by drug/alcohol cause (simple)
  O_mcd = D{N}.V13  when filtering by MCD drug codes
  O_age = D{N}.V5   when grouping by 10-year age
  O_age = D{N}.V51  when grouping by 5-year age
  O_age = D{N}.V6   when grouping by infant age

## Measures
  M_1 = D{N}.M1  Deaths (or Births/Events)
  M_2 = D{N}.M2  Population
  M_3 = D{N}.M3  Crude Rate
  M_9 = D{N}.M9  Age-Adjusted Rate (mortality only; disable with O_aar_enable=false when grouping by age)

## Output Options
  O_rate_per = 100000    rate denominator
  O_show_totals = true   include grand total row
  O_aar_enable = false   disable AAR (required when grouping by age)
  O_aar = aar_none       (goes with O_aar_enable=false)

## Rules
1. Select the most appropriate dataset based on topic and year range.
2. Specify B_1..B_5 group-by slots — use *None* for unused slots.
3. Set mode selectors (O_ucd/O_age) to match your active filter or group-by.
4. Set O_aar_enable=false when grouping by any age variable.
5. Output OVERRIDES ONLY — the base template fills in all boilerplate (V_*, I_*, finder-stage-*, VM_*).
6. Do NOT output finder-stage-*, O_*_fmode, I_*, or VM_* — those come from the template.
"""

_TOOL_SCHEMA = {
    "name": "build_wonder_query",
    "description": (
        "Output OVERRIDES for a CDC WONDER XML query. "
        "The base template fills in boilerplate. You only need B_1..B_5, "
        "F_* filters, V_* value filters, O_ucd/O_age mode selectors, "
        "O_aar_enable, and non-default measures."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "CDC WONDER dataset code (e.g. D176, D77, D66)",
            },
            "parameters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "values": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "values"],
                },
                "description": "Override parameters only (B_*, F_*, V_*, O_*, M_*)",
            },
        },
        "required": ["dataset_id", "parameters"],
    },
}


class WonderParam(BaseModel):
    name: str
    values: list[str]


class WonderRequest(BaseModel):
    dataset_id: str
    parameters: list[WonderParam] = Field(default_factory=list)

    def to_xml(self) -> str:
        lines = ['<?xml version="1.0" encoding="UTF-8"?><request-parameters>']
        for p in self.parameters:
            lines.append("\t<parameter>")
            lines.append(f"\t\t<name>{p.name}</name>")
            for v in p.values:
                if v:
                    lines.append(f"\t\t<value>{v}</value>")
                else:
                    lines.append("\t\t<value/>")
            lines.append("\t</parameter>")
        lines.append("</request-parameters>")
        return "\n".join(lines)


def _load_template(dataset_id: str) -> Optional[str]:
    path = _TEMPLATES_DIR / f"{dataset_id}-base.xml"
    return path.read_text() if path.exists() else None


def _parse_xml_params(xml_str: str) -> list[WonderParam]:
    root = ET.fromstring(xml_str)
    params = []
    for param in root.findall("parameter"):
        name_el = param.find("name")
        if name_el is None or name_el.text is None:
            continue
        values = [v.text or "" for v in param.findall("value")]
        params.append(WonderParam(name=name_el.text, values=values))
    return params


def _merge_overrides(template_xml: str, overrides: list[WonderParam]) -> str:
    base_params = _parse_xml_params(template_xml)
    index = {p.name: i for i, p in enumerate(base_params)}

    for override in overrides:
        if override.name in index:
            base_params[index[override.name]] = override
        else:
            base_params.append(override)

    dataset_id = next(
        (p.values[0] for p in base_params if p.name == "dataset_code"),
        "D176",
    )
    return WonderRequest(dataset_id=dataset_id, parameters=base_params).to_xml()


def _apply_constraints(overrides: list[WonderParam]) -> list[WonderParam]:
    """Enforce CDC WONDER rules: disable AAR when grouping by age."""
    by_name = {p.name: p for p in overrides}
    group_by_values = {
        v for k, p in by_name.items() if k.startswith("B_") for v in p.values
    }
    if group_by_values & _AGE_VARS:
        by_name["O_aar_enable"] = WonderParam(name="O_aar_enable", values=["false"])
        by_name["O_aar"] = WonderParam(name="O_aar", values=["aar_none"])
        by_name["O_aar_CI"] = WonderParam(name="O_aar_CI", values=["false"])
    return list(by_name.values())


class LLMQueryBuilder:
    """Build or refine CDC WONDER queries using Claude as the reasoning engine."""

    def __init__(
        self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6"
    ) -> None:
        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = model

    def build(
        self,
        prompt: str,
        base_xml: Optional[str] = None,
        max_tokens: int = 4096,
        on_thinking: Optional[callable] = None,
    ) -> WonderRequest:
        """
        Build a WONDER query from natural language.

        Args:
            prompt: Natural language description of the desired query.
            base_xml: Optional existing query XML to use as starting context for refinement.
            max_tokens: Max tokens for LLM.
            on_thinking: Optional callback(text) called with LLM reasoning text.
        """
        user_content = prompt
        if base_xml:
            user_content = (
                f"Starting from this existing query, modify it as requested:\n\n"
                f"<existing-query>\n{base_xml}\n</existing-query>\n\n"
                f"Modification request: {prompt}"
            )

        messages = [{"role": "user", "content": user_content}]

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            tool_block = next(
                (
                    b
                    for b in response.content
                    if b.type == "tool_use" and b.name == "build_wonder_query"
                ),
                None,
            )

            if tool_block:
                raw = WonderRequest(**tool_block.input)
                template = _load_template(raw.dataset_id)
                if template:
                    constrained = _apply_constraints(raw.parameters)
                    merged_xml = _merge_overrides(template, constrained)
                    merged_params = _parse_xml_params(merged_xml)
                    return WonderRequest(
                        dataset_id=raw.dataset_id, parameters=merged_params
                    )
                return raw

            text = "".join(getattr(b, "text", "") for b in response.content)

            if on_thinking:
                on_thinking(text)

            if response.stop_reason == "end_turn":
                import re as _re

                dataset_matches = _re.findall(r"\b(D\d+)\b", text)
                if dataset_matches:
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Please proceed with dataset {dataset_matches[0]}.",
                        }
                    )
                    continue
                raise ValueError(f"LLM did not produce a query. Response: {text[:300]}")

            raise ValueError(f"Unexpected stop reason: {response.stop_reason}")
