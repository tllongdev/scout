"""Coordinates a full mission: plan -> collect -> synthesize -> report."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.rule import Rule

from .agents.collector import run_collector
from .agents.planner import plan_mission
from .agents.synthesizer import synthesize
from .config import Config
from .llm import LLM
from .models import Mission
from .output import write_outputs
from .tools.recommend import recommend_tools


class Orchestrator:
    def __init__(self, config: Config, console: Console) -> None:
        self.config = config
        self.console = console
        self.llm = LLM(config, console)

    def run(self, brief: str, out_dir: Path) -> dict[str, Path]:
        mission = Mission(brief=brief)

        # ── Plan ──────────────────────────────────────────────────────────
        self.console.print(Rule("[bold cyan]Planning[/bold cyan]"))
        with self.console.status("Decomposing the mission into tasks..."):
            tasks = plan_mission(self.llm, mission, self.config.max_tasks)
        mission.tasks = tasks

        for i, task in enumerate(tasks, 1):
            flag = " [yellow](may need you)[/yellow]" if task.needs_human else ""
            self.console.print(f"  [cyan]{i}.[/cyan] {task.objective}{flag}")

        # ── Recommend tools the operator could enable to go deeper ──────────
        mission.tool_suggestions = recommend_tools(mission)
        if mission.tool_suggestions:
            self.console.print(
                "\n[bold yellow]Tools that could help this mission "
                "(not enabled):[/bold yellow]"
            )
            for s in mission.tool_suggestions:
                self.console.print(
                    f"  [yellow]·[/yellow] [bold]{escape(s.name)}[/bold] - "
                    f"{escape(s.summary)}\n"
                    f"      [dim]{escape(s.why)} → to enable: "
                    f"{escape(s.how_to_enable)}[/dim]"
                )

        # ── Collect ───────────────────────────────────────────────────────
        for i, task in enumerate(tasks, 1):
            self.console.print(
                Rule(f"[bold green]Collecting {i}/{len(tasks)}[/bold green]")
            )
            self.console.print(f"[dim]{task.objective}[/dim]")
            task.status = "running"

            def on_step(step: int, action: str, _task=task) -> None:
                if action == "done":
                    self.console.print("  [dim]· wrapping up[/dim]")
                else:
                    self.console.print(f"  [dim]· step {step}: {action}[/dim]")

            try:
                summary = run_collector(
                    self.llm, self.config, mission, task, self.console, on_step
                )
                task.status = "done"
                if summary:
                    self.console.print(f"  [green]✓[/green] {summary}")
            except Exception as exc:  # noqa: BLE001
                task.status = "failed"
                self.console.print(f"  [red]✗ task failed: {exc}[/red]")

        # ── Synthesize ────────────────────────────────────────────────────
        self.console.print(Rule("[bold magenta]Synthesizing[/bold magenta]"))
        with self.console.status("Drawing conclusions from the graph..."):
            synthesize(self.llm, mission)
        self.console.print(
            f"  [magenta]{len(mission.entities)}[/magenta] entities · "
            f"[magenta]{len(mission.edges)}[/magenta] relationships · "
            f"[magenta]{len(mission.findings)}[/magenta] findings"
        )

        # ── Report ────────────────────────────────────────────────────────
        return write_outputs(mission, out_dir)
