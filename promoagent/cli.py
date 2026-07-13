"""CLI for PromoAgent - main entry point for all commands."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import __version__
from .analyzer import analyze_target
from .ui import console, print_banner, print_success, print_error, print_warning, print_info, print_tip, print_analysis_result, print_promo_result, print_platforms_table, progress_spinner, ask_for_clarifications


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
        _report_error(args, str(error))
        return 1
    except Exception as error:
        # Catch-all for unexpected errors
        msg = f"Unexpected error: {error}"
        _report_error(args, msg)
        if os.environ.get("DEBUG") or os.environ.get("PROMOAGENT_DEBUG"):
            console.print_exception()
        return 1


def _report_error(args: argparse.Namespace, message: str) -> None:
    """Surface an error to both the human (stderr) and, in --json mode, the
    machine (stdout). Without the stdout path, scripts/CI/MCP callers that
    parse ``--json`` output get an empty stdout on failure and can't tell
    why."""
    print_error(message)
    if getattr(args, "json", False) and not getattr(args, "output", None):
        # Emit a structured error to stdout so JSON consumers can parse it.
        sys.stdout.write(json.dumps({"ok": False, "error": message}, ensure_ascii=False) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="promoagent", description="AI agent for multi-platform promotional content — repos, papers, PDFs → platform-native copy + card images.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    # analyze
    analyze = sub.add_parser("analyze", help="Extract evidence from a source (repo/PDF/text). Run this first to see what PromoAgent finds.")
    _add_target(analyze)
    analyze.add_argument("--json", action="store_true", help="Print JSON output.")
    analyze.add_argument("-o", "--output", help="Write to file.")

    # draft - unified content generation
    draft = sub.add_parser("draft", help="Generate promotional content: research → blueprint → produce. Use --quality polished for best results.")
    _add_target(draft)
    draft.add_argument("--stage", choices=["research", "blueprint", "produce", "all"], default="all", help="Run up to this stage.")
    draft.add_argument("--interactive", "-i", action="store_true", help="Stop at blueprint for editing.")
    draft.add_argument("--edit", help="Edit blueprint: JSON file with edits {element_id: new_content}")
    draft.add_argument("--preview", action="store_true", help="Preview blueprint content.")
    draft.add_argument("--resume", action="store_true", help="Resume from saved blueprint.")
    draft.add_argument("--platforms", help="Comma-separated list of target platforms.")
    draft.add_argument("--image", action="store_true", help="Generate cover images.")
    draft.add_argument("--image-style", choices=["card", "photo", "auto"], default="auto",
                       help="Image style: card (HTML card render, xhs) / photo (AI image) / auto (xhs→card, else photo).")
    draft.add_argument("--no-search", action="store_true", help="Skip reference ad search during research.")
    draft.add_argument("--quality", choices=["fast", "balanced", "polished"], default="balanced",
                       help="质量模式：fast(仅事实)/balanced(+平台知识+few-shot)/polished(+critic重写)。")
    draft.add_argument("--output-dir", default="launch-assets", help="Output directory for files.")
    draft.add_argument("--dry-run", action="store_true", help="Run research/blueprint only, skip produce (saves API calls).")
    draft.add_argument("--json", action="store_true", help="Output as JSON.")
    draft.add_argument("-o", "--output", help="Output file.")
    _add_ai_options(draft)

    # fill
    fill = sub.add_parser("fill", help="Auto-fill content in browser (use 'all' for every platform).")
    fill.add_argument("platform", help="Platform to fill (or 'all' for every available).")
    fill.add_argument("--content", help="Content to fill.")
    fill.add_argument("--assets-dir", default="launch-assets", help="Assets directory.")
    fill.add_argument("--title", default="", help="Post title.")
    fill.add_argument("--no-headless", action="store_true", help="Show browser window (default: headless).")

    # publish
    publish = sub.add_parser("publish", help="Publish to social platforms (use 'all' for API + browser fill).")
    publish.add_argument("platform", nargs="?", help="Platform to publish to (or 'all' for every available).")
    publish.add_argument("--content", help="Content to publish.")
    publish.add_argument("--assets-dir", default="launch-assets", help="Assets directory.")
    publish.add_argument("--title", default="", help="Post title.")
    publish.add_argument("--dry-run", action="store_true", help="Preview only.")
    publish.add_argument("--list", action="store_true", help="List configured publishers.")
    publish.add_argument("--no-headless", action="store_true", help="Show browser window for manual platforms (default: headless).")

    # serve — launches the MCP server (stdio) for AI tool integration.
    sub.add_parser("serve", help="Launch the MCP server (for Claude Desktop / Cursor).")

    # cache
    cache = sub.add_parser("cache", help="Manage cache.")
    cache.add_argument("--stats", action="store_true", help="Show stats.")
    cache.add_argument("--clear", action="store_true", help="Clear cache.")
    cache.add_argument("--disable", action="store_true", help="Disable cache.")
    cache.add_argument("--enable", action="store_true", help="Re-enable cache after --disable.")

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
        print_tip("Run `promoagent draft .` to generate promotional content from this source.")
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

    raw = args.platform.lower().strip()
    if raw == "all":
        platforms = list_supported_platforms()
        if not platforms:
            print_error("No supported fill platforms found.")
            return 1
        print_info(f"Filling {len(platforms)} platforms: {', '.join(platforms)}")
    else:
        platforms = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]

    failures = 0
    succeeded: list[str] = []
    for plat in platforms:
        try:
            content = args.content or load_content_from_assets(args.assets_dir, plat)
            # Extract hashtags from content if present (optimize writes them as
            # the last line, e.g. "#tag1 #tag2"). Pass to filler so XHS etc.
            # can fill the tag field.
            tags = _extract_tags(content) if not args.content else None
            print_info(f"Filling {plat}...")
            fill_platform(plat, content, title=args.title, tags=tags, headless=not args.no_headless)
            print_success(f"Done: {plat}")
            succeeded.append(plat)
        except FileNotFoundError as exc:
            print_error(f"{plat}: {exc}")
            failures += 1
        except Exception as exc:  # noqa: BLE001
            print_error(f"{plat}: {exc}")
            failures += 1
    if len(platforms) > 1:
        print_info(f"Fill summary: {len(succeeded)} succeeded, {failures} failed"
                   + (f" ({', '.join(succeeded)})" if succeeded else ""))
    return 1 if failures else 0


def _run_publish_cmd(args: argparse.Namespace) -> int:
    from .publish import available_publishers, load_content_from_assets, publish_content, NO_API_PLATFORMS

    if args.list or args.platform is None:
        pubs = available_publishers()
        print_info(f"Configured API publishers: {', '.join(pubs) if pubs else 'None'}")
        print_info(f"Manual platforms (browser fill): {', '.join(NO_API_PLATFORMS)}")
        print_tip("Use `promoagent publish all` to publish to every available platform.")
        return 0

    raw = args.platform.lower().strip()

    # Determine the target platform list.
    if raw == "all":
        api_platforms = list(available_publishers())
        manual_platforms = [p for p in NO_API_PLATFORMS if _has_assets_for(args.assets_dir, p)]
        platforms = api_platforms + manual_platforms
        if not platforms:
            print_error("No platforms available. Configure API keys or run `promoagent draft` first.")
            return 1
        print_info(f"Publishing to {len(platforms)} platforms: {', '.join(platforms)}")
    else:
        platforms = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]

    failures = 0
    succeeded: list[str] = []
    for plat in platforms:
        # Validate platform is known before trying to load content.
        from .publish import _PUBLISH_ALIASES
        resolved = _PUBLISH_ALIASES.get(plat.lower(), plat).lower()
        if resolved not in NO_API_PLATFORMS and resolved not in available_publishers():
            print_error(f"{plat}: Unknown platform. Use `promoagent publish --list` to see supported platforms.")
            failures += 1
            continue

        try:
            content = args.content or load_content_from_assets(args.assets_dir, plat)
        except FileNotFoundError as exc:
            print_error(f"{plat}: {exc}")
            failures += 1
            continue

        if args.dry_run:
            print_info(f"[DRY RUN] {plat}:\n{content[:300]}{'...' if len(content) > 300 else ''}")
            succeeded.append(plat)
            continue

        # Route: API platform → publish_content; manual platform → browser fill.
        if plat in NO_API_PLATFORMS:
            print_info(f"{plat}: opening browser (manual platform)...")
            from .browser import fill_platform
            tags = _extract_tags(content)
            fill_platform(plat, content, title=args.title, tags=tags, headless=not args.no_headless)
            print_success(f"{plat}: browser filled")
            succeeded.append(plat)
        else:
            result = publish_content(plat, content, title=args.title)
            if result.ok:
                print_success(f"{plat}: published")
                succeeded.append(plat)
            else:
                print_error(f"{plat}: {result.error}")
                failures += 1
    if len(platforms) > 1:
        print_info(f"Publish summary: {len(succeeded)} succeeded, {failures} failed"
                   + (f" ({', '.join(succeeded)})" if succeeded else ""))
    return 1 if failures else 0


def _has_assets_for(assets_dir: str, platform: str) -> bool:
    """Quick check whether a promo file exists for this platform (no exception)."""
    from .optimize import _platform_filename
    from pathlib import Path
    return (Path(assets_dir) / _platform_filename(platform)).exists()


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
    if getattr(args, "enable", False):
        os.environ.pop("PROMOAGENT_CACHE_DISABLED", None)
        print_success("Cache enabled")
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

        # --dry-run on resume: just show blueprint, skip produce.
        if args.dry_run:
            print_info("Dry run: skipping produce (blueprint already saved).")
            console.print(preview_blueprint(blueprint))
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
                                platforms=platforms, result=result)

        # Generate assets
        assets = generate_assets(blueprint, produce, platforms=platforms, options=options)

        # Save files + images (resume was previously skipping this).
        outputs = {"produce": produce, "blueprint": blueprint, "research": research}
        _save_draft_outputs(args, outputs, result or {})

        if args.json:
            # Match normal-path schema: {research, blueprint, produce} as data dicts.
            output = {
                "research": research.get("data", {}),
                "blueprint": blueprint.get("data", {}),
                "produce": produce.get("data", {}),
            }
            _write_or_print(json.dumps(output, ensure_ascii=False, indent=2), args.output)
        else:
            print_promo_result(produce.get("data", {}))
        return 0

    # Run research first so we can surface gaps before blueprint.
    stop_after = args.stage if args.stage != "all" else None
    # --interactive: stop at blueprint for editing (don't waste produce API calls).
    # --dry-run: also stop after blueprint, skip produce (saves API calls).
    # --dry-run always wins even if --stage produce is set (don't waste API calls).
    if args.interactive and stop_after is None:
        stop_after = "blueprint"
    if args.dry_run:
        stop_after = "blueprint"
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
    # Pass --platforms so produce generates for the user's selection.
    user_platforms = [p.strip() for p in args.platforms.split(",")] if args.platforms else None
    if stop_after != "research":
        rest = run_pipeline(result, options, stop_after=stop_after, state=state,
                            search=do_search, platforms=user_platforms)
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
    if (args.stage == "all" or args.stage == "produce") and not args.dry_run:
        _save_draft_outputs(args, outputs, result)

    return 0


def _save_draft_outputs(args: argparse.Namespace, outputs: dict, result: dict) -> None:
    """Save produce content to files + generate images. Extracted from _run_draft."""
    if not getattr(args, "output_dir", None):
        return

    from .optimize import _format_platform_content, _platform_filename

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    produce_data = outputs.get("produce", {}).get("data", {})

    # Save platform content to files — use _format_platform_content to surface
    # title/thread/hashtags/publish_notes, not just markdown.
    saved_files = []
    for platform, content in produce_data.items():
        if isinstance(content, dict) and "error" not in content:
            rendered = _format_platform_content(content)
            if rendered:
                filename = _platform_filename(platform)
                filepath = output_path / filename
                filepath.write_text(rendered, encoding="utf-8")
                saved_files.append(filename)

    # Save blueprint
    blueprint = outputs.get("blueprint", {})
    (output_path / "blueprint.json").write_text(
        json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Generate images if requested
    if getattr(args, "image", False):
        from .image import generate_platform_images
        try:
            image_options = {"platforms": args.platforms} if args.platforms else {}
            images = generate_platform_images(
                result, output_path, image_options,
                produce_data=produce_data,
                image_style=getattr(args, "image_style", "auto"),
            )
            if images:
                print_success(f"Generated {len(images)} images")
        except Exception as exc:
            print_warning(f"Image generation failed: {exc}")

    print_success(f"Saved {len(saved_files)} files to {output_path}")


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


def _extract_tags(content: str) -> list[str] | None:
    """Extract hashtags from content's last non-empty line (optimize format)."""
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if not lines:
        return None
    last = lines[-1]
    tags = [w for w in last.split() if w.startswith("#")]
    return tags if tags else None
