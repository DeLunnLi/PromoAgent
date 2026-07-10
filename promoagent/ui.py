"""Rich-based UI components for PromoAgent.

Provides beautiful CLI output with progress bars, panels, tables, and animations.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

# Rich imports
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.syntax import Syntax
from rich.tree import Tree
from rich import box

# Global console
console = Console(stderr=True, highlight=False)
stdout_console = Console(highlight=False)


def print_banner() -> None:
    """Print the PromoAgent banner."""
    banner = """
[bold blue]╔═══════════════════════════════════════════════════════════╗[/]
[bold blue]║[/]  [bold cyan]PromoAgent[/] — [italic]Your AI Agent for Every Promotion[/]          [bold blue]║[/]
[bold blue]║[/]  [dim]Generate launch posts, ads, and multi-platform copy[/]    [bold blue]║[/]
[bold blue]╚═══════════════════════════════════════════════════════════╝[/]
"""
    console.print(banner)


def print_success(message: str, **kwargs: Any) -> None:
    """Print a success message with a green checkmark."""
    console.print(f"[bold green]✓[/] {message}", **kwargs)


def print_error(message: str, **kwargs: Any) -> None:
    """Print an error message with a red cross."""
    console.print(f"[bold red]✗[/] {message}", **kwargs)


def print_warning(message: str, **kwargs: Any) -> None:
    """Print a warning message with a yellow warning sign."""
    console.print(f"[bold yellow]⚠[/] {message}", **kwargs)


def print_info(message: str, **kwargs: Any) -> None:
    """Print an info message with a blue info sign."""
    console.print(f"[bold blue]ℹ[/] {message}", **kwargs)


def print_tip(message: str) -> None:
    """Print a tip in a nice panel."""
    console.print(Panel(
        f"[italic]{message}[/]",
        title="[bold yellow]💡 Tip[/]",
        border_style="yellow",
        box=box.ROUNDED,
    ))


def print_code(code: str, language: str = "bash", title: str | None = None) -> None:
    """Print syntax-highlighted code."""
    syntax = Syntax(code, language, theme="monokai", line_numbers=False)
    console.print(Panel(
        syntax,
        title=f"[bold]{title}" if title else None,
        border_style="dim",
        box=box.ROUNDED,
    ))


@contextmanager
def progress_spinner(description: str) -> Generator[Any, None, None]:
    """Context manager for a simple spinner."""
    with console.status(f"[bold cyan]{description}...", spinner="dots"):
        yield


@contextmanager
def print_analysis_result(result: dict[str, Any]) -> None:
    """Print a beautiful analysis result."""
    project = result.get("project", {})
    evidence = result.get("evidence", {})
    repo = result.get("repository", {})

    # Project info table
    table = Table(
        title="[bold cyan]📊 Project Analysis[/]",
        box=box.ROUNDED,
        show_header=False,
        border_style="blue",
    )
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    if project.get("name"):
        table.add_row("Name", project["name"])
    if project.get("description"):
        table.add_row("Description", project["description"][:100] + "..." if len(project["description"]) > 100 else project["description"])
    if project.get("installCommand"):
        table.add_row("Install", f"[dim]`{project['installCommand']}`[/]")
    if project.get("topics"):
        table.add_row("Topics", ", ".join(project["topics"][:5]))
    if repo.get("filesScanned"):
        table.add_row("Files Scanned", str(repo["filesScanned"]))

    console.print(table)

    # Risks panel
    risks = evidence.get("launchRisks", [])
    if risks:
        risk_table = Table(
            title="[bold yellow]⚠️ Launch Risks[/]",
            box=box.ROUNDED,
            show_header=False,
            border_style="yellow",
        )
        risk_table.add_column("#", style="dim", width=3)
        risk_table.add_column("Risk", style="yellow")

        for i, risk in enumerate(risks, 1):
            msg = risk.get("message", str(risk)) if isinstance(risk, dict) else str(risk)
            risk_table.add_row(str(i), msg)

        console.print(risk_table)
    else:
        console.print(Panel(
            "[bold green]✓ No significant risks detected[/]",
            border_style="green",
            box=box.ROUNDED,
        ))


def print_promo_result(content: dict[str, Any]) -> None:
    """Print promotional content result."""
    positioning = content.get("positioning", "")
    promotions = content.get("promotions", {})

    if positioning:
        console.print(Panel(
            f'[italic]"{positioning}"[/]',
            title="[bold cyan]🎯 Positioning[/]",
            border_style="cyan",
            box=box.ROUNDED,
        ))

    if promotions:
        console.print(f"\n[bold cyan]📱 Generated Content for {len(promotions)} Platforms:[/]\n")

        for platform, item in promotions.items():
            if isinstance(item, dict):
                title = item.get("title", "")
                md = item.get("markdown", "")
                thread = item.get("thread", []) or []
                hashtags = item.get("hashtags", []) or []
                notes = item.get("publish_notes", "") or item.get("publishNotes", "")
            else:
                title, md, thread, hashtags, notes = "", str(item), [], [], ""

            # Build a preview that surfaces thread / hashtags / notes, not just markdown.
            preview_parts: list[str] = []
            if title:
                preview_parts.append(f"[bold]{title}[/]")
            if thread:
                preview_parts.append("\n".join(f"{i+1}/ {t}" for i, t in enumerate(thread) if t))
            elif md:
                preview_parts.append(md[:500] + ("..." if len(md) > 500 else ""))
            if hashtags:
                preview_parts.append("[dim]" + " ".join(hashtags) + "[/]")
            panel_content = "\n\n".join(preview_parts) if preview_parts else "(empty)"

            console.print(Panel(
                panel_content,
                title=f"[bold]{platform.upper()}[/]",
                border_style="green" if platform in ["xiaohongshu", "xhs"] else "blue",
                box=box.ROUNDED,
                subtitle=f"[dim]📌 {notes}" if notes else None,
            ))

            # Show critic scores + backflow info when available (polished mode).
            meta = item.get("_meta") if isinstance(item, dict) else None
            if isinstance(meta, dict):
                _print_quality_meta(platform, meta)


def _print_quality_meta(platform: str, meta: dict[str, Any]) -> None:
    """Display critic scores and backflow info inline after a platform's content."""
    critique = meta.get("critique") or {}
    scores = critique.get("scores") or {}
    parts: list[str] = []

    # Score badges: fidelity / engagement / alignment + total.
    for axis in ("fidelity", "engagement", "alignment"):
        val = scores.get(axis)
        if val is not None:
            color = "green" if int(val) >= 4 else ("yellow" if int(val) >= 3 else "red")
            parts.append(f"{axis[:3]} [{color}]{val}[/]")

    total = critique.get("total")
    if total is not None:
        parts.append(f"total [bold]{total}/15[/]")

    # Backflow indicator.
    backflow = meta.get("backflow")
    if backflow and backflow.get("attempted"):
        stage = backflow.get("stage", "?")
        pre = backflow.get("pre_backflow_score", "?")
        post = backflow.get("post_backflow_score", "?")
        parts.append(f"backflow {stage} ({pre}→{post})")
    elif meta.get("rewritten"):
        parts.append("rewritten")

    skipped = meta.get("skipped")
    if skipped:
        parts.append(f"[dim]skipped: {skipped}[/]")

    if parts:
        console.print(f"  [dim]quality:[/] " + "  ".join(parts))


def print_optimize_manifest(manifest: dict[str, Any]) -> None:
    """Print the optimize command result manifest."""
    output_dir = manifest.get("outputDir", "launch-assets")
    generated = manifest.get("generated", [])
    images = manifest.get("images", [])

    # Summary
    console.print(Panel(
        f"[bold green]✓[/] Generated [bold]{len(generated)}[/] files in [bold cyan]{output_dir}[/]\n"
        f"[bold green]✓[/] Model: [dim]{manifest.get('promoModel', 'N/A')}[/]",
        title="[bold]📦 Launch Assets Created[/]",
        border_style="green",
        box=box.ROUNDED,
    ))

    # File tree
    tree = Tree(f"[bold]{output_dir}/[/]")

    text_files = [f for f in generated if not f.endswith(('.jpg', '.jpeg', '.png', '.gif'))]
    image_files = [f for f in generated if f.endswith(('.jpg', '.jpeg', '.png', '.gif'))]
    image_files += [Path(img.get("outputPath", "")).name for img in images if img.get("outputPath")]

    if text_files:
        text_branch = tree.add("[bold cyan]📝 Text Files[/]")
        for f in text_files[:10]:
            text_branch.add(f"[dim]{f}[/]")
        if len(text_files) > 10:
            text_branch.add(f"[dim]... and {len(text_files) - 10} more[/]")

    if image_files:
        img_branch = tree.add("[bold magenta]🖼️  Images[/]")
        for f in image_files[:5]:
            img_branch.add(f"[dim]{f}[/]")
        if len(image_files) > 5:
            img_branch.add(f"[dim]... and {len(image_files) - 5} more[/]")

    console.print(tree)


def print_platforms_table() -> None:
    """Print a nice table of supported platforms."""
    from .platforms import list_platforms

    table = Table(
        title="[bold cyan]📱 Supported Platforms[/]",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Platform", style="bold")
    table.add_column("Key", style="dim")
    table.add_column("Style", style="italic")
    table.add_column("API", justify="center")

    for spec in list_platforms():
        api_mark = "✅" if spec.api_support else "❌"
        table.add_row(f"{spec.icon} {spec.name_cn}", spec.key, spec.style, api_mark)

    console.print(table)


def ask_for_clarifications(gaps: list[str]) -> dict[str, str]:
    """Ask the user to fill information gaps surfaced by the research stage.

    Each gap is prompted in turn; empty answers are skipped. Prompts render on
    the stderr ``console`` so ``--json`` stdout stays clean.
    """
    if not gaps:
        return {}

    console.print(Panel(
        "\n".join(f"• {g}" for g in gaps),
        title="[bold yellow]信息缺口[/]",
        border_style="yellow",
    ))
    console.print("[dim]补充后可提升推广质量，直接回车跳过不需要的问题。[/]")

    answers: dict[str, str] = {}
    for gap in gaps:
        # console=console routes prompt + echo to stderr, keeping stdout clean.
        answer = Prompt.ask(f"  {gap}", default="", console=console)
        if answer.strip():
            answers[gap] = answer.strip()
    return answers


class LiveProgress:
    """Live progress display for multi-stage operations."""

    def __init__(self, stages: list[str]):
        self.stages = stages
        self.current = 0
        self.console = Console(stderr=True)

    def __enter__(self) -> LiveProgress:
        self._render()
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def next(self, message: str | None = None) -> None:
        """Move to next stage."""
        self.current += 1
        self._render(message)

    def _render(self, message: str | None = None) -> None:
        """Render current state."""
        self.console.clear()
        print_banner()

        for i, stage in enumerate(self.stages):
            if i < self.current:
                self.console.print(f"[bold green]✓[/] [dim]{stage}[/]")
            elif i == self.current:
                self.console.print(f"[bold cyan]→[/] [bold]{stage}[/]" + (f" — {message}" if message else ""))
            else:
                self.console.print(f"[dim]○ {stage}[/]")
