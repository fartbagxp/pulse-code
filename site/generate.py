#!/usr/bin/env python3
"""Generate the static site explaining CDC WONDER XML query structure.

Pure stdlib — no runtime dependency on the pulse package or anthropic.
Reads real bundled queries + the dataset catalog so the site can't drift
from what the CLI actually produces.

Look and feel is modeled on https://fartbagxp.github.io/venture/ — same
CSS custom properties, font stack, and component patterns (nav, hero
kicker, code-pill, chapter sections).
"""

from __future__ import annotations

import html
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

_SITE_DIR = Path(__file__).parent
_REPO_ROOT = _SITE_DIR.parent
_QUERIES_DIR = _REPO_ROOT / "src" / "pulse" / "queries"
_CATALOG_PATH = _REPO_ROOT / "src" / "pulse" / "data" / "catalog.json"
_QUERIES_INDEX_PATH = _REPO_ROOT / "src" / "pulse" / "data" / "queries_index.json"
_VARIABLE_LABELS_PATH = _REPO_ROOT / "src" / "pulse" / "data" / "variable_labels.json"
_DIST_DIR = _SITE_DIR / "dist"

# Plain-English explanations for boilerplate parameters — not tied to any
# specific dataset variable.
BOILERPLATE_HELP = {
    "action-Send": "Submit trigger. CDC WONDER only processes the request when this is present with value 'Send'.",
    "dataset_code": "Which CDC WONDER dataset to query (e.g. D202 for Tuberculosis).",
    "dataset_label": "Human-readable dataset name, echoed back in the response header.",
    "dataset_vintage": "Dataset revision/vintage identifier — usually left blank.",
    "dataset_vintage_latest": "Which vintage (version) of this dataset to use.",
    "stage": "Always 'request' — tells WONDER this is a data request, not a form page render.",
}

# Plain-English explanations for common O_* output/mode options that aren't
# themselves a reference to a dataset variable.
O_HELP = {
    "O_rate_per": "Denominator for computed rates — e.g. 100000 means 'per 100,000 people'.",
    "O_show_totals": "Whether to include a grand-total row in the results.",
    "O_show_zeros": "Whether to include rows where the count is zero.",
    "O_show_suppressed": "Whether to include rows CDC suppressed for small counts (shown as 'Suppressed', not a real number).",
    "O_precision": "How many decimal places to show on computed rates.",
    "O_timeout": "Server-side timeout for the request, in seconds.",
    "O_javascript": "Internal form flag copied from the web UI — always 'on'.",
    "O_export-format": "File format used when exporting results (e.g. xls).",
    "O_title": "Optional custom title for the result set.",
    "O_oc-sect1-request": "Internal UI state for the request form's collapsible section — has no effect on the data.",
    "O_aar_enable": "Whether to calculate Age-Adjusted Rate. Must be 'false' when grouping by age.",
    "O_aar": "Which Age-Adjusted Rate standard population to use.",
    "O_aar_CI": "Whether to include confidence intervals on the Age-Adjusted Rate.",
    "O_change_action-Send-Export Results": "Internal flag tied to the 'Export Results' button's state.",
}


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    color: str
    description: str

    def matches(self, name: str) -> bool:
        if self.key == "finder-stage":
            return name.startswith("finder-stage-")
        if self.key == "boilerplate":
            return not any(
                name.startswith(p) for p in ("B_", "F_", "I_", "M_", "O_", "V_")
            )
        return name.startswith(f"{self.key}_")


# Source of truth for both the legend and the per-line highlighting —
# transcribed from docs/building-xml-queries.md.
CATEGORIES: list[Category] = [
    Category(
        "B",
        "Group-By",
        "#60a5fa",
        "Which dimensions appear as rows (B_1 through B_5). Unused slots are *None*.",
    ),
    Category(
        "F",
        "Finder Filter",
        "#fb923c",
        "Filter select for a hierarchical codelist (e.g. ICD chapters). Paired with an I_* and finder-stage-*.",
    ),
    Category(
        "I",
        "Finder Text Input",
        "#facc15",
        "Empty text-input companion to an F_* finder filter.",
    ),
    Category(
        "finder-stage",
        "Finder Stage",
        "#f97316",
        "Declares that a variable uses codeset (hierarchical) filter mode.",
    ),
    Category(
        "M",
        "Measure",
        "#c084fc",
        "What's counted: deaths, births, cases, population, crude rate, age-adjusted rate.",
    ),
    Category(
        "O",
        "Option / Mode Selector",
        "#ff4b4b",
        "Output options and radio-button mode selectors (e.g. O_age picks which age variable is active). Omitting a required one causes HTTP 500.",
    ),
    Category(
        "V",
        "Value Filter",
        "#86efac",
        "Dropdown filter for a specific value (e.g. year, state, sex). *All* means no restriction.",
    ),
    Category(
        "boilerplate",
        "Boilerplate",
        "#85837e",
        "Required metadata: dataset_code, dataset_label, stage, action-Send.",
    ),
]

_CATEGORY_BY_KEY = {c.key: c for c in CATEGORIES}

# Topic → accent color, tuned for readability on the dark theme.
TOPIC_COLORS = {
    "Mortality": "#f87171",
    "Infant Mortality": "#fb923c",
    "Fetal Deaths": "#f97316",
    "Natality": "#4ade80",
    "Cancer": "#e879f9",
    "Infectious Disease": "#22d3ee",
    "STI / Sexual Health": "#67e8f9",
    "Tuberculosis": "#facc15",
    "HIV/AIDS": "#ef4444",
    "Vaccine Safety": "#c084fc",
    "Environment": "#60a5fa",
    "Population": "#9ca3af",
}


def categorize(name: str) -> Category:
    for cat in CATEGORIES:
        if cat.matches(name):
            return cat
    return _CATEGORY_BY_KEY["boilerplate"]


def load_catalog() -> dict[str, dict]:
    raw = json.loads(_CATALOG_PATH.read_text())
    return {d["id"]: d for d in raw["datasets"]}


def load_queries_index() -> list[dict]:
    raw = json.loads(_QUERIES_INDEX_PATH.read_text())
    return raw["queries"]


def load_variable_labels() -> dict[str, dict[str, str]]:
    return json.loads(_VARIABLE_LABELS_PATH.read_text())


def explain_parameter(
    name: str,
    values: list[str],
    dataset_id: str,
    variable_labels: dict[str, dict[str, str]],
    catalog: dict[str, dict],
) -> str:
    """Plain-English explanation of what this exact parameter does — not
    just its category, but what B_1=D202.V20 actually means (Year)."""

    def lookup(code: str) -> str | None:
        # Finder/value parameter names reference the base variable code
        # (e.g. "D150.V22"), but multi-level variables are only keyed by
        # their "-level1"/"-level2" variants (e.g. "D150.V22-level1").
        if code in labels:
            return labels[code]
        return labels.get(f"{code}-level1")

    cat = categorize(name)
    labels = variable_labels.get(dataset_id, {})
    dataset = catalog.get(dataset_id, {})
    val = values[0] if values else ""

    if cat.key == "B":
        if val == "*None*":
            return (
                "Unused group-by slot — this row won't be split out by anything extra."
            )
        label = lookup(val) or val
        return f"Splits the results out by {label}."

    if cat.key in ("F", "V", "I"):
        code = name.split("_", 1)[1] if "_" in name else name
        label = lookup(code) or code
        if cat.key == "F":
            return f"Filter picker for {label} — lets you narrow results down to specific {label.lower()} values before sending the request."
        if cat.key == "I":
            return f"Blank text box paired with the {label} filter above, for typing a custom search term."
        if val == "*All*" or not val:
            return f"Filter on {label}: not restricted here — every value is included."
        shown = ", ".join(values[:5]) + ("…" if len(values) > 5 else "")
        return f"Filter on {label}, restricted to: {shown}."

    if cat.key == "finder-stage":
        code = name[len("finder-stage-") :]
        label = lookup(code) or code
        return f"Tells WONDER that {label} uses the multi-level picker (needed whenever a filter on {label} is present)."

    if cat.key == "M":
        measure = next(
            (m for m in dataset.get("measures", []) if m["code"] == val), None
        )
        return (
            f"Includes {measure['label']} as a column in the results."
            if measure
            else "A number or rate included as a column in the results."
        )

    if cat.key == "O":
        if name in O_HELP:
            return O_HELP[name]
        if name.endswith("_fmode"):
            return "Tells WONDER to use the standard filter mode for the paired finder variable above."
        label = lookup(val)
        if label:
            return f"Required selection — tells WONDER to use {label} here. Missing this causes an HTTP 500 error."
        return "A required output setting or radio-button selection for this dataset."

    return BOILERPLATE_HELP.get(name, "Required request metadata — always sent as-is.")


def queries_by_dataset(queries: list[dict]) -> dict[str, list[dict]]:
    by_ds: dict[str, list[dict]] = {}
    for q in queries:
        by_ds.setdefault(q["dataset_id"], []).append(q)
    return by_ds


def parse_params(filename: str) -> list[tuple[str, list[str]]]:
    xml_text = (_QUERIES_DIR / filename).read_text()
    root = ET.fromstring(xml_text)
    params = []
    for param in root.findall("parameter"):
        name_el = param.find("name")
        if name_el is None or name_el.text is None:
            continue
        values = [v.text or "" for v in param.findall("value")]
        params.append((name_el.text, values))
    return params


def complexity_tier(params: list[tuple[str, list[str]]]) -> str:
    if any(name.startswith("finder-stage-") for name, _ in params):
        return "Complex"
    group_by = sum(
        1
        for name, values in params
        if name.startswith("B_") and values and values[0] != "*None*"
    )
    if len(params) > 60 or group_by >= 2:
        return "Medium"
    return "Simple"


# ── shared chrome ────────────────────────────────────────────────────────


def render_nav(depth: int) -> str:
    root = "../" * depth or "./"
    return f"""<nav>
  <a class="logo" href="{root}index.html">pul<em>se</em></a>
  <ul>
    <li><a href="{root}index.html#legend">Structure</a></li>
    <li><a href="{root}index.html#datasets">Datasets</a></li>
    <li><a href="{root}index.html#examples">Examples</a></li>
    <li><a href="https://github.com/fartbagxp/pulse-code" target="_blank">GitHub</a></li>
  </ul>
</nav>"""


def render_footer() -> str:
    return """<footer>
  <span>MIT license</span>
  <span>pulse — CDC WONDER query explorer</span>
</footer>"""


def page(title: str, depth: int, body: str) -> str:
    root = "../" * depth or "./"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
{render_nav(depth)}
<div class="page">
{body}
</div>
{render_footer()}
</body>
</html>
"""


# ── parameter rendering ──────────────────────────────────────────────────


def render_parameter(
    name: str,
    values: list[str],
    dataset_id: str,
    variable_labels: dict[str, dict[str, str]],
    catalog: dict[str, dict],
) -> str:
    cat = categorize(name)
    esc_name = html.escape(name)
    esc_values = (
        ", ".join(html.escape(v) if v else "&lt;empty&gt;" for v in values)
        or "&lt;empty&gt;"
    )
    explanation = explain_parameter(name, values, dataset_id, variable_labels, catalog)
    return f"""<div class="param param-{cat.key}">
      <span class="param-name">{esc_name}</span>
      <span class="param-value">{esc_values}</span>
      <div class="param-tip">
        <strong>{html.escape(cat.label)}</strong>
        <p>{html.escape(explanation)}</p>
      </div>
    </div>"""


# ── pages ────────────────────────────────────────────────────────────────


def render_example(
    query: dict,
    catalog: dict,
    siblings: list[dict],
    variable_labels: dict[str, dict[str, str]],
) -> str:
    filename = query["filename"]
    dataset_id = query["dataset_id"]
    params = parse_params(filename)
    lines = "\n    ".join(
        render_parameter(n, v, dataset_id, variable_labels, catalog) for n, v in params
    )
    dataset = catalog.get(dataset_id, {})
    tier = complexity_tier(params)
    topic_color = TOPIC_COLORS.get(dataset.get("topic", ""), "#85837e")

    other_links = "\n    ".join(
        f'<a href="{Path(s["filename"]).stem}.html">{html.escape(s["description"])}</a>'
        for s in siblings
        if s["filename"] != filename
    )
    sibling_block = (
        f"""
  <section class="chapter chapter--tight">
    <p class="ch-kicker">Other examples for {html.escape(query["dataset_id"])}</p>
    <div class="ch-links">
    {other_links}
    </div>
  </section>"""
        if other_links
        else ""
    )

    body = f"""
<section class="hero hero--example">
  <p class="hero-kicker" style="color:{topic_color}">
    {html.escape(dataset.get("topic", ""))} · {html.escape(query["dataset_id"])}
  </p>
  <h1>{html.escape(query["description"])}</h1>
  <p class="hero-p">{html.escape(dataset.get("subject", ""))}</p>
  <p class="hero-meta">
    <span class="badge badge--{tier.lower()}">{html.escape(tier)}</span>
    <span>{html.escape(dataset.get("title", ""))}</span>
    <span>&middot;</span>
    <span>{html.escape(dataset.get("year_range_label", ""))}</span>
  </p>
</section>

<section class="chapter">
  <p class="ch-kicker">Hover any row to see what it does</p>
  <div class="query code-pill">
    {lines}
  </div>
</section>
{sibling_block}
"""
    return page(f"{query['description']} — pulse", 1, body)


def render_index(catalog: dict, by_dataset: dict[str, list[dict]]) -> str:
    legend_items = "\n    ".join(
        f'<li><span class="swatch param-{c.key}"></span>'
        f"<strong>{html.escape(c.label)}</strong><span>{html.escape(c.description)}</span></li>"
        for c in CATEGORIES
    )

    dataset_rows = []
    for d in sorted(catalog.values(), key=lambda d: (d["topic"], d["id"])):
        queries = by_dataset.get(d["id"], [])
        color = TOPIC_COLORS.get(d["topic"], "#85837e")
        subject = d["subject"]
        if len(subject) > 110:
            subject = subject[:110] + "…"
        aar = "✓" if d.get("has_aar") else "—"
        if queries:
            link_target = f"examples/{Path(queries[0]['filename']).stem}.html"
            id_cell = f'<a href="{link_target}"><code>{html.escape(d["id"])}</code></a>'
            queries_cell = f'<a href="{link_target}">{len(queries)} →</a>'
        else:
            id_cell = f"<code>{html.escape(d['id'])}</code>"
            queries_cell = "—"
        dataset_rows.append(
            f"""<tr>
      <td>{id_cell}</td>
      <td><span class="topic-dot" style="background:{color}"></span>{html.escape(d["topic"])}</td>
      <td class="mono">{html.escape(d["year_range_label"])}</td>
      <td class="subject">{html.escape(subject)}</td>
      <td class="mono">{queries_cell}</td>
      <td class="mono">{aar}</td>
    </tr>"""
        )

    example_cards = []
    for ds_id in sorted(
        by_dataset, key=lambda k: (catalog.get(k, {}).get("topic", ""), k)
    ):
        dataset = catalog.get(ds_id, {})
        color = TOPIC_COLORS.get(dataset.get("topic", ""), "#85837e")
        for q in by_dataset[ds_id]:
            params = parse_params(q["filename"])
            tier = complexity_tier(params)
            example_cards.append(
                f"""<a class="example-card" href="examples/{Path(q["filename"]).stem}.html">
      <span class="card-tag" style="color:{color}">{html.escape(dataset.get("topic", ""))}</span>
      <h2 class="card-title">{html.escape(q["description"])}</h2>
      <p class="card-desc">{html.escape(dataset.get("title", ""))} &middot; {html.escape(q["year_range"])}</p>
      <span class="card-arrow">
        <span class="badge badge--{tier.lower()}">{html.escape(tier)}</span>
        Explore →
      </span>
    </a>"""
            )

    total_queries = sum(len(v) for v in by_dataset.values())

    body = f"""
<section class="hero">
  <p class="hero-kicker">CDC WONDER API Reference</p>
  <h1>What every parameter<br>actually does.</h1>
  <p class="hero-p">
    A CDC WONDER API request is a flat list of <code>&lt;parameter&gt;</code>
    elements with cryptic names like <code>B_1</code> or <code>F_D202.V20</code>.
    This is a reference for reviewing or building those requests — color-coded
    by category, with a plain-English explanation for every parameter in
    every bundled query from the
    <a href="https://github.com/fartbagxp/pulse-code" target="_blank">pulse</a> CLI.
  </p>
  <div class="code-pill hero-snippet"><span class="ck">B_1</span> = <span class="cs">D202.V20</span>   <span class="cm"># Group by Year</span>
<span class="ck">O_age</span> = <span class="cs">D202.V1</span>  <span class="cm"># Required radio button</span>
<span class="ck">M_1</span> = <span class="cs">D202.M1</span>  <span class="cm"># Measure: Cases</span></div>
</section>

<section class="chapter" id="legend">
  <p class="ch-kicker">Parameter Structure</p>
  <h2 class="ch-h">Eight kinds of parameter.</h2>
  <p class="ch-p">Every <code>&lt;parameter&gt;</code> in a WONDER request falls into one of these categories.</p>
  <ul class="legend">
    {legend_items}
  </ul>
</section>

<section class="chapter" id="datasets">
  <p class="ch-kicker">{len(catalog)} Datasets &middot; {total_queries} Bundled Queries</p>
  <h2 class="ch-h">Dataset overview.</h2>
  <p class="ch-p">Same summary as <code>uv run pulse datasets</code> — every dataset pulse knows about, and whether there's an annotated example to look at.</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Dataset</th><th>Topic</th><th>Years</th><th>Subject</th><th>Queries</th><th>AAR</th></tr>
      </thead>
      <tbody>
    {"".join(dataset_rows)}
      </tbody>
    </table>
  </div>
</section>

<div class="example-grid" id="examples">
  {"".join(example_cards)}
</div>
"""
    return page("pulse — CDC WONDER XML query structure", 0, body)


CSS = """\
*, :before, :after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #252423; --bg2: #1e1d1c;
  --t: #f6f4f2; --t2: #cccac9; --t3: #85837e; --t4: #5b5855;
  --rim: #f6f4f20f; --theme: 255, 75, 75;
}
html { scroll-behavior: smooth; overflow-x: hidden; }
body {
  background: var(--bg); color: var(--t);
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; }
code, .mono { font-family: ui-monospace, "Cascadia Code", monospace; }

nav {
  position: fixed; inset: 0 0 auto; z-index: 200;
  display: flex; align-items: center; justify-content: space-between;
  height: 3.75rem; padding: 0 2.5rem;
  background: #252423cc; backdrop-filter: blur(18px);
  border-bottom: 1px solid var(--rim);
}
.logo { font-size: .875rem; font-weight: 700; letter-spacing: -.02em; text-decoration: none; color: var(--t); }
.logo em { color: rgb(var(--theme)); font-style: normal; }
nav ul { list-style: none; display: flex; gap: 2rem; }
nav a { color: var(--t3); font-size: .8rem; text-decoration: none; transition: color .15s; }
nav a:hover { color: var(--t); }

footer {
  display: flex; justify-content: space-between;
  padding: 1.75rem 3.5rem; border-top: 1px solid var(--rim);
  color: var(--t4); font-size: .72rem;
}

.page { max-width: 1280px; margin: 0 auto; padding: 0 3.5rem; }

.hero { padding: 8.5rem 0 3rem; }
.hero-kicker {
  display: flex; align-items: center; gap: .5rem;
  font-size: .62rem; font-weight: 700; letter-spacing: .22em; text-transform: uppercase;
  color: rgb(var(--theme)); margin-bottom: 1.5rem;
}
.hero-kicker:before { content: ""; width: 18px; height: 1px; background: currentColor; }
.hero h1 {
  font-size: clamp(2.6rem, 5.5vw, 4.25rem); font-weight: 900;
  letter-spacing: -.045em; line-height: 1; margin-bottom: 1.25rem;
  max-width: 20ch;
}
.hero-p { color: var(--t3); font-size: 1rem; line-height: 1.7; max-width: 640px; margin-bottom: 1.75rem; }
.hero-meta { display: flex; align-items: center; gap: .6rem; color: var(--t3); font-size: .85rem; margin-top: 1rem; }
.hero--example { padding-bottom: 2rem; }

.code-pill {
  background: var(--bg2); border: 1px solid var(--rim); border-radius: 10px;
  padding: 1.1rem 1.3rem; font-family: ui-monospace, "Cascadia Code", monospace;
  font-size: .78rem; line-height: 1.8; white-space: pre-wrap;
}
.hero-snippet { color: var(--t2); max-width: 640px; }
.cs { color: #86efac; }
.cn { color: #fbbf24; }
.ck { color: rgb(var(--theme)); }
.cm { color: var(--t3); }

.chapter { padding: 3.5rem 0; border-top: 1px solid var(--rim); }
.chapter--tight { padding-top: 0; padding-bottom: 3rem; }
.ch-kicker { font-size: .6rem; font-weight: 700; letter-spacing: .22em; text-transform: uppercase; opacity: .5; margin-bottom: 1.1rem; }
.ch-h { font-size: clamp(1.7rem, 3vw, 2.3rem); font-weight: 900; letter-spacing: -.04em; line-height: 1.05; margin-bottom: 1.1rem; }
.ch-p { color: var(--t3); font-size: .92rem; line-height: 1.7; max-width: 720px; margin-bottom: 1.75rem; }
.ch-links { display: flex; flex-direction: column; gap: .6rem; }
.ch-links a { color: var(--t3); font-size: .85rem; text-decoration: none; display: inline-flex; align-items: center; gap: .5rem; transition: color .15s; }
.ch-links a:before { content: "→"; font-size: .75rem; }
.ch-links a:hover { color: var(--t); }

.legend { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1px; background: var(--rim); border: 1px solid var(--rim); border-radius: 10px; overflow: hidden; }
.legend li { background: var(--bg); padding: 1.1rem 1.3rem; display: flex; flex-direction: column; gap: .35rem; }
.legend li strong { font-size: .85rem; }
.legend li span { color: var(--t3); font-size: .78rem; line-height: 1.5; }
.swatch { width: .7rem; height: .7rem; border-radius: 2px; display: inline-block; margin-bottom: .2rem; }

.table-wrap { overflow-x: auto; border: 1px solid var(--rim); border-radius: 10px; }
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
thead th { text-align: left; padding: .8rem 1rem; color: var(--t4); font-size: .68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; border-bottom: 1px solid var(--rim); }
tbody td { padding: .7rem 1rem; border-bottom: 1px solid var(--rim); color: var(--t2); vertical-align: top; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: var(--bg2); }
tbody a { color: rgb(var(--theme)); text-decoration: none; }
tbody a:hover { text-decoration: underline; }
td.subject { color: var(--t3); max-width: 420px; }
.topic-dot { display: inline-block; width: .5rem; height: .5rem; border-radius: 50%; margin-right: .5rem; }

.badge { display: inline-block; border-radius: 999px; padding: .15rem .6rem; font-size: .65rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.badge--simple { background: #4ade8022; color: #4ade80; }
.badge--medium { background: #facc1522; color: #facc15; }
.badge--complex { background: #f8717122; color: #f87171; }

.example-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1px; background: var(--rim); border-top: 1px solid var(--rim);
}
.example-card { background: var(--bg); padding: 2.25rem; text-decoration: none; color: inherit; display: flex; flex-direction: column; gap: .85rem; transition: background .2s; }
.example-card:hover { background: var(--bg2); }
.card-tag { font-size: .58rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; }
.card-title { font-size: clamp(1.15rem, 2vw, 1.45rem); font-weight: 900; letter-spacing: -.03em; line-height: 1.15; }
.card-desc { color: var(--t3); font-size: .8rem; line-height: 1.5; }
.card-arrow { margin-top: auto; padding-top: .75rem; font-size: .78rem; color: var(--t4); display: flex; align-items: center; gap: .6rem; }
.example-card:hover .card-arrow { color: var(--t); }

.query { display: flex; flex-direction: column; gap: 2px; }
.param {
  position: relative; display: flex; gap: 1rem; padding: .35rem .6rem;
  border-radius: 4px; border-left: 3px solid transparent; cursor: default;
}
.param:hover { background: #ffffff08; }
.param-name { min-width: 220px; font-weight: 600; }
.param-value { color: var(--t2); word-break: break-all; }
.param-tip {
  position: absolute; left: 0; top: calc(100% + 6px); z-index: 50;
  min-width: 260px; max-width: 360px;
  background: var(--bg2); border: 1px solid var(--rim); border-radius: 8px;
  padding: .7rem .9rem; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  box-shadow: 0 12px 32px #00000066;
  opacity: 0; pointer-events: none; transform: translateY(4px);
  transition: opacity .15s, transform .15s;
}
.param:hover .param-tip { opacity: 1; transform: translateY(0); pointer-events: auto; }
.param-tip strong { font-size: .78rem; color: rgb(var(--theme)); }
.param-tip p { font-size: .78rem; color: var(--t3); line-height: 1.5; margin-top: .3rem; white-space: normal; }

@media (max-width: 700px) {
  nav { padding: 0 1.25rem; }
  nav ul { gap: 1.1rem; }
  .page { padding: 0 1.25rem; }
  .hero { padding: 7rem 0 2.5rem; }
  .chapter { padding: 2.5rem 0; }
  footer { padding: 1.5rem; flex-direction: column; gap: .4rem; }
  .param-name { min-width: 140px; }
}
"""


_CATEGORY_CSS = "\n".join(
    f".param-{c.key} {{ border-left-color: {c.color}; }}\n"
    f".param-{c.key} .param-name {{ color: {c.color}; }}\n"
    f".swatch.param-{c.key} {{ background: {c.color}; }}"
    for c in CATEGORIES
)


def main() -> None:
    catalog = load_catalog()
    queries = load_queries_index()
    by_dataset = queries_by_dataset(queries)
    variable_labels = load_variable_labels()

    examples_dir = _DIST_DIR / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    (_DIST_DIR / "style.css").write_text(CSS + "\n" + _CATEGORY_CSS)
    (_DIST_DIR / "index.html").write_text(render_index(catalog, by_dataset))
    print("wrote index.html")

    for ds_id, ds_queries in by_dataset.items():
        for q in ds_queries:
            out_name = f"{Path(q['filename']).stem}.html"
            (examples_dir / out_name).write_text(
                render_example(q, catalog, ds_queries, variable_labels)
            )
            print(f"wrote examples/{out_name}")


if __name__ == "__main__":
    main()
