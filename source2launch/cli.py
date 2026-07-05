from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .ai import build_promo_payload, generate_ai_content, has_ai_key, refine_content
from .analyzer import analyze_target
from .optimize import run_optimize
from .promo_prompts import build_evidence_brief, build_promo_system_prompt, build_promo_user_prompt, expand_presets

# File where the last generation context is saved for multi-turn refinement
_SESSION_FILE = ".s2l-session.json"


def main(argv: list[str] | None = None) -> int:
    argv = _normalize_argv(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "promote":
            return _run_promote(args)
        if args.command == "optimize":
            return _run_optimize(args)
        if args.command == "refine":
            return _run_refine(args)
        return _run_analyze(args)
    except Exception as error:  # noqa: BLE001
        print(f"source2launch: {error}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="source2launch",
        description="Generate launch promotional content from repos, papers, and PDFs.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    # analyze
    analyze = sub.add_parser("analyze", help="Show what evidence was extracted from a source.")
    _add_target(analyze)
    analyze.add_argument("--json", action="store_true", help="Print full JSON.")
    analyze.add_argument("-o", "--output", help="Write output to a file.")

    # promote
    promote = sub.add_parser("promote", help="Generate promotional content from a source.")
    _add_target(promote)
    promote.add_argument("--platform", default="all", help="Target platform(s): xhs, zhihu, wechat, launch, all.")
    promote.add_argument("--ai", action="store_true", help="Call the configured AI model to generate copy.")
    promote.add_argument("--interactive", "-i", action="store_true",
                         help="Ask clarifying questions before generating (auto-enabled when info is thin).")
    promote.add_argument("--no-examples", action="store_true",
                         help="Skip Stage 1 example search; generate directly (faster, no extra API call).")
    promote.add_argument("--json", action="store_true", help="Print JSON output.")
    promote.add_argument("-o", "--output", help="Write output to a file.")
    _add_ai_options(promote)
    _add_context_options(promote)

    # optimize
    optimize = sub.add_parser("optimize", help="Save promotional content to a launch-assets/ folder.")
    _add_target(optimize)
    optimize.add_argument("--output", "--output-dir", dest="output_dir", default="launch-assets",
                          help="Output directory (default: launch-assets).")
    optimize.add_argument("--ai", action="store_true", help="Call the configured AI model to generate copy.")
    optimize.add_argument("--interactive", "-i", action="store_true",
                         help="Ask clarifying questions before generating.")
    optimize.add_argument("--no-examples", action="store_true",
                         help="Skip Stage 1 example search.")
    optimize.add_argument("--image", action="store_true",
                          help="Also generate cover images (README screenshots + AI cover). "
                               "Requires SOURCE2LAUNCH_MODELSCOPE_API_KEY for AI images.")
    optimize.add_argument("--image-model", dest="image_model", default=None,
                          help="Override image model ID (default: from SOURCE2LAUNCH_IMAGE_MODEL or Qwen/Qwen-Image).")
    _add_ai_options(optimize)
    _add_context_options(optimize)

    # refine
    refine = sub.add_parser("refine", help="Refine previously generated content with feedback.")
    refine.add_argument("feedback", help="What to change, e.g. \"小红书那条太广告感了，改得更像真实探店\".")
    refine.add_argument("--platform", default=None, help="Focus refinement on a specific platform.")
    refine.add_argument("--session", default=_SESSION_FILE,
                        help=f"Path to saved session file (default: {_SESSION_FILE}).")
    refine.add_argument("-o", "--output", help="Write refined output to a file.")
    _add_ai_options(refine)

    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["analyze", "."]
    commands = {"analyze", "promote", "optimize"}
    if argv[0] in commands or argv[0] in {"-h", "--help", "--version"}:
        return argv
    return ["analyze", *argv]


def _add_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", nargs="?", default=".",
                        help=(
                            "What to promote: local path, GitHub URL, PDF file, "
                            "or a free-text description (e.g. \"上海火锅店，麻辣鲜香，人均80元\")."
                        ))


def _add_ai_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", help="Override SOURCE2LAUNCH_MODEL.")
    parser.add_argument("--base-url", help="Override SOURCE2LAUNCH_BASE_URL.")
    parser.add_argument("--max-tokens", type=int, help="Override SOURCE2LAUNCH_MAX_TOKENS.")
    parser.add_argument("--temperature", type=float, help="Override SOURCE2LAUNCH_TEMPERATURE.")


def _add_context_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--context", action="append", default=[],
                        help="Extra file, URL, or notes to include as context.")
    parser.add_argument("--prompt-note", action="append", default=[],
                        help="Additional writing instruction injected into the prompt.")
    parser.add_argument("--prompt-preset", action="append", default=[],
                        help=f"Prompt preset name (e.g. autopr, paper, xhs).")


# ---------------------------------------------------------------------------
# Command runners
# ---------------------------------------------------------------------------

def _run_analyze(args: argparse.Namespace) -> int:
    result = analyze_target(args.target)
    if args.json:
        output = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        output = _format_summary(result)
    _write_or_print(output, getattr(args, "output", None))
    return 0


def _run_promote(args: argparse.Namespace) -> int:
    from .interactive import ask_and_merge, has_significant_gaps
    result = analyze_target(args.target)
    # Interactive Q&A: run when --interactive is set OR when info is thin and we're in a TTY
    force_interactive = getattr(args, "interactive", False)
    if force_interactive or (not getattr(args, "json", False) and has_significant_gaps(result)):
        result = ask_and_merge(result, force=force_interactive)
    payload = build_promo_payload(result)
    platform = args.platform
    brief = _build_brief(args)

    if args.ai:
        ai_result = _call_ai(result, platform=platform, brief=brief, args=args)
        _save_session(ai_result, result)   # save for multi-turn refinement
        if args.json:
            output = json.dumps({
                "ai": {"content": ai_result["content"], "model": ai_result["model"]},
                "project": result["project"],
            }, ensure_ascii=False, indent=2)
        else:
            output = _format_ai_output(result, ai_result["content"])
            print(f"\n💡 Tip: run `source2launch refine \"<your feedback>\"` to refine any platform's content.", file=sys.stderr)
    elif args.json:
        output = json.dumps({
            "platform": platform,
            "system": build_promo_system_prompt(),
            "user": build_promo_user_prompt(payload, platform=platform, brief_section=brief),
            "evidenceBrief": build_evidence_brief(payload),
            "payload": payload,
        }, ensure_ascii=False, indent=2)
    else:
        output = "\n".join([
            f"# {result['project']['name']} · Promotion Prompt",
            "",
            "## Evidence Brief",
            "",
            build_evidence_brief(payload),
            "",
            "## Next Step",
            "",
            "Run again with `--ai` after setting SOURCE2LAUNCH_API_KEY or SOURCE2LAUNCH_MODELSCOPE_API_KEY.",
            "",
        ])

    _write_or_print(output, args.output)
    return 0


def _run_optimize(args: argparse.Namespace) -> int:
    from .interactive import ask_and_merge, has_significant_gaps
    result = analyze_target(args.target)
    force_interactive = getattr(args, "interactive", False)
    if force_interactive or has_significant_gaps(result):
        result = ask_and_merge(result, force=force_interactive)
    ai_result = _call_ai(result, platform="all", brief=_build_brief(args), args=args) if args.ai else None
    image_options = {"model": getattr(args, "image_model", None)} if getattr(args, "image", False) else None
    manifest = run_optimize(
        result,
        cwd=Path.cwd(),
        output_dir=args.output_dir,
        ai_content=ai_result.get("content") if ai_result else None,
        ai_model=ai_result.get("model") if ai_result else None,
        generate_images=getattr(args, "image", False),
        image_options=image_options,
    )
    print(f"Source2Launch · launch assets saved to {manifest['outputDir']}")
    print(f"Text files : {len(manifest['generated'])}")
    images = manifest.get("images") or []
    if images:
        print(f"Images     : {len(images)}")
        for img in images:
            print(f"  {Path(img.get('outputPath', '')).name}")
    for f in manifest["generated"]:
        print(f"  {f}")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_ai(result: dict[str, Any], *, platform: str, brief: str, args: argparse.Namespace) -> dict[str, Any]:
    if not has_ai_key():
        raise RuntimeError(
            "No API key found. Set SOURCE2LAUNCH_API_KEY or SOURCE2LAUNCH_MODELSCOPE_API_KEY in .env or environment."
        )
    options = {
        "model": getattr(args, "model", None),
        "base_url": getattr(args, "base_url", None),
        "max_tokens": getattr(args, "max_tokens", None),
        "temperature": getattr(args, "temperature", None),
    }
    # Stage 1: find reference examples
    no_examples = getattr(args, "no_examples", False)
    examples: list[str] | None = None
    if not no_examples:
        from .examples import find_examples
        examples = find_examples(result, platform=platform, ai_options=options) or None

    # Stage 2: generate with examples as few-shot context
    return generate_ai_content(result, platform=platform, brief_section=brief, examples=examples, options=options)


def _build_brief(args: argparse.Namespace) -> str:
    """Combine prompt presets, notes, and context into a single brief section."""
    parts: list[str] = []

    presets = _flatten(getattr(args, "prompt_preset", []))
    if presets:
        expanded = expand_presets(presets)
        if expanded:
            parts += ["## Prompt Presets", "", expanded, ""]

    notes = getattr(args, "prompt_note", [])
    if notes:
        parts += ["## Writing Instructions", ""]
        parts += [f"- {n}" for n in notes]
        parts.append("")

    contexts = getattr(args, "context", [])
    if contexts:
        parts += ["## Additional Context", ""]
        for item in contexts:
            parts.append(_format_context(item))
        parts.append("")

    return "\n".join(parts).strip()


def _flatten(values: list[str]) -> list[str]:
    result: list[str] = []
    for v in values:
        result.extend(p.strip() for p in str(v or "").split(",") if p.strip())
    return result


def _format_context(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return f"### Remote context: {raw}\nUse as a review note; content may not have been fetched."
    path = Path(raw).expanduser()
    if not path.exists():
        return f"### Note: {raw}"
    if path.is_dir():
        return f"### Directory context: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    clipped = text if len(text) <= 4000 else text[:4000].rstrip() + "\n\n...[truncated]"
    return f"### Context: {path.name}\n\n{clipped}"


def _format_summary(result: dict[str, Any]) -> str:
    project = result["project"]
    lines = [
        "Source2Launch · analysis",
        "",
        f"Project  {project.get('name')}",
    ]
    if project.get("description"):
        lines.append(f"Summary  {project['description']}")
    if project.get("installCommand"):
        lines.append(f"Try      {project['installCommand']}")
    if project.get("stars") is not None:
        lines.append(f"Stars    {project['stars']}")
    repo = result.get("repository", {})
    if repo.get("filesScanned"):
        lines.append(f"Files    {repo['filesScanned']} scanned")
    risks = result.get("evidence", {}).get("launchRisks", [])
    if risks:
        lines += ["", "Launch risks"]
        for r in risks:
            lines.append(f"- {r['message']}")
    return "\n".join(lines)


def _format_ai_output(result: dict[str, Any], content: dict[str, Any]) -> str:
    project = result["project"]
    lines = [
        f"# {project.get('name')} · Launch Content",
        "",
        f"**Positioning:** {content.get('positioning') or project.get('description') or ''}",
        "",
    ]
    strategy = content.get("promotionStrategy") or {}
    if strategy.get("coreAngle"):
        lines += ["## Strategy", "", strategy["coreAngle"], ""]

    # Render whatever platforms the AI returned — no hardcoded list
    promotions = content.get("promotions") or {}
    for key, item in promotions.items():
        if isinstance(item, dict) and item.get("markdown"):
            lines += [f"## {key}", "", str(item["markdown"]).strip(), ""]

    if len(lines) <= 4:
        lines.append(json.dumps(content, ensure_ascii=False, indent=2))
    return "\n".join(lines).rstrip()


def _run_refine(args: argparse.Namespace) -> int:
    session_path = Path(args.session)
    if not session_path.exists():
        print(
            f"source2launch: session file not found: {session_path}\n"
            "Run `source2launch promote ... --ai` first to generate content.",
            file=sys.stderr,
        )
        return 1

    previous = json.loads(session_path.read_text(encoding="utf-8"))
    options = {
        "model": getattr(args, "model", None),
        "base_url": getattr(args, "base_url", None),
        "max_tokens": getattr(args, "max_tokens", None),
        "temperature": getattr(args, "temperature", None),
    }

    try:
        ai_result = refine_content(
            previous,
            args.feedback,
            platform=getattr(args, "platform", None),
            options=options,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"source2launch: {exc}", file=sys.stderr)
        return 1

    # Save updated session
    _save_session(ai_result)

    output = _format_ai_output(
        previous.get("result") or {"project": {}},
        ai_result["content"],
    )
    _write_or_print(output, getattr(args, "output", None))
    print("\n✓ Content refined. Run `refine` again to continue.", file=sys.stderr)
    return 0


def _save_session(ai_result: dict[str, Any], result: dict[str, Any] | None = None) -> None:
    """Save generation context for multi-turn refinement."""
    session = {
        "messages": ai_result.get("messages") or [],
        "content": ai_result.get("content") or {},
        "model": ai_result.get("model"),
        "baseUrl": ai_result.get("baseUrl"),
    }
    if result:
        session["result"] = result
    try:
        Path(_SESSION_FILE).write_text(
            json.dumps(session, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass  # Session save failure is non-fatal


def _write_or_print(output: str, path: str | None) -> None:
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(output.rstrip() + "\n", encoding="utf-8")
        print(f"Saved to {p}")
    else:
        print(output.rstrip())


if __name__ == "__main__":
    raise SystemExit(main())
