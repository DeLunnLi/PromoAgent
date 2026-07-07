"""CLI for PromoAgent - main entry point for all commands."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .ai import generate_ai_content, has_ai_key, refine_content
from .analyzer import analyze_target
from .optimize import run_optimize
from .promo_prompts import build_evidence_brief, build_promo_payload, build_promo_system_prompt, build_promo_user_prompt, expand_presets
from .ui import console, print_banner, print_success, print_error, print_info, print_tip, print_code, print_analysis_result, print_promo_result, print_optimize_manifest, print_platforms_table, progress_spinner

_SESSION_FILE = ".promoagent-session.json"


def main(argv: list[str] | None = None) -> int:
    argv = _normalize_argv(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("-h", "--help", "--version", "-v"):
        print_banner()

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        cmd_map = {
            "promote": _run_promote, "optimize": _run_optimize, "refine": _run_refine,
            "serve": _run_serve, "publish": _run_publish_cmd, "fill": _run_fill,
            "cache": _run_cache, "platforms": _run_platforms, "setup": _run_setup, "doctor": _run_doctor,
        }
        return cmd_map.get(args.command, _run_analyze)(args)
    except Exception as error:
        print_error(str(error))
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

    # promote
    promote = sub.add_parser("promote", help="Generate promotional content.")
    _add_target(promote)
    promote.add_argument("--platform", default="all", help="Target platform(s).")
    promote.add_argument("--ai", action="store_true", help="Use AI to generate copy.")
    promote.add_argument("-i", "--interactive", action="store_true", help="Ask clarifying questions.")
    promote.add_argument("--no-examples", action="store_true", help="Skip example search.")
    promote.add_argument("--json", action="store_true", help="Print JSON.")
    promote.add_argument("-o", "--output", help="Write to file.")
    _add_ai_options(promote)
    _add_context_options(promote)

    # optimize
    optimize = sub.add_parser("optimize", help="Save content to launch-assets/ folder.")
    _add_target(optimize)
    optimize.add_argument("--output", "--output-dir", dest="output_dir", default="launch-assets", help="Output directory.")
    optimize.add_argument("--ai", action="store_true", help="Use AI.")
    optimize.add_argument("-i", "--interactive", action="store_true", help="Ask questions.")
    optimize.add_argument("--no-examples", action="store_true", help="Skip examples.")
    optimize.add_argument("--image", action="store_true", help="Generate cover images.")
    optimize.add_argument("--image-model", dest="image_model", help="Image model override.")
    optimize.add_argument("--image-platforms", dest="image_platforms", help="Comma-separated platforms for cover images.")
    optimize.add_argument("--image-style", dest="image_style", help="Visual style hint for cover images.")
    optimize.add_argument("--image-skill", dest="image_skill", help="Creative image skill: auto, ad-cover, xhs-lifestyle, food-local, product-hero, event-poster, b2b-saas, research-editorial, service-trust.")
    optimize.add_argument("--image-interactive", action="store_true", help="Ask for ad image brief before generation.")
    optimize.add_argument("--image-title", dest="image_title", help="Ad headline rendered as local overlay.")
    optimize.add_argument("--image-subtitle", dest="image_subtitle", help="Ad subhead rendered as local overlay.")
    optimize.add_argument("--image-cta", dest="image_cta", help="CTA text rendered as local overlay.")
    optimize.add_argument("--image-badges", dest="image_badges", help="Comma-separated badges rendered as local overlay.")
    optimize.add_argument("--image-note", dest="image_note", help="Creative direction for image prompt.")
    optimize.add_argument("--image-variants", dest="image_variants", type=int, help="Number of image variants per platform.")
    optimize.add_argument("--no-image-text-overlay", action="store_true", help="Disable local ad text overlay.")
    _add_ai_options(optimize)
    _add_context_options(optimize)

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

    # serve
    serve = sub.add_parser("serve", help="Launch web interface.")
    serve.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve.add_argument("--port", type=int, default=7860, help="Port.")
    serve.add_argument("--share", action="store_true", help="Create public link.")

    # refine
    refine = sub.add_parser("refine", help="Refine generated content.")
    refine.add_argument("feedback", help="What to change.")
    refine.add_argument("--platform", help="Target platform.")
    refine.add_argument("--session", default=_SESSION_FILE, help="Session file.")
    refine.add_argument("-o", "--output", help="Output file.")
    _add_ai_options(refine)

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


def _add_context_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--context", action="append", default=[], help="Extra context file/URL.")
    parser.add_argument("--prompt-note", action="append", default=[], help="Writing instructions.")
    parser.add_argument("--prompt-preset", action="append", default=[], help="Preset name(s).")


def _normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["analyze", "."]
    if argv[0] in {"analyze", "promote", "optimize", "fill", "publish", "serve", "refine", "cache", "platforms", "setup", "doctor", "-h", "--help", "--version"}:
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


def _run_promote(args: argparse.Namespace) -> int:
    from .interactive import ask_and_merge, has_significant_gaps

    with progress_spinner("Analyzing source"):
        result = analyze_target(args.target)

    if args.interactive or (not args.json and has_significant_gaps(result)):
        result = ask_and_merge(result, force=args.interactive)

    payload = build_promo_payload(result)
    brief = _build_brief(args)

    if args.ai:
        ai_result = _call_ai(result, platform=args.platform, brief=brief, args=args)
        _save_session(ai_result, result)
        if args.json:
            _write_or_print(json.dumps({"ai": {"content": ai_result["content"], "model": ai_result["model"]}, "project": result["project"]}, ensure_ascii=False, indent=2), args.output)
        else:
            print_promo_result(ai_result["content"])
            print_tip("Run `promoagent refine \"<feedback>\"` to refine content")
    elif args.json:
        _write_or_print(json.dumps({"platform": args.platform, "system": build_promo_system_prompt(), "user": build_promo_user_prompt(payload, platform=args.platform, brief_section=brief), "evidenceBrief": build_evidence_brief(payload), "payload": payload}, ensure_ascii=False, indent=2), args.output)
    else:
        print_info("Analysis complete. Run with --ai to generate content.")
        print_code(build_evidence_brief(payload), language="markdown", title="Evidence Brief")
        print_tip("Set PROMOAGENT_API_KEY to enable AI generation")
    return 0


def _run_optimize(args: argparse.Namespace) -> int:
    from .interactive import ask_and_merge, has_significant_gaps

    with progress_spinner("Analyzing source"):
        result = analyze_target(args.target)

    if args.interactive or has_significant_gaps(result):
        result = ask_and_merge(result, force=args.interactive)

    ai_result = _call_ai(result, platform="all", brief=_build_brief(args), args=args) if args.ai else None
    image_options = None
    if args.image:
        image_options = {
            k: v for k, v in {
                "model": args.image_model,
                "platforms": args.image_platforms,
                "style": args.image_style,
                "skill": args.image_skill,
                "title": args.image_title,
                "subtitle": args.image_subtitle,
                "cta": args.image_cta,
                "badges": args.image_badges,
                "note": args.image_note,
                "variants": args.image_variants,
                "text_overlay": False if args.no_image_text_overlay else None,
            }.items() if v
        }
        if args.no_image_text_overlay:
            image_options["text_overlay"] = False
        if args.image_interactive:
            from .image import ask_image_brief_interactively
            image_options = ask_image_brief_interactively(result, image_options)

    with progress_spinner("Generating launch assets"):
        manifest = run_optimize(
            result, cwd=Path.cwd(), output_dir=args.output_dir,
            ai_content=ai_result.get("content") if ai_result else None,
            ai_model=ai_result.get("model") if ai_result else None,
            generate_images=args.image, image_options=image_options,
        )

    print_optimize_manifest(manifest)
    print_tip("Run `promoagent refine \"<feedback>\"` to iterate")
    return 0


def _run_refine(args: argparse.Namespace) -> int:
    session_path = Path(args.session)
    if not session_path.exists():
        print_error(f"Session file not found: {session_path}\nRun `promoagent promote ... --ai` first.")
        return 1

    previous = json.loads(session_path.read_text(encoding="utf-8"))
    options = {k: getattr(args, k) for k in ["model", "base_url", "max_tokens", "temperature"] if getattr(args, k)}

    try:
        ai_result = refine_content(previous, args.feedback, platform=args.platform, options=options)
    except Exception as exc:
        print_error(str(exc))
        return 1

    _save_session(ai_result)
    _write_or_print(_format_ai_output(previous.get("result", {"project": {}}), ai_result["content"]), args.output)
    print_success("Content refined. Run `refine` again to continue.")
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    try:
        from .web import launch
    except ImportError:
        print_error("Gradio required. Install: pip install gradio")
        return 1
    launch(host=args.host, port=args.port, share=args.share)
    return 0


def _run_fill(args: argparse.Namespace) -> int:
    from .browser import fill_platform, list_supported_platforms
    from .publish import load_content_from_assets

    try:
        content = args.content or load_content_from_assets(args.assets_dir, args.platform)
    except FileNotFoundError as exc:
        print_error(f"{exc}\nTip: Run `promoagent optimize --ai` first.")
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
        print_error(f"{exc}\nTip: Run `promoagent optimize --ai` first.")
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_ai(result: dict[str, Any], *, platform: str, brief: str, args: argparse.Namespace) -> dict[str, Any]:
    if not has_ai_key():
        raise RuntimeError("No API key found. Set PROMOAGENT_API_KEY or PROMOAGENT_MODELSCOPE_API_KEY.")

    options = {k: getattr(args, k) for k in ["model", "base_url", "max_tokens", "temperature"] if getattr(args, k)}

    examples = None
    if not args.no_examples:
        from .examples import find_examples
        examples = find_examples(result, platform=platform, ai_options=options) or None

    return generate_ai_content(result, platform=platform, brief_section=brief, examples=examples, options=options)


def _build_brief(args: argparse.Namespace) -> str:
    parts = []
    if presets := _flatten(args.prompt_preset):
        if expanded := expand_presets(presets):
            parts += ["## Prompt Presets", "", expanded, ""]
    if args.prompt_note:
        parts += ["## Writing Instructions", ""] + [f"- {n}" for n in args.prompt_note] + [""]
    if args.context:
        parts += ["## Additional Context", ""] + [_format_context(c) for c in args.context] + [""]
    return "\n".join(parts).strip()


def _flatten(values: list[str]) -> list[str]:
    result = []
    for v in values:
        result.extend(p.strip() for p in str(v or "").split(",") if p.strip())
    return result


def _format_context(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith(("http://", "https://")):
        return f"### Remote context: {raw}\nUse as review note; content may not have been fetched."
    path = Path(raw).expanduser()
    if not path.exists():
        return f"### Note: {raw}"
    if path.is_dir():
        return f"### Directory context: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    clipped = text if len(text) <= 4000 else text[:4000] + "\n\n...[truncated]"
    return f"### Context: {path.name}\n\n{clipped}"


def _format_ai_output(result: dict[str, Any], content: dict[str, Any]) -> str:
    project = result.get("project", {})
    lines = [f"# {project.get('name', 'Project')} · Launch Content", ""]
    if positioning := content.get("positioning"):
        lines.append(f"**Positioning:** {positioning}")
    if strategy := content.get("promotionStrategy", {}):
        if core_angle := strategy.get("coreAngle"):
            lines += ["## Strategy", "", core_angle, ""]
    if promotions := content.get("promotions", {}):
        for key, item in promotions.items():
            if isinstance(item, dict) and (md := item.get("markdown")):
                lines += [f"## {key}", "", str(md).strip(), ""]
    if len(lines) <= 4:
        lines.append(json.dumps(content, ensure_ascii=False, indent=2))
    return "\n".join(lines).rstrip()


def _save_session(ai_result: dict[str, Any], result: dict[str, Any] | None = None) -> None:
    session = {"messages": ai_result.get("messages", []), "content": ai_result.get("content", {}), "model": ai_result.get("model"), "baseUrl": ai_result.get("baseUrl")}
    if result:
        session["result"] = result
    try:
        Path(_SESSION_FILE).write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _write_or_print(output: str, path: str | None) -> None:
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(output.rstrip() + "\n", encoding="utf-8")
        print_success(f"Saved to {p}")
    else:
        sys.stdout.write(output.rstrip() + "\n")
