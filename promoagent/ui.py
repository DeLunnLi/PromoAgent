"""Rich-based UI components for PromoAgent.

Provides beautiful CLI output with progress bars, panels, tables, and animations.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

# Rich imports
from rich.console import Console
from rich.panel import Panel
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
from rich.align import Align
from rich.columns import Columns
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
def progress_bar(description: str, total: int | None = None) -> Generator[Progress, None, None]:
    """Context manager for a progress bar."""
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(complete_style="green", finished_style="bright_green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    )
    with progress:
        task = progress.add_task(description, total=total)
        yield progress


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
            md = item.get("markdown", "") if isinstance(item, dict) else str(item)
            notes = item.get("publishNotes", "") if isinstance(item, dict) else ""

            panel_content = md[:500] + "..." if len(md) > 500 else md

            console.print(Panel(
                panel_content,
                title=f"[bold]{platform.upper()}[/]",
                border_style="green" if platform in ["xiaohongshu", "xhs"] else "blue",
                box=box.ROUNDED,
                subtitle=f"[dim]{notes}" if notes else None,
            ))


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

    platforms = [
        ("小红书", "xhs", "图文种草，口语化", "❌"),
        ("知乎", "zhihu", "专业深度，结构化", "❌"),
        ("微信", "wechat", "正式，长内容", "❌"),
        ("Twitter/X", "twitter", "简洁有力，280字", "✅"),
        ("LinkedIn", "linkedin", "专业人脉，B2B", "✅"),
        ("Reddit", "reddit", "社区驱动，真实", "✅"),
        ("Show HN", "showhn", "极简，技术原创", "❌"),
        ("Product Hunt", "producthunt", "发布日，tagline", "❌"),
        ("Telegram", "telegram", "频道/群组", "✅"),
        ("Bluesky", "bluesky", "去中心化", "✅"),
        ("微博", "weibo", "大众社交，140字", "✅"),
    ]

    for name, key, style, api in platforms:
        table.add_row(name, key, style, api)

    console.print(table)


def interactive_select_platforms() -> list[str]:
    """Interactive platform selection (if inquirer is available)."""
    try:
        import inquirer
        from inquirer import Checkbox, Text

        questions = [
            Checkbox(
                'platforms',
                message="Select platforms (Space to select, Enter to confirm)",
                choices=[
                    ('小红书 (Xiaohongshu)', 'xhs'),
                    ('知乎 (Zhihu)', 'zhihu'),
                    ('微信 (WeChat)', 'wechat'),
                    ('Twitter/X', 'twitter'),
                    ('LinkedIn', 'linkedin'),
                    ('Reddit', 'reddit'),
                    ('Show HN', 'showhn'),
                    ('Product Hunt', 'producthunt'),
                    ('Telegram', 'telegram'),
                    ('Bluesky', 'bluesky'),
                    ('微博 (Weibo)', 'weibo'),
                ],
                default=['xhs', 'twitter'],
            ),
        ]

        answers = inquirer.prompt(questions)
        return answers['platforms'] if answers else ['all']
    except ImportError:
        # Fallback to simple input
        console.print("[dim]Install 'inquirer' for interactive selection: pip install inquirer[/]")
        return ['all']


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
