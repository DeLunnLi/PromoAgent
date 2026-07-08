"""CLI for PromoAgent - main entry point for all commands."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__
from .analyzer import analyze_target
from .ui import console, print_banner, print_success, print_error, print_warning, print_info, print_tip, print_code, print_analysis_result, print_promo_result, print_optimize_manifest, print_platforms_table, progress_spinner, ask_for_clarifications


def main(argv: list[str] | None = None) -> int:
    argv = _normalize_argv(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("-h", "--help", "--version", "-v"):
        print_banner()

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        cmd_map = {
            "serve": _run_serve, "publish": _run_publish_cmd, "fill": _run_fill,
            "cache": _run_cache, "platforms": _run_platforms, "setup": _run_setup, "doctor": _run_doctor,
            "draft": _run_draft,
        }
        return cmd_map.get(args.command, _run_analyze)(args)
    except (RuntimeError, ValueError, FileNotFoundError) as error:
        print_error(str(error))
        return 1
    except Exception as error:
        # Catch-all for unexpected errors
        print_error(f"Unexpected error: {error}")
        if os.environ.get("DEBUG") or os.environ.get("PROMOAGENT_DEBUG"):
            console.print_exception()
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="promoagent", description="Generate promotional content from repos, papers, and PDFs.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    # analyze
    analyze = sub.add_parser("analyze", help="Show evidence extracted from a source.")
    _add_target(analyze)
    analyze.add_argument("--json", action="store_true", help="Print JSON output.")
    analyze.add_argument("-o", "--output", help="Write to file.")

    # draft - unified content generation
    draft = sub.add_parser("draft", help="Generate promotional content with interactive editing.")
    _add_target(draft)
    draft.add_argument("--stage", choices=["research", "blueprint", "produce", "all"], default="all", help="Run up to this stage.")
    draft.add_argument("--interactive", "-i", action="store_true", help="Stop at blueprint for editing.")
    draft.add_argument("--edit", help="Edit blueprint: JSON file with edits {element_id: new_content}")
    draft.add_argument("--preview", action="store_true", help="Preview blueprint content.")
    draft.add_argument("--resume", action="store_true", help="Resume from saved blueprint.")
    draft.add_argument("--parallel", action="store_true", default=True, help="Parallel platform generation.")
    draft.add_argument("--platforms", help="Comma-separated list of target platforms.")
    draft.add_argument("--image", action="store_true", help="Generate cover images.")
    draft.add_argument("--no-search", action="store_true", help="Skip reference ad search during research.")
    draft.add_argument("--quality", choices=["fast", "balanced", "polished"], default="balanced",
                       help="质量模式：fast(仅事实)/balanced(+平台知识+few-shot)/polished(+critic重写)。")
    draft.add_argument("--output-dir", default="launch-assets", help="Output directory for files.")
    draft.add_argument("--json", action="store_true", help="Output as JSON.")
    draft.add_argument("-o", "--output", help="Output file.")
    _add_ai_options(draft)

    # fill
    fill = sub.add_parser("fill", help="Auto-fill content in browser.")
    fill.add_argument("platform", help="Platform to fill.")
    fill.add_argument("--content", help="Content to fill.")
    fill.add_argument("--assets-dir", default="launch-assets", help="Assets directory.")
    fill.add_argument("--title", default="", help="Post title.")
    fill.add_argument("--headless", action="store_true", help="Headless mode.")

    # publish
    publish = sub.add_parser("publish", help="Publish to social platforms.")
    publish.add_argument("platform", nargs="?", help="Platform to publish to.")
    publish.add_argument("--content", help="Content to publish.")
    publish.add_argument("--assets-dir", default="launch-assets", help="Assets directory.")
    publish.add_argument("--title", default="", help="Post title.")
    publish.add_argument("--dry-run", action="store_true", help="Preview only.")
    publish.add_argument("--list", action="store_true", help="List configured publishers.")

    # serve — launches the MCP server (stdio) for AI tool integration.
    sub.add_parser("serve", help="Launch the MCP server (for Claude Desktop / Cursor).")

    # cache
    cache = sub.add_parser("cache", help="Manage cache.")
    cache.add_argument("--stats", action="store_true", help="Show stats.")
    cache.add_argument("--clear", action="store_true", help="Clear cache.")
    cache.add_argument("--disable", action="store_true", help="Disable cache.")

    # platforms
    sub.add_parser("platforms", help="Show supported platforms.")

    # setup
    sub.add_parser("setup", help="Interactive setup wizard.")

    # doctor
    sub.add_parser("doctor", help="Check configuration.")

    return parser


def _add_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", nargs="?", default=".", help="Source: path, URL, PDF, or description.")


def _add_ai_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", help="Override PROMOAGENT_MODEL.")
    parser.add_argument("--base-url", help="Override PROMOAGENT_BASE_URL.")
    parser.add_argument("--max-tokens", type=int, help="Override max tokens.")
    parser.add_argument("--temperature", type=float, help="Override temperature.")


def _normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["analyze", "."]
    if argv[0] in {"analyze", "draft", "fill", "publish", "serve", "cache", "platforms", "setup", "doctor", "-h", "--help", "--version"}:
        return argv
    return ["analyze", *argv]


# ---------------------------------------------------------------------------
# Command runners
# ---------------------------------------------------------------------------

def _run_analyze(args: argparse.Namespace) -> int:
    with progress_spinner("Analyzing source"):
        result = analyze_target(args.target)

    if args.json:
        _write_or_print(json.dumps(result, ensure_ascii=False, indent=2), args.output)
    else:
        print_analysis_result(result)
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    """Launch the MCP server over stdio (for Claude Desktop / Cursor)."""
    from .mcp_server import main as mcp_main
    try:
        mcp_main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


def _run_fill(args: argparse.Namespace) -> int:
    from .browser import fill_platform, list_supported_platforms
    from .publish import load_content_from_assets

    try:
        content = args.content or load_content_from_assets(args.assets_dir, args.platform)
    except FileNotFoundError as exc:
        print_error(f"{exc}\nTip: Run `promoagent draft . --output-dir {args.assets_dir}` first.")
        return 1

    fill_platform(args.platform.lower().strip(), content, title=args.title, headless=args.headless)
    return 0


def _run_publish_cmd(args: argparse.Namespace) -> int:
    from .publish import available_publishers, load_content_from_assets, publish_content, NO_API_PLATFORMS

    if args.list or args.platform is None:
        pubs = available_publishers()
        print_info(f"Configured: {', '.join(pubs) if pubs else 'None'}")
        print_info(f"Manual platforms: {', '.join(NO_API_PLATFORMS)}")
        return 0

    platform = args.platform.lower().strip()

    try:
        content = args.content or load_content_from_assets(args.assets_dir, platform)
    except FileNotFoundError as exc:
        print_error(f"{exc}\nTip: Run `promoagent draft . --output-dir {args.assets_dir}` first.")
        return 1

    if args.dry_run:
        print_info(f"[DRY RUN] Would publish to {platform}:\n{content[:500]}{'...' if len(content) > 500 else ''}")
        return 0

    result = publish_content(platform, content, title=args.title)
    print(result)
    return 0 if result.ok else 1


def _run_cache(args: argparse.Namespace) -> int:
    from . import cache
    from rich.table import Table
    from rich import box

    if args.clear:
        print_success(f"Cleared {cache.clear()} cache entries")
        return 0
    if args.disable:
        cache.disable_cache()
        print_info("Cache disabled")
        return 0

    stats = cache.get_stats()
    table = Table(title="[bold cyan]📦 Cache Statistics[/]", box=box.ROUNDED, show_header=False, border_style="blue")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Directory", stats["cache_dir"])
    table.add_row("Total", str(stats["entries"]))
    table.add_row("Valid", f"[green]{stats['valid_entries']}[/]")
    table.add_row("Expired", f"[yellow]{stats['expired_entries']}[/]")
    table.add_row("Size", f"[bold]{stats['size_human']}[/]")
    console.print(table)
    return 0


def _run_platforms(_args: argparse.Namespace) -> int:
    print_platforms_table()
    return 0


def _run_setup(_args: argparse.Namespace) -> int:
    from .setup_wizard import run_setup
    return run_setup()


def _run_doctor(_args: argparse.Namespace) -> int:
    from .setup_wizard import run_doctor
    return run_doctor()


def _run_draft(args: argparse.Namespace) -> int:
    """Run improved 3-stage content generation pipeline."""
    from .pipeline import (
        PipelineState,
        run_pipeline,
        stage_research,
        stage_blueprint,
        stage_produce,
        edit_blueprint,
        preview_blueprint,
        generate_assets,
        _source_id,
    )

    options = {k: getattr(args, k) for k in ["model", "base_url", "max_tokens", "temperature"] if getattr(args, k)}
    options["quality_mode"] = args.quality

    with progress_spinner("Analyzing source"):
        result = analyze_target(args.target)

    source_id = _source_id(result)
    state = PipelineState(source_id)

    # Handle resume mode
    blueprint_path = Path(".blueprint.json")
    if args.resume and state.has("blueprint"):
        print_info("Resuming from saved Blueprint")
        blueprint = state.get("blueprint")

        if args.edit:
            edit_file = Path(args.edit)
            if edit_file.exists():
                edits = json.loads(edit_file.read_text(encoding="utf-8"))
                blueprint = edit_blueprint(blueprint, edits)
                state.set("blueprint", blueprint)
                print_success("Applied edits to Blueprint")

        if args.preview:
            preview = preview_blueprint(blueprint)
            print(preview)
            return 0

        # Continue to produce
        research = state.get("research")
        if research is None:
            print_error("Cannot resume: research stage is missing from saved state. Re-run `promoagent draft` from the start.")
            return 1
        platforms = args.platforms.split(",") if args.platforms else None
        # result enables polished-mode backflow to re-run research on fact gaps.
        result = state.get("result")
        produce = stage_produce(blueprint, research, state, options,
                                platforms=platforms, parallel=args.parallel, result=result)

        # Generate assets
        assets = generate_assets(blueprint, produce, platforms=platforms, options=options)

        if args.json:
            output = {"produce": produce.get("data", {}), "assets": assets}
            _write_or_print(json.dumps(output, ensure_ascii=False, indent=2), args.output)
        else:
            print_promo_result(produce.get("data", {}))
        return 0

    # Run research first so we can surface gaps before blueprint.
    stop_after = args.stage if args.stage != "all" else None
    do_search = not args.no_search
    research_out = stage_research(result, state, options, search=do_search)
    outputs = {"research": research_out}

    # Interactive clarification: ask about research gaps before producing the
    # blueprint. Only in interactive, non-JSON mode, and only once per state.
    if (args.interactive and not args.json
            and stop_after != "research"
            and not state.has("clarifications")):
        gaps = (research_out.get("data", {}) or {}).get("facts", {}).get("gaps", []) or []
        if gaps:
            print_info(f"Research surfaced {len(gaps)} information gap(s). Let's clarify.")
            answers = ask_for_clarifications(gaps)
            state.set("clarifications", {"answers": answers, "timestamp": time.time()})

    # Continue to blueprint + produce. research is cached in state, so
    # run_pipeline will skip re-running it (and re-searching references).
    if stop_after != "research":
        rest = run_pipeline(result, options, stop_after=stop_after, state=state, search=do_search)
        outputs.update({k: v for k, v in rest.items() if k != "research"})

    # Handle interactive mode at blueprint stage
    if args.stage == "blueprint" or (args.interactive and "blueprint" in outputs):
        blueprint = outputs["blueprint"]

        # Also save to local file for easy editing
        blueprint_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")

        preview = preview_blueprint(blueprint)
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]BLUEPRINT PREVIEW (Editable)[/]")
        console.print("=" * 60)
        console.print(preview)
        console.print("=" * 60)

        # Show editable elements
        data = blueprint.get("data", {})
        console.print("\n[bold]Editable Elements:[/]")
        for element in data.get("elements", []):
            elem_id = element.get("id", "")
            label = element.get("label", "")
            content = element.get("content", "")[:50]
            variants = element.get("variants", [])
            marker = "✎" if element.get("editable") else " "
            console.print(f"\n  [{marker}] {elem_id}: {label}")
            console.print(f"      [dim]{content}...[/]")
            if variants:
                console.print(f"      [dim]({len(variants)} variants available)[/]")

        # Show alternative structures
        structures = data.get("structure", {}).get("alternative_structures", [])
        if structures:
            console.print("\n[bold]Alternative Structures:[/]")
            for struct in structures:
                console.print(f"  • {struct.get('name')}: {' → '.join(struct.get('order', []))}")

        print_info(f"Blueprint saved to: {blueprint_path}")
        print_tip("To continue after editing: promoagent draft --resume --stage produce")
        return 0

    # Output results
    if args.json:
        output_data = {k: v.get("data", {}) for k, v in outputs.items()}
        _write_or_print(json.dumps(output_data, ensure_ascii=False, indent=2), args.output)
    else:
        # Print summary
        if "research" in outputs:
            research_data = outputs["research"].get("data", {})
            facts = research_data.get("facts", {})
            strategy = research_data.get("strategy", {})

            console.print("\n" + "=" * 50)
            console.print("[bold cyan]RESEARCH RESULTS[/]")
            console.print("=" * 50)
            console.print(f"[bold]Core Claim:[/] {facts.get('core_claim', 'N/A')}")
            console.print(f"[bold]Positioning:[/] {strategy.get('positioning', {}).get('one_liner', 'N/A')}")
            console.print(f"[bold]Platforms:[/] {', '.join(strategy.get('recommended_platforms', []))}")

        if "blueprint" in outputs:
            blueprint_data = outputs["blueprint"].get("data", {})
            console.print("\n" + "=" * 50)
            console.print("[bold cyan]BLUEPRINT[/]")
            console.print("=" * 50)
            console.print(f"[bold]Elements:[/] {len(blueprint_data.get('elements', []))}")
            console.print(f"[bold]Key Message:[/] {blueprint_data.get('positioning', {}).get('key_message', 'N/A')[:60]}...")

        if "produce" in outputs:
            produce_data = outputs["produce"].get("data", {})
            console.print("\n" + "=" * 50)
            console.print("[bold cyan]PLATFORM CONTENT[/]")
            console.print("=" * 50)
            for platform, content in produce_data.items():
                if isinstance(content, dict) and "error" not in content:
                    md = content.get("markdown", "")[:100]
                    console.print(f"\n[bold]{platform}:[/]")
                    console.print(f"  [dim]{md}...[/]")

    # Handle file output and image generation for full pipeline
    if args.stage == "all" or args.stage == "produce":
        if hasattr(args, 'output_dir') and args.output_dir:
            # Generate and save files
            output_path = Path(args.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            produce_data = outputs.get("produce", {}).get("data", {})

            # Save platform content to files
            saved_files = []
            for platform, content in produce_data.items():
                if isinstance(content, dict) and "markdown" in content:
                    filename = f"promo-{platform}.md"
                    filepath = output_path / filename
                    filepath.write_text(content.get("markdown", ""), encoding="utf-8")
                    saved_files.append(filename)

            # Save blueprint
            blueprint = outputs.get("blueprint", {})
            (output_path / "blueprint.json").write_text(
                json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # Generate images if requested
            if args.image:
                from .image import generate_platform_images
                try:
                    image_options = {"platforms": args.platforms} if args.platforms else {}
                    images = generate_platform_images(result, output_path, image_options)
                    if images:
                        print_success(f"Generated {len(images)} images")
                except Exception as exc:
                    print_warning(f"Image generation failed: {exc}")

            print_success(f"Saved {len(saved_files)} files to {output_path}")

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_or_print(output: str, path: str | None) -> None:
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(output.rstrip() + "\n", encoding="utf-8")
        print_success(f"Saved to {p}")
    else:
        sys.stdout.write(output.rstrip() + "\n")
