"""pulse CLI — CDC WONDER query explorer, builder, and refiner."""

from __future__ import annotations

import csv
import io
import json
import sys
import time
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from pulse.catalog import Catalog
from pulse.matcher import match_datasets, match_queries
from pulse.wonder_client import WonderClient

app = typer.Typer(
    name="pulse",
    help="CDC WONDER public health data query CLI — explore, build, and refine.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
err = Console(stderr=True)

_QUERIES_DIR = Path(__file__).parent / "queries"
_catalog = None


def _get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = Catalog()
    return _catalog


def _print_missing_provider_package(error: ImportError) -> None:
    err.print(f"[red]Missing package for the configured LLM provider: {error}[/red]")
    err.print(
        "[dim]Anthropic needs `anthropic`; Azure OpenAI needs `openai` "
        "(both are pulse dependencies — try `uv sync`).[/dim]"
    )


def _print_missing_api_key() -> None:
    err.print("[red]No credentials found for the configured LLM provider.[/red]")
    err.print(
        "[dim]Set [bold]ANTHROPIC_API_KEY[/bold] (default provider), or "
        "[bold]LLM_PROVIDER=azure_openai[/bold] plus [bold]AZURE_OPENAI_API_KEY[/bold], "
        "[bold]AZURE_OPENAI_ENDPOINT[/bold], [bold]AZURE_OPENAI_DEPLOYMENT[/bold], "
        "[bold]AZURE_OPENAI_API_VERSION[/bold].[/dim]"
    )


def _reference_queries(
    prompt: str, catalog: Catalog, top_n: int = 2, min_score: float = 0.10
) -> list[tuple[str, str]]:
    """Find the closest bundled queries to a prompt and load their XML as few-shot context."""
    matches = match_queries(prompt, catalog, top_n=top_n)
    refs = []
    for m in matches:
        if m.score < min_score:
            continue
        path = _QUERIES_DIR / m.query.filename
        if path.exists():
            refs.append((m.query.description, path.read_text()))
    return refs


# ── datasets ──────────────────────────────────────────────────────────────────


@app.command("datasets")
def cmd_datasets(
    topic: Annotated[
        Optional[str], typer.Option("--topic", "-t", help="Filter by topic")
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
):
    """List all CDC WONDER datasets — what they cover and when."""
    catalog = _get_catalog()
    datasets = catalog.datasets()

    if topic:
        datasets = [d for d in datasets if topic.lower() in d.topic.lower()]

    if json_out:
        out = []
        for d in datasets:
            q_count = len(catalog.queries_for_dataset(d.id))
            out.append(
                {
                    "id": d.id,
                    "title": d.title,
                    "topic": d.topic,
                    "year_range": d.year_range_label,
                    "subject": d.subject,
                    "has_aar": d.has_aar,
                    "bundled_queries": q_count,
                }
            )
        print(json.dumps(out, indent=2))
        return

    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        expand=True,
    )
    table.add_column("Dataset", style="bold yellow", width=9, no_wrap=True)
    table.add_column("Topic", width=18)
    table.add_column("Years", width=13, no_wrap=True)
    table.add_column("Subject", ratio=1)
    table.add_column("Queries", justify="right", width=7)
    table.add_column("AAR", justify="center", width=5)

    topic_colors = {
        "Mortality": "red",
        "Infant Mortality": "orange3",
        "Fetal Deaths": "dark_orange",
        "Natality": "green",
        "Cancer": "bright_magenta",
        "Infectious Disease": "cyan",
        "STI / Sexual Health": "bright_cyan",
        "Tuberculosis": "yellow",
        "HIV/AIDS": "bright_red",
        "Vaccine Safety": "magenta",
        "Environment": "blue",
        "Population": "dim",
    }

    for d in datasets:
        q_count = len(catalog.queries_for_dataset(d.id))
        color = topic_colors.get(d.topic, "white")
        table.add_row(
            d.id,
            Text(d.topic, style=color),
            d.year_range_label,
            d.subject[:120] + ("…" if len(d.subject) > 120 else ""),
            str(q_count) if q_count else "—",
            "✓" if d.has_aar else "",
        )

    console.print()
    console.print(table)
    all_topics = catalog.topics()
    console.print(
        f"\n[dim]{len(datasets)} datasets across {len(all_topics)} topics  |  "
        f"[bold]pulse topics[/bold] to list topics  |  "
        f"[bold]pulse datasets --topic Cancer[/bold]  |  "
        f"[bold]pulse info <ID>[/bold]  |  "
        f'[bold]pulse search "<topic>"[/bold][/dim]'
    )
    if not topic:
        console.print(
            "[dim]Note: Immunization coverage data (NIS, VaxView, school vaccination) "
            "is not in WONDER — it is available through CDC Open Data. "
            "WONDER does include VAERS vaccine adverse events (D8).[/dim]"
        )


# ── info ──────────────────────────────────────────────────────────────────────


@app.command("info")
def cmd_info(
    dataset_id: Annotated[str, typer.Argument(help="Dataset ID (e.g. D176)")],
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
):
    """Show detailed information about a dataset — measures, groupings, bundled queries."""
    catalog = _get_catalog()
    ds = catalog.dataset(dataset_id)
    if not ds:
        err.print(f"[red]Dataset {dataset_id!r} not found.[/red]")
        err.print("Run [bold]pulse datasets[/bold] to see all available datasets.")
        raise typer.Exit(1)

    bundled = catalog.queries_for_dataset(ds.id)

    if json_out:
        print(
            json.dumps(
                {
                    "id": ds.id,
                    "title": ds.title,
                    "topic": ds.topic,
                    "subject": ds.subject,
                    "year_range": ds.year_range_label,
                    "has_aar": ds.has_aar,
                    "has_template": ds.has_template,
                    "notes": ds.notes,
                    "tags": ds.tags,
                    "measures": [
                        {"code": m.code, "label": m.label} for m in ds.measures
                    ],
                    "key_groupings": ds.key_groupings,
                    "bundled_queries": [
                        {
                            "filename": q.filename,
                            "description": q.description,
                            "groupings": q.groupings,
                            "year_range": q.year_range,
                        }
                        for q in bundled
                    ],
                },
                indent=2,
            )
        )
        return

    console.print()
    console.print(
        Panel(
            f"[bold cyan]{ds.id}[/bold cyan]  [bold]{ds.title}[/bold]\n"
            f"[dim]{ds.topic}  ·  {ds.year_range_label}[/dim]",
            border_style="cyan",
            expand=False,
        )
    )

    console.print("\n[bold]Subject[/bold]")
    console.print(f"  {ds.subject}\n")

    if ds.notes:
        console.print(f"[dim italic]Note: {ds.notes}[/dim italic]\n")

    console.print("[bold]Measures[/bold]")
    for m in ds.measures:
        console.print(f"  [cyan]{m.code}[/cyan]  {m.label}")

    console.print(f"\n[bold]Key Grouping Dimensions ({len(ds.key_groupings)})[/bold]")
    for g in ds.key_groupings:
        console.print(f"  · {g}")

    if ds.has_aar:
        console.print("\n  [green]✓ Age-adjusted rates (AAR) available[/green]")
    else:
        console.print("\n  [dim]✗ No age-adjusted rates[/dim]")

    if bundled:
        console.print(f"\n[bold]Bundled Example Queries ({len(bundled)})[/bold]")
        qt = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        qt.add_column("File", style="dim")
        qt.add_column("Description")
        qt.add_column("Groups By")
        qt.add_column("Years")
        for q in bundled:
            qt.add_row(
                q.filename,
                q.description,
                ", ".join(q.groupings),
                q.year_range,
            )
        console.print(qt)
        console.print(
            f"[dim]Run a bundled query: [bold]pulse run {bundled[0].filename}[/bold][/dim]"
        )
    else:
        console.print("\n[dim]No bundled example queries for this dataset.[/dim]")
        if ds.has_template:
            console.print(
                '[dim]Template available — use [bold]pulse build "<prompt>"[/bold] to generate a query.[/dim]'
            )

    console.print()


# ── search ────────────────────────────────────────────────────────────────────


@app.command("search")
def cmd_search(
    prompt: Annotated[str, typer.Argument(help="Natural language query topic")],
    top: Annotated[int, typer.Option("--top", "-n", help="Number of results")] = 5,
    queries_only: Annotated[
        bool, typer.Option("--queries", "-q", help="Show only bundled queries")
    ] = False,
    datasets_only: Annotated[
        bool, typer.Option("--datasets", "-d", help="Show only datasets")
    ] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
):
    """Find the best matching datasets and bundled queries for a topic."""
    catalog = _get_catalog()

    ds_matches = match_datasets(prompt, catalog, top_n=top) if not queries_only else []
    q_matches = match_queries(prompt, catalog, top_n=top) if not datasets_only else []

    if json_out:
        print(
            json.dumps(
                {
                    "prompt": prompt,
                    "dataset_matches": [
                        {
                            "id": m.dataset.id,
                            "title": m.dataset.title,
                            "score": round(m.score, 3),
                            "reason": m.reason,
                        }
                        for m in ds_matches
                    ],
                    "query_matches": [
                        {
                            "filename": m.query.filename,
                            "dataset_id": m.query.dataset_id,
                            "description": m.query.description,
                            "score": round(m.score, 3),
                        }
                        for m in q_matches
                    ],
                },
                indent=2,
            )
        )
        return

    console.print()
    console.print(f"[bold]Search:[/bold] {prompt!r}\n")

    if ds_matches and not queries_only:
        console.print("[bold cyan]Best Matching Datasets[/bold cyan]")
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        t.add_column("Score", justify="right", width=7)
        t.add_column("Dataset", width=9)
        t.add_column("Topic", width=16)
        t.add_column("Years", width=13)
        t.add_column("Title / Reason")
        for m in ds_matches:
            pct = int(m.score * 100)
            color = "green" if pct >= 30 else "yellow" if pct >= 15 else "dim"
            t.add_row(
                Text(f"{pct}%", style=color),
                m.dataset.id,
                m.dataset.topic,
                m.dataset.year_range_label,
                f"{m.dataset.title}\n[dim]{m.reason}[/dim]",
            )
        console.print(t)

    if q_matches and not datasets_only:
        console.print("[bold cyan]Best Matching Bundled Queries[/bold cyan]")
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        t.add_column("Score", justify="right", width=7)
        t.add_column("Dataset", width=8)
        t.add_column("File", width=42)
        t.add_column("Description")
        for m in q_matches:
            pct = int(m.score * 100)
            color = "green" if pct >= 30 else "yellow" if pct >= 15 else "dim"
            t.add_row(
                Text(f"{pct}%", style=color),
                m.query.dataset_id,
                m.query.filename,
                m.query.description,
            )
        console.print(t)

    console.print(
        f"\n[dim]Run a query: [bold]pulse run <filename>[/bold]  ·  "
        f'Build new: [bold]pulse build "{prompt}"[/bold][/dim]\n'
    )


# ── build ─────────────────────────────────────────────────────────────────────


@app.command("build")
def cmd_build(
    prompt: Annotated[str, typer.Argument(help="Natural language query description")],
    output: Annotated[
        Optional[Path], typer.Option("-o", "--output", help="Save XML to file")
    ] = None,
    suggest: Annotated[
        bool,
        typer.Option(
            "--suggest/--no-suggest", help="Show closest existing queries first"
        ),
    ] = True,
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
):
    """Build a CDC WONDER XML query from natural language using Claude."""
    catalog = _get_catalog()

    if suggest:
        q_matches = match_queries(prompt, catalog, top_n=3)
        if q_matches and q_matches[0].score > 0.10:
            console.print(
                "\n[dim]Closest existing queries — run these directly with [bold]pulse run <file>[/bold]:[/dim]"
            )
            for m in q_matches[:3]:
                pct = int(m.score * 100)
                console.print(
                    f"  [yellow]{pct}%[/yellow]  {m.query.filename}  [dim]{m.query.description}[/dim]"
                )
            console.print()

    console.print(f"[bold]Building query:[/bold] {prompt!r}")
    console.print("[dim]Calling the LLM…[/dim]\n")

    def _on_thinking(text: str) -> None:
        if verbose and text.strip():
            console.print(f"[dim italic]{text[:200]}…[/dim italic]")

    refs = _reference_queries(prompt, catalog)
    try:
        from pulse.llm_builder import get_query_builder

        builder = get_query_builder()
        request = builder.build(
            prompt, reference_queries=refs, on_thinking=_on_thinking
        )
    except ImportError as e:
        _print_missing_provider_package(e)
        raise typer.Exit(1)
    except (RuntimeError, ValueError) as e:
        err.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except TypeError as e:
        if "api_key" in str(e) or "authentication" in str(e).lower():
            _print_missing_api_key()
            raise typer.Exit(1)
        raise
    xml = request.to_xml()

    if output:
        output.write_text(xml)
        console.print(f"[green]✓[/green] Saved to [bold]{output}[/bold]")
        console.print(f"[dim]Run it: [bold]pulse run {output}[/bold][/dim]\n")
    else:
        print(xml)


# ── run ───────────────────────────────────────────────────────────────────────


@app.command("run")
def cmd_run(
    query_file: Annotated[
        str, typer.Argument(help="Path to XML query file, or bundled query filename")
    ],
    format: Annotated[
        str, typer.Option("-f", "--format", help="Output format: table|csv|json|xml")
    ] = "table",
    timeout: Annotated[
        int, typer.Option("-t", "--timeout", help="Request timeout in seconds")
    ] = 120,
    no_totals: Annotated[
        bool, typer.Option("--no-totals", help="Exclude total rows")
    ] = False,
    output: Annotated[
        Optional[Path], typer.Option("-o", "--output", help="Save output to file")
    ] = None,
):
    """Execute a CDC WONDER XML query and display results."""
    path = Path(query_file)
    if not path.exists():
        bundled = _QUERIES_DIR / query_file
        if bundled.exists():
            path = bundled
        else:
            err.print(f"[red]File not found: {query_file}[/red]")
            err.print(f"[dim]Bundled queries are in {_QUERIES_DIR}[/dim]")
            raise typer.Exit(1)

    err.print(f"[bold]Executing:[/bold] {path.name}")
    err.print("[dim]Querying CDC WONDER API…[/dim]\n")

    client = WonderClient(timeout=timeout)
    try:
        response_xml = client.execute_file(path)
    except RuntimeError as e:
        err.print(f"[red]Error from CDC WONDER:[/red] {e}")
        raise typer.Exit(1)

    _output_response(client, response_xml, format, output, no_totals)


# ── query ─────────────────────────────────────────────────────────────────────


@app.command("query")
def cmd_query(
    prompt: Annotated[str, typer.Argument(help="Natural language query")],
    format: Annotated[
        str, typer.Option("-f", "--format", help="Output: table|csv|json|xml")
    ] = "table",
    save_xml: Annotated[
        Optional[Path], typer.Option("--save-xml", help="Save generated XML")
    ] = None,
    timeout: Annotated[int, typer.Option("-t", "--timeout")] = 120,
    no_totals: Annotated[bool, typer.Option("--no-totals")] = False,
):
    """Build a query from natural language and execute it immediately."""
    console.print(f"[bold]Building query:[/bold] {prompt!r}", file=sys.stderr)

    catalog = _get_catalog()
    refs = _reference_queries(prompt, catalog)
    try:
        from pulse.llm_builder import get_query_builder

        builder = get_query_builder()
        request = builder.build(prompt, reference_queries=refs)
    except ImportError as e:
        _print_missing_provider_package(e)
        raise typer.Exit(1)
    except (RuntimeError, ValueError) as e:
        err.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except TypeError as e:
        if "api_key" in str(e) or "authentication" in str(e).lower():
            _print_missing_api_key()
            raise typer.Exit(1)
        raise
    xml = request.to_xml()

    if save_xml:
        save_xml.write_text(xml)
        console.print(f"[green]✓[/green] Saved XML to {save_xml}", file=sys.stderr)

    console.print(
        f"[dim]Executing against {request.dataset_id}…[/dim]\n", file=sys.stderr
    )

    client = WonderClient(timeout=timeout)
    try:
        response_xml = client.query_from_xml(request.dataset_id, xml)
    except RuntimeError as e:
        err.print(f"[red]Error from CDC WONDER:[/red] {e}")
        raise typer.Exit(1)

    _output_response(client, response_xml, format, None, no_totals)


# ── compare ───────────────────────────────────────────────────────────────────

_WONDER_RATE_LIMIT_SECONDS = 15


@app.command("compare")
def cmd_compare(
    prompt: Annotated[
        str,
        typer.Argument(
            help="Natural language comparison, e.g. 'opioid deaths vs suicide deaths by state'"
        ),
    ],
    format: Annotated[
        str, typer.Option("-f", "--format", help="Output: table|csv|json|xml")
    ] = "table",
    save_xml_dir: Annotated[
        Optional[Path],
        typer.Option("--save-xml-dir", help="Directory to save each sub-query's XML"),
    ] = None,
    timeout: Annotated[int, typer.Option("-t", "--timeout")] = 120,
    no_totals: Annotated[bool, typer.Option("--no-totals")] = False,
):
    """Build and run a comparison across two or more causes/datasets from natural language."""
    catalog = _get_catalog()

    console.print(f"[bold]Building comparison:[/bold] {prompt!r}\n")

    refs = _reference_queries(prompt, catalog)
    try:
        from pulse.llm_builder import get_query_builder, WonderRequestSet

        builder = get_query_builder()
        result = builder.build_any(prompt, reference_queries=refs)
    except ImportError as e:
        _print_missing_provider_package(e)
        raise typer.Exit(1)
    except (RuntimeError, ValueError) as e:
        err.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except TypeError as e:
        if "api_key" in str(e) or "authentication" in str(e).lower():
            _print_missing_api_key()
            raise typer.Exit(1)
        raise

    if not isinstance(result, WonderRequestSet):
        console.print(
            "[yellow]This didn't look like a comparison — running it as a single query.[/yellow]\n"
        )
        requests, labels = [result], [result.dataset_id]
    else:
        requests, labels = result.requests, result.labels

    client = WonderClient(timeout=timeout)
    if save_xml_dir:
        save_xml_dir.mkdir(parents=True, exist_ok=True)

    for i, (request, label) in enumerate(zip(requests, labels)):
        xml = request.to_xml()

        if save_xml_dir:
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
            xml_path = save_xml_dir / f"{safe_name}.xml"
            xml_path.write_text(xml)
            console.print(f"[green]✓[/green] Saved {xml_path}")

        console.print(f"\n[bold cyan]── {label} ──[/bold cyan]")
        console.print(f"[dim]Executing against {request.dataset_id}…[/dim]\n")

        try:
            response_xml = client.query_from_xml(request.dataset_id, xml)
        except RuntimeError as e:
            err.print(f"[red]Error from CDC WONDER:[/red] {e}")
            raise typer.Exit(1)

        _output_response(client, response_xml, format, None, no_totals)

        if i < len(requests) - 1:
            console.print(
                f"\n[dim]Waiting {_WONDER_RATE_LIMIT_SECONDS}s (CDC WONDER rate limit)…[/dim]"
            )
            time.sleep(_WONDER_RATE_LIMIT_SECONDS)


# ── refine ────────────────────────────────────────────────────────────────────


@app.command("refine")
def cmd_refine(
    query_file: Annotated[str, typer.Argument(help="Existing XML query to refine")],
    feedback: Annotated[
        str, typer.Argument(help="What to change (e.g. 'break down by state')")
    ],
    output: Annotated[
        Optional[Path], typer.Option("-o", "--output", help="Save refined XML")
    ] = None,
    execute: Annotated[
        bool, typer.Option("--run", help="Also execute the refined query")
    ] = False,
    format: Annotated[str, typer.Option("-f", "--format")] = "table",
):
    """Refine an existing query using natural language feedback."""
    path = Path(query_file)
    if not path.exists():
        bundled = _QUERIES_DIR / query_file
        if bundled.exists():
            path = bundled
        else:
            err.print(f"[red]File not found: {query_file}[/red]")
            raise typer.Exit(1)

    base_xml = path.read_text()

    console.print(f"[bold]Refining:[/bold] {path.name}")
    console.print(f"[bold]Feedback:[/bold] {feedback!r}\n")

    try:
        from pulse.llm_builder import get_query_builder

        builder = get_query_builder()
        request = builder.build(feedback, base_xml=base_xml)
    except ImportError as e:
        _print_missing_provider_package(e)
        raise typer.Exit(1)
    except (RuntimeError, ValueError) as e:
        err.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except TypeError as e:
        if "api_key" in str(e) or "authentication" in str(e).lower():
            _print_missing_api_key()
            raise typer.Exit(1)
        raise
    xml = request.to_xml()

    if output:
        output.write_text(xml)
        console.print(f"[green]✓[/green] Saved refined query to [bold]{output}[/bold]")
    else:
        print(xml)

    if execute:
        console.print(
            f"\n[dim]Executing refined query against {request.dataset_id}…[/dim]\n"
        )
        client = WonderClient()
        try:
            response_xml = client.query_from_xml(request.dataset_id, xml)
        except RuntimeError as e:
            err.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        _output_response(client, response_xml, format, None, False)


# ── chat ──────────────────────────────────────────────────────────────────────


@app.command("chat")
def cmd_chat(
    initial_prompt: Annotated[
        Optional[str], typer.Argument(help="Optional first request to start with")
    ] = None,
):
    """Interactively build and refine a CDC WONDER query over multiple turns."""
    catalog = _get_catalog()

    try:
        from pulse.llm_builder import get_query_builder

        builder = get_query_builder()
    except ImportError as e:
        _print_missing_provider_package(e)
        raise typer.Exit(1)
    except (RuntimeError, ValueError) as e:
        err.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    current_xml: Optional[str] = None
    current_dataset_id: Optional[str] = None

    console.print(
        "\n[bold]pulse chat[/bold] — describe a query, then refine it turn by turn."
    )
    console.print("[dim]Commands: :xml  :run  :save <path>  :reset  :exit[/dim]\n")

    def _build_turn(text: str) -> None:
        nonlocal current_xml, current_dataset_id
        try:
            if current_xml is None:
                refs = _reference_queries(text, catalog)
                request = builder.build(text, reference_queries=refs)
            else:
                request = builder.build(text, base_xml=current_xml)
        except TypeError as e:
            if "api_key" in str(e) or "authentication" in str(e).lower():
                _print_missing_api_key()
                return
            raise
        current_xml = request.to_xml()
        current_dataset_id = request.dataset_id
        console.print(f"\n[dim]Dataset:[/dim] {current_dataset_id}")
        console.print(current_xml)
        console.print()

    if initial_prompt:
        console.print(f"[bold]>[/bold] {initial_prompt}")
        _build_turn(initial_prompt)

    while True:
        try:
            text = Prompt.ask("[bold cyan]pulse>[/bold cyan]").strip()
        except EOFError, KeyboardInterrupt:
            console.print()
            break

        if not text:
            continue

        if text in (":exit", ":quit"):
            break

        if text == ":xml":
            if current_xml:
                console.print(current_xml)
            else:
                console.print("[yellow]No query built yet.[/yellow]")
            continue

        if text == ":reset":
            current_xml = None
            current_dataset_id = None
            console.print("[dim]Reset.[/dim]")
            continue

        if text.startswith(":save"):
            parts = text.split(maxsplit=1)
            if not current_xml:
                console.print("[yellow]No query built yet.[/yellow]")
            elif len(parts) < 2:
                console.print("[yellow]Usage: :save <path>[/yellow]")
            else:
                out_path = Path(parts[1])
                out_path.write_text(current_xml)
                console.print(f"[green]✓[/green] Saved to {out_path}")
            continue

        if text == ":run":
            if not current_xml or not current_dataset_id:
                console.print("[yellow]No query built yet.[/yellow]")
                continue
            client = WonderClient()
            try:
                response_xml = client.query_from_xml(current_dataset_id, current_xml)
            except RuntimeError as e:
                err.print(f"[red]Error from CDC WONDER:[/red] {e}")
                continue
            _output_response(client, response_xml, "table", None, False)
            continue

        _build_turn(text)

    console.print("[dim]Bye.[/dim]")


# ── topics ────────────────────────────────────────────────────────────────────


@app.command("topics")
def cmd_topics():
    """List all dataset topics and dataset counts."""
    catalog = _get_catalog()
    from collections import Counter

    counts = Counter(d.topic for d in catalog.datasets())

    topic_colors = {
        "Mortality": "red",
        "Infant Mortality": "orange3",
        "Fetal Deaths": "dark_orange",
        "Natality": "green",
        "Cancer": "bright_magenta",
        "Infectious Disease": "cyan",
        "STI / Sexual Health": "bright_cyan",
        "Tuberculosis": "yellow",
        "HIV/AIDS": "bright_red",
        "Vaccine Safety": "magenta",
        "Environment": "blue",
        "Population": "dim",
    }

    t = Table(
        box=box.ROUNDED, show_header=True, header_style="bold cyan", border_style="dim"
    )
    t.add_column("Topic", ratio=1)
    t.add_column("Datasets", justify="right", width=9)
    t.add_column("Filter command", style="dim")

    for topic, count in sorted(counts.items(), key=lambda x: -x[1]):
        color = topic_colors.get(topic, "white")
        t.add_row(
            Text(topic, style=color),
            str(count),
            f'pulse datasets --topic "{topic}"',
        )

    console.print()
    console.print(t)
    console.print(f"\n[dim]{sum(counts.values())} total datasets[/dim]\n")


# ── list-queries ──────────────────────────────────────────────────────────────


@app.command("list-queries")
def cmd_list_queries(
    dataset_id: Annotated[Optional[str], typer.Option("--dataset", "-d")] = None,
    json_out: Annotated[bool, typer.Option("--json")] = False,
):
    """List all bundled example queries."""
    catalog = _get_catalog()
    queries = catalog.queries()

    if dataset_id:
        queries = [q for q in queries if q.dataset_id.upper() == dataset_id.upper()]

    if json_out:
        print(
            json.dumps(
                [
                    {
                        "filename": q.filename,
                        "dataset_id": q.dataset_id,
                        "description": q.description,
                        "groupings": q.groupings,
                        "year_range": q.year_range,
                    }
                    for q in queries
                ],
                indent=2,
            )
        )
        return

    t = Table(
        box=box.ROUNDED, show_header=True, header_style="bold cyan", border_style="dim"
    )
    t.add_column("Dataset", width=9, style="yellow")
    t.add_column("File")
    t.add_column("Description")
    t.add_column("Groups By")
    t.add_column("Years", width=12)

    for q in queries:
        t.add_row(
            q.dataset_id,
            q.filename,
            q.description,
            ", ".join(q.groupings),
            q.year_range,
        )

    console.print()
    console.print(t)
    console.print(
        f"\n[dim]{len(queries)} bundled queries  ·  Run: [bold]pulse run <filename>[/bold][/dim]\n"
    )


# ── helpers ───────────────────────────────────────────────────────────────────


def _output_response(
    client: WonderClient,
    response_xml: str,
    format: str,
    output: Optional[Path],
    no_totals: bool,
) -> None:
    if format == "xml":
        text = response_xml
        if output:
            output.write_text(text)
        else:
            print(text)
        return

    if format == "json":
        records = client.to_records(response_xml)
        text = json.dumps(records, indent=2)
        if output:
            output.write_text(text)
        else:
            print(text)
        return

    headers, data = client.to_arrays(response_xml)
    rows = client.parse_rows(response_xml)

    if no_totals:
        data = [row for row, r in zip(data, rows) if not r.is_total]

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerows(data)
        text = buf.getvalue()
        if output:
            output.write_text(text)
        else:
            print(text, end="")
        return

    if format == "table":
        if not data:
            console.print("[yellow]No data returned.[/yellow]")
            return
        t = Table(
            box=box.ROUNDED, show_header=True, header_style="bold", border_style="dim"
        )
        for h in headers:
            t.add_column(h)
        for i, (row, row_obj) in enumerate(zip(data, rows)):
            style = "bold" if row_obj.is_total and not no_totals else None
            t.add_row(*[str(v) if v is not None else "—" for v in row], style=style)
        console.print(t)
        console.print(f"[dim]{len(data)} rows[/dim]")
        if output:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(headers)
            writer.writerows(data)
            output.write_text(buf.getvalue())
            console.print(f"[green]✓[/green] Saved to {output}")
        return

    err.print(f"[red]Unknown format: {format!r}. Use: table|csv|json|xml[/red]")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
