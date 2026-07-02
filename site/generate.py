#!/usr/bin/env python3
"""Generate the static site explaining CDC WONDER XML query structure.

Pure stdlib — no runtime dependency on the pulse package or anthropic.
Reads real bundled queries + the dataset catalog so the site can't drift
from what the CLI actually produces.
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
_STATIC_DIR = _SITE_DIR / "static"
_DIST_DIR = _SITE_DIR / "dist"


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
        "#2563eb",
        "Which dimensions appear as rows (B_1 through B_5). Unused slots are *None*.",
    ),
    Category(
        "F",
        "Finder Filter",
        "#d97706",
        "Filter select for a hierarchical codelist (e.g. ICD chapters). Paired with an I_* and finder-stage-*.",
    ),
    Category(
        "I",
        "Finder Text Input",
        "#a16207",
        "Empty text-input companion to an F_* finder filter.",
    ),
    Category(
        "finder-stage",
        "Finder Stage",
        "#c2410c",
        "Declares that a variable uses codeset (hierarchical) filter mode.",
    ),
    Category(
        "M",
        "Measure",
        "#7c3aed",
        "What's counted: deaths, births, cases, population, crude rate, age-adjusted rate.",
    ),
    Category(
        "O",
        "Option / Mode Selector",
        "#dc2626",
        "Output options and radio-button mode selectors (e.g. O_age picks which age variable is active). Omitting a required one causes HTTP 500.",
    ),
    Category(
        "V",
        "Value Filter",
        "#16a34a",
        "Dropdown filter for a specific value (e.g. year, state, sex). *All* means no restriction.",
    ),
    Category(
        "boilerplate",
        "Boilerplate",
        "#6b7280",
        "Required metadata: dataset_code, dataset_label, stage, action-Send.",
    ),
]

_CATEGORY_BY_KEY = {c.key: c for c in CATEGORIES}


def categorize(name: str) -> Category:
    for cat in CATEGORIES:
        if cat.matches(name):
            return cat
    return _CATEGORY_BY_KEY["boilerplate"]


# (filename, complexity label) — simple/medium/complex tiers, chosen to show
# a finder-stage/F_*/I_* heavy query (complex) vs a flat one (simple).
EXAMPLE_FILES = [
    ("tb-cases-by-year-1993-2023-req.xml", "Simple"),
    ("drug-deaths-by-year-2018-2024-req.xml", "Medium"),
    ("fetal-deaths-by-cause-by-year-2014-2024-req.xml", "Complex"),
]


def load_catalog() -> dict[str, dict]:
    raw = json.loads(_CATALOG_PATH.read_text())
    return {d["id"]: d for d in raw["datasets"]}


def load_queries_index() -> dict[str, dict]:
    raw = json.loads(_QUERIES_INDEX_PATH.read_text())
    return {q["filename"]: q for q in raw["queries"]}


def render_parameter(name: str, values: list[str]) -> str:
    cat = categorize(name)
    esc_name = html.escape(name)
    esc_values = (
        ", ".join(html.escape(v) if v else "<empty>" for v in values) or "<empty>"
    )
    return (
        f'<div class="param param-{cat.key}" title="{html.escape(cat.label)}: {html.escape(cat.description)}">'
        f'<span class="param-name">{esc_name}</span>'
        f'<span class="param-value">{esc_values}</span>'
        f"</div>"
    )


def render_example(
    filename: str, complexity: str, catalog: dict, queries_index: dict
) -> str:
    xml_text = (_QUERIES_DIR / filename).read_text()
    root = ET.fromstring(xml_text)

    lines = []
    for param in root.findall("parameter"):
        name_el = param.find("name")
        if name_el is None or name_el.text is None:
            continue
        values = [v.text or "" for v in param.findall("value")]
        lines.append(render_parameter(name_el.text, values))

    meta = queries_index.get(filename, {})
    dataset = catalog.get(meta.get("dataset_id", ""), {})

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(meta.get("description", filename))} — pulse WONDER query explainer</title>
<link rel="stylesheet" href="../style.css">
</head>
<body>
<header>
  <a href="../index.html">&larr; back to overview</a>
  <h1>{html.escape(meta.get("description", filename))}</h1>
  <p class="subtitle">
    <span class="badge">{html.escape(complexity)}</span>
    Dataset <code>{html.escape(dataset.get("id", meta.get("dataset_id", "?")))}</code>
    &mdash; {html.escape(dataset.get("title", ""))}
    ({html.escape(dataset.get("year_range_label", ""))})
  </p>
  <p>{html.escape(dataset.get("subject", ""))}</p>
</header>
<main>
  <div class="query">
    {"".join(lines)}
  </div>
</main>
</body>
</html>
"""


def render_index(catalog: dict, queries_index: dict) -> str:
    legend_items = "".join(
        f'<li><span class="swatch param-{c.key}"></span>'
        f"<strong>{html.escape(c.label)}</strong> — {html.escape(c.description)}</li>"
        for c in CATEGORIES
    )
    example_links = "".join(
        f'<li><a href="examples/{Path(filename).stem}.html">'
        f"{html.escape(queries_index.get(filename, {}).get('description', filename))}</a> "
        f'<span class="badge">{html.escape(complexity)}</span></li>'
        for filename, complexity in EXAMPLE_FILES
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>pulse — CDC WONDER XML query structure</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
  <h1>CDC WONDER XML Query Structure</h1>
  <p>
    A CDC WONDER API request is a flat list of <code>&lt;parameter&gt;</code> elements.
    Each name's prefix tells you what it does. This page color-codes those
    prefixes across real, working queries from the
    <a href="https://github.com/fartbagxp/pulse-code">pulse</a> CLI.
  </p>
</header>
<main>
  <section>
    <h2>Legend</h2>
    <ul class="legend">{legend_items}</ul>
  </section>
  <section>
    <h2>Annotated Examples</h2>
    <ul class="examples">{example_links}</ul>
  </section>
</main>
</body>
</html>
"""


CSS = """\
:root { color-scheme: light; }
body { font-family: -apple-system, system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1f2937; }
header h1 { margin-bottom: 0.25rem; }
header a { color: #2563eb; text-decoration: none; }
code { background: #f3f4f6; padding: 0.1rem 0.35rem; border-radius: 4px; }
.badge { display: inline-block; background: #e5e7eb; border-radius: 999px; padding: 0.1rem 0.6rem; font-size: 0.8rem; margin-left: 0.4rem; }
ul.legend, ul.examples { list-style: none; padding: 0; }
ul.legend li, ul.examples li { padding: 0.35rem 0; border-bottom: 1px solid #f0f0f0; }
.swatch { display: inline-block; width: 0.85rem; height: 0.85rem; border-radius: 3px; margin-right: 0.5rem; vertical-align: middle; }
.query { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.9rem; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
.param { display: flex; gap: 1rem; padding: 0.3rem 0.7rem; border-bottom: 1px solid #f3f4f6; }
.param:last-child { border-bottom: none; }
.param-name { min-width: 220px; font-weight: 600; }
.param-value { color: #374151; word-break: break-all; }
"""

_CATEGORY_CSS = "\n".join(
    f".param-{c.key} {{ border-left: 4px solid {c.color}; background: {c.color}10; }}\n"
    f".swatch.param-{c.key} {{ background: {c.color}; }}"
    for c in CATEGORIES
)


def main() -> None:
    catalog = load_catalog()
    queries_index = load_queries_index()

    examples_dir = _DIST_DIR / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    (_DIST_DIR / "style.css").write_text(CSS + "\n" + _CATEGORY_CSS)
    (_DIST_DIR / "index.html").write_text(render_index(catalog, queries_index))

    for filename, complexity in EXAMPLE_FILES:
        out_name = f"{Path(filename).stem}.html"
        (examples_dir / out_name).write_text(
            render_example(filename, complexity, catalog, queries_index)
        )
        print(f"wrote examples/{out_name}")

    print("wrote index.html")


if __name__ == "__main__":
    main()
