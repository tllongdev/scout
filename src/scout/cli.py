"""Command-line entrypoint for Scout."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from .config import Config, ConfigError
from .discovery import ProviderModels, discover_all
from .orchestrator import Orchestrator

_BANNER = r"""
   ___  _________  __  _________
  / __/ / ___/ _ \/ / / /_  __/
 _\ \  / /__/ // / /_/ / / /
/___/  \___/\____/\____/ /_/   intelligence collector
"""

_HELP = """Usage:
  scout "<mission brief>"     Run a collection mission
  scout models               List the models available to your credentials
  scout tools                List OSINT tools and whether each is available
  scout discover [query]     Find top OSINT tool repos on GitHub (new candidates)
  scout help                 Show this help

Try it with no API key:
  SCOUT_MODEL=mock scout "<mission brief>"   Run the full pipeline with a
                                             scripted demo model (no key, no
                                             cost; findings are illustrative)
"""


def main() -> int:
    console = Console()
    console.print(f"[bold cyan]{_BANNER}[/bold cyan]")

    args = sys.argv[1:]
    command = args[0].lower() if args else ""

    if command in {"help", "-h", "--help"}:
        console.print(_HELP)
        return 0
    if command == "models":
        return _cmd_models(console)
    if command == "tools":
        return _cmd_tools(console)
    if command == "discover":
        return _cmd_discover(console, args[1:])

    return _cmd_run(console, args)


# ── `scout discover` ───────────────────────────────────────────────────────


def _cmd_discover(console: Console, args: list[str]) -> int:
    from .tools.github_discovery import discover_github_osint

    query = " ".join(args).strip() or None
    with console.status("Searching GitHub for top OSINT tools..."):
        repos, error = discover_github_osint(query=query)

    if not repos:
        console.print(f"[yellow]No results.[/yellow] {error or ''}".strip())
        return 1

    table = Table(
        title="[bold]Top OSINT repos on GitHub[/bold]"
        + (f" [dim](query: {query})[/dim]" if query else ""),
        title_justify="left",
        border_style="cyan",
    )
    table.add_column("", justify="center")
    table.add_column("Repo")
    table.add_column("Stars", justify="right")
    table.add_column("Updated", style="dim")
    table.add_column("Description")

    for r in repos:
        mark = "[green]✓[/green]" if r.integrated else ""
        stars = f"{r.stars / 1000:.1f}k" if r.stars >= 1000 else str(r.stars)
        desc = (r.description[:70] + "…") if len(r.description) > 70 else r.description
        table.add_row(mark, r.full_name, stars, r.pushed_at, desc)

    console.print(table)
    console.print(
        "\n[dim][green]✓[/green] already integrated in Scout. Others are "
        "candidates - wrap one by adding a ToolSpec under "
        "src/scout/tools/osint/.[/dim]"
    )
    if error:
        console.print(f"[dim]Note: {error}[/dim]")
    return 0


# ── `scout tools` ──────────────────────────────────────────────────────────


def _cmd_tools(console: Console) -> int:
    from .tools.registry import discover_tools

    discovered = discover_tools()
    table = Table(
        title="[bold]OSINT tool library[/bold]",
        title_justify="left",
        border_style="cyan",
        show_lines=False,
    )
    table.add_column("", justify="center")
    table.add_column("Tool")
    table.add_column("Category", style="dim")
    table.add_column("What it's for")
    table.add_column("Status", style="dim")

    for d in sorted(discovered, key=lambda x: (not x.available, x.spec.category)):
        if d.enabled:
            mark, status = "[green]●[/green]", "[green]ready[/green]"
        elif d.available:
            mark, status = "[yellow]○[/yellow]", "available (disabled)"
        else:
            mark, status = "[dim]·[/dim]", d.reason
        name = d.spec.name + (" [red]⚠[/red]" if d.spec.sensitive else "")
        table.add_row(mark, name, d.spec.category, d.spec.summary, status)

    console.print(table)
    console.print(
        "\n[dim][green]●[/green] active in missions · [yellow]○[/yellow] available "
        "but disabled · · needs setup · [red]⚠[/red] sensitive (legal/ethical "
        "weight)[/dim]"
    )
    console.print(
        "[dim]Enable a subset with SCOUT_TOOLS=id1,id2 · turn some off with "
        "SCOUT_DISABLE_TOOLS=id1,id2[/dim]"
    )
    return 0


# ── `scout models` ─────────────────────────────────────────────────────────


def _cmd_models(console: Console) -> int:
    with console.status("Querying your providers for available models..."):
        discovered = discover_all()

    if not discovered:
        console.print(
            "[yellow]No providers to query.[/yellow] Add a key (ANTHROPIC_API_KEY, "
            "OPENAI_API_KEY, GEMINI_API_KEY) or set SCOUT_API_BASE for a local "
            "model, then try again."
        )
        return 1

    _print_models(console, discovered)
    console.print(
        "\n[dim]Copy one of the IDs above into [bold]SCOUT_MODEL[/bold] in your "
        ".env.[/dim]"
    )
    return 0


def _print_models(console: Console, discovered: list[ProviderModels]) -> None:
    for pm in discovered:
        if pm.models:
            table = Table(
                title=f"[bold]{pm.provider}[/bold]"
                + (f" [dim]({pm.note})[/dim]" if pm.note else ""),
                show_header=False,
                title_justify="left",
                border_style="cyan",
            )
            for model in pm.models:
                table.add_row(model)
            console.print(table)
        else:
            console.print(
                f"[yellow]{pm.provider}[/yellow]: {pm.note or 'no models found'}"
            )


# ── `scout "<brief>"` ──────────────────────────────────────────────────────


def _cmd_run(console: Console, args: list[str]) -> int:
    if not os.getenv("SCOUT_MODEL", "").strip():
        if not _interactive_pick_model(console):
            return 1

    try:
        config = Config.from_env()
        config.check_credentials()
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        console.print("[dim]Tip: run [bold]scout models[/bold] to see your options.[/dim]")
        return 1

    console.print(
        f"[dim]Model:[/dim] {config.model}"
        + (f"  [dim]via[/dim] {config.api_base}" if config.api_base else "")
    )

    brief = " ".join(args).strip()
    if not brief:
        brief = Prompt.ask(
            "\n[bold]What do you want to know?[/bold]\n[dim]Describe the mission "
            "(what to collect, or what you're trying to accomplish)[/dim]"
        ).strip()
    if not brief:
        console.print("[red]No mission provided. Exiting.[/red]")
        return 1

    out_dir = Path(os.getenv("SCOUT_OUTPUT_DIR", "/app/output"))
    if not out_dir.exists():
        out_dir = Path.cwd() / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(brief, title="[bold]Mission[/bold]", border_style="cyan"))

    orchestrator = Orchestrator(config, console)
    try:
        paths = orchestrator.run(brief, out_dir)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Partial output may exist.[/yellow]")
        return 130
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Mission failed:[/red] {exc}")
        return 1

    console.print(
        Panel("[bold green]Mission complete[/bold green]", border_style="green")
    )
    for label, path in paths.items():
        console.print(f"  [green]·[/green] {label}: {path}")
    if "report" in paths:
        console.print(f"\n[bold]Read the report:[/bold] {paths['report']}")
    if "graph_html" in paths:
        console.print(f"[bold]Open the graph:[/bold] {paths['graph_html']}")

    return 0


def _interactive_pick_model(console: Console) -> bool:
    """When SCOUT_MODEL is unset, discover models and let the user choose one.

    Sets SCOUT_MODEL in the environment for this run. Returns False if there's
    nothing to choose from.
    """
    console.print("[dim]No SCOUT_MODEL set - discovering available models...[/dim]")
    with console.status("Querying your providers..."):
        discovered = discover_all()

    choices: list[str] = []
    for pm in discovered:
        choices.extend(pm.models)

    # Always offer the no-key demo model as a last option.
    choices.append("mock")

    if discovered:
        _print_models(console, discovered)
    else:
        console.print(
            "[yellow]No provider credentials found.[/yellow] You can still try the "
            "demo model below, or add a key to your .env (see .env.example)."
        )

    numbered = Table(show_header=True, header_style="bold", border_style="dim")
    numbered.add_column("#", justify="right")
    numbered.add_column("Model")
    for i, model in enumerate(choices, 1):
        label = (
            "mock  [dim](demo - no key, scripted, illustrative findings)[/dim]"
            if model == "mock"
            else model
        )
        numbered.add_row(str(i), label)
    console.print(numbered)

    pick = IntPrompt.ask(
        "[bold]Pick a model for this run[/bold]",
        choices=[str(i) for i in range(1, len(choices) + 1)],
        show_choices=False,
    )
    chosen = choices[pick - 1]
    os.environ["SCOUT_MODEL"] = chosen
    console.print(f"[green]Using[/green] {chosen} [dim](set SCOUT_MODEL in .env to skip this)[/dim]")
    return True


if __name__ == "__main__":
    raise SystemExit(main())
