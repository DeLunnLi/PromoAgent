from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .ai import build_promo_payload, generate_ai_content, has_ai_key
from .analyzer import analyze_target
from .image import build_promo_image_prompt, generate_image, resolve_image_provider
from .markdown import generate_markdown_document, markdown_type_names
from .optimize import run_optimize
from .publish import build_publish_plan, format_publish_plan
from .skills import build_promotion_skill_plan, promotion_skill_names


def main(argv: list[str] | None = None) -> int:
    argv = normalize_argv(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "markdown":
            return run_markdown(args)
        if args.command == "optimize":
            return run_optimize_cli(args)
        if args.command == "publish":
            return run_publish(args)
        if args.command == "promote":
            return run_promote(args)
        if args.command == "image":
            return run_image(args)
        return run_analyze(args)
    except Exception as error:  # noqa: BLE001 - CLI should report concise failures.
        print(f"source2launch-py: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="source2launch",
        description="Python implementation of Source2Launch core workflows.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser("analyze", help="Analyze a local repository and print JSON or a text summary.")
    add_target(analyze)
    analyze.add_argument("--json", action="store_true", help="Print JSON analysis.")
    analyze.add_argument("-o", "--output", help="Write output to a file.")
    analyze.add_argument("--fail-under", type=int, help="Exit 1 when local score is below this threshold.")
    analyze.add_argument("--intro", "--docs", action="store_true", dest="intro", help="Generate a project introduction Markdown document.")

    markdown = subparsers.add_parser("markdown", help="Generate local Markdown from source evidence.")
    add_target(markdown)
    markdown.add_argument("--markdown-type", default="project", choices=markdown_type_names())
    markdown.add_argument("-o", "--output", help="Write Markdown to a file.")
    add_context_options(markdown)

    optimize = subparsers.add_parser("optimize", help="Generate launch-assets with reviewable local artifacts.")
    add_target(optimize)
    optimize.add_argument("--output", "--optimize-dir", dest="output_dir", default="launch-assets")
    optimize.add_argument("--llm-only", action="store_true", help="Skip local heuristic artifacts.")
    optimize.add_argument("--with-heuristic", action="store_true", help="Include local heuristic artifacts.")
    add_ai_options(optimize)
    add_context_options(optimize)

    promote = subparsers.add_parser("promote", help="Prepare a promotion prompt payload from source evidence.")
    add_target(promote)
    promote.add_argument("--platform", default="all")
    promote.add_argument("--json", action="store_true", help="Print JSON prompt payload.")
    promote.add_argument("-o", "--output", help="Write output to a file.")
    add_ai_options(promote)
    add_context_options(promote)

    image = subparsers.add_parser("image", help="Generate or edit a launch image from source evidence.")
    add_target(image)
    image.add_argument("--platform", default="xhs")
    image.add_argument("--provider", choices=["modelscope", "gradio"], help="Image provider.")
    image.add_argument("--prompt", help="Custom image prompt. Defaults to a prompt built from source evidence.")
    image.add_argument("--style", default="clean", help="Visual style hint for auto-built prompts.")
    image.add_argument("--output", default="promo-image.jpg", help="Image output path.")
    image.add_argument("--image-url", help="Reference image URL for editing.")
    image.add_argument("--image-file", help="Reference image file for editing.")
    image.add_argument("--image-base64", help="Reference image as base64/data URL for editing.")
    image.add_argument("--model", help="Image model id.")
    image.add_argument("--base-url", help="ModelScope base URL, or Gradio URL when --provider gradio.")
    image.add_argument("--api-name", help="Gradio API name, default generate_image.")
    image.add_argument("--negative-prompt", help="Negative prompt.")
    image.add_argument("--width", type=int, help="Override output width.")
    image.add_argument("--height", type=int, help="Override output height.")
    image.add_argument("--seed", type=float, help="Gradio seed.")
    image.add_argument("--no-randomize-seed", action="store_true", help="Disable Gradio random seed.")
    image.add_argument("--no-prompt-extend", action="store_true", help="Disable Gradio prompt extension.")
    image.add_argument("--edit-custom-size", action="store_true", help="Enable Gradio custom edit output size.")
    image.add_argument("--poll-interval-ms", type=int, help="Polling interval.")
    image.add_argument("--timeout-ms", type=int, help="Generation timeout.")
    image.add_argument("--dry-run", action="store_true", help="Print the image plan without calling the API.")
    image.add_argument("--json", action="store_true", help="Print JSON output.")

    publish = subparsers.add_parser("publish", help="Build a human review publish plan from promotion JSON.")
    publish.add_argument("input", help="Path to promotion JSON.")
    publish.add_argument("--platform", default="all")
    publish.add_argument("--publish-mode", default="review", choices=["review", "dry-run", "api", "assist"])
    publish.add_argument("--media", action="append", default=[])
    publish.add_argument("--yes", "-y", action="store_true", help="Mark content as human-approved; still does not execute publishing.")
    publish.add_argument("--json", action="store_true", help="Print JSON plan.")

    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return ["analyze", "."]
    commands = {"analyze", "markdown", "optimize", "publish", "promote", "image"}
    if argv[0] in commands or argv[0] in {"-h", "--help", "--version"}:
        return argv
    return ["analyze", *argv]


def add_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", nargs="?", default=".", help="Local project path.")


def add_ai_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ai", action="store_true", help="Call configured OpenAI-compatible / ModelScope model.")
    parser.add_argument("--model", help="Override SOURCE2LAUNCH_MODEL.")
    parser.add_argument("--base-url", help="Override SOURCE2LAUNCH_BASE_URL.")
    parser.add_argument("--max-tokens", type=int, help="Override SOURCE2LAUNCH_MAX_TOKENS.")
    parser.add_argument("--temperature", type=float, help="Override SOURCE2LAUNCH_TEMPERATURE.")


def add_context_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--skill", action="append", default=[], help=f"Task skill: {', '.join(promotion_skill_names())}.")
    parser.add_argument("--context", action="append", default=[], help="Related source path, URL, or notes file.")
    parser.add_argument("--prompt-note", action="append", default=[], help="Additional writing instruction.")
    parser.add_argument("--prompt-file", action="append", default=[], help="Read additional prompt instructions from a file.")
    parser.add_argument("--prompt-preset", action="append", default=[], help="Prompt preset name for compatibility.")


def run_analyze(args: argparse.Namespace) -> int:
    result = analyze_target(args.target)
    if getattr(args, "intro", False):
        output = generate_markdown_document(result, markdown_type="project")
    elif args.json:
        output = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        output = format_analysis_summary(result)
    write_or_print(output, getattr(args, "output", None))
    fail_under = getattr(args, "fail_under", None)
    if fail_under is not None and isinstance(result.get("score"), int) and result["score"] < fail_under:
        return 1
    return 0


def run_markdown(args: argparse.Namespace) -> int:
    result = analyze_target(args.target)
    output = generate_markdown_document(result, markdown_type=args.markdown_type)
    brief_section = build_brief_section(args)
    if brief_section:
        output = f"{output.rstrip()}\n\n---\n\n{brief_section}\n"
    write_or_print(output, args.output)
    return 0


def run_optimize_cli(args: argparse.Namespace) -> int:
    result = analyze_target(args.target)
    ai_result = maybe_generate_ai(result, args)
    manifest = run_optimize(
        result,
        cwd=Path.cwd(),
        output_dir=args.output_dir,
        llm_only=args.llm_only,
        with_heuristic=args.with_heuristic,
        ai_content=ai_result.get("content") if ai_result else None,
        ai_model=ai_result.get("model") if ai_result else None,
    )
    print("Source2Launch · Python launch assets generated")
    print(f"目录    {manifest['outputDir']}")
    print(f"文件    {len(manifest['generated'])} 个")
    for file in manifest["generated"]:
        print(f"        {file}")
    return 0


def run_promote(args: argparse.Namespace) -> int:
    from .promo_prompts import build_evidence_brief, build_promo_system_prompt, build_promo_user_prompt

    result = analyze_target(args.target)
    payload = build_promo_payload(result)
    platform = resolve_platform(args)
    brief_section = build_brief_section(args)
    ai_result = maybe_generate_ai(result, args)
    if ai_result and args.json:
        output = json.dumps({
            "ai": {
                "content": ai_result["content"],
                "model": ai_result["model"],
                "baseUrl": ai_result["baseUrl"],
            },
            "project": result["project"],
        }, ensure_ascii=False, indent=2)
    elif ai_result:
        output = format_ai_promo_output(result, ai_result["content"])
    elif args.json:
        output = json.dumps({
            "platform": platform,
            "system": build_promo_system_prompt(),
            "user": build_promo_user_prompt(payload, platform=platform, brief_section=brief_section),
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
            "Run again with `--ai` after setting SOURCE2LAUNCH_API_KEY or SOURCE2LAUNCH_MODELSCOPE_API_KEY to generate platform copy.",
            "",
        ])
    write_or_print(output, args.output)
    return 0


def run_image(args: argparse.Namespace) -> int:
    result = analyze_target(args.target)
    prompt = (args.prompt or "").strip() or build_promo_image_prompt(result, platform=args.platform, style=args.style)
    options = image_options_from_args(args)
    provider = resolve_image_provider(options)
    if args.dry_run:
        plan = {
            "provider": provider,
            "platform": args.platform,
            "model": args.model,
            "prompt": prompt,
            "output": args.output,
            "usesReference": bool(args.image_url or args.image_file or args.image_base64),
        }
        output = json.dumps(plan, ensure_ascii=False, indent=2) if args.json else format_image_plan(plan)
        print(output)
        return 0

    generated = generate_image(result, prompt=prompt, platform=args.platform, output_path=args.output, options=options)
    output = json.dumps(generated, ensure_ascii=False, indent=2) if args.json else format_image_result(generated)
    print(output)
    return 0


def image_options_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "provider": args.provider,
        "style": args.style,
        "image_url": args.image_url,
        "image_file": args.image_file,
        "image_base64": args.image_base64,
        "model": args.model,
        "base_url": args.base_url,
        "gradio_url": args.base_url if args.provider == "gradio" else None,
        "api_name": args.api_name,
        "negative_prompt": args.negative_prompt,
        "width": args.width,
        "height": args.height,
        "seed": args.seed,
        "randomize_seed": False if args.no_randomize_seed else None,
        "prompt_extend": False if args.no_prompt_extend else None,
        "edit_custom_size": args.edit_custom_size,
        "poll_interval_ms": args.poll_interval_ms,
        "timeout_ms": args.timeout_ms,
    }


def maybe_generate_ai(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any] | None:
    if not getattr(args, "ai", False):
        return None
    if not has_ai_key():
        raise RuntimeError("Missing AI API key. Set SOURCE2LAUNCH_API_KEY or SOURCE2LAUNCH_MODELSCOPE_API_KEY.")
    return generate_ai_content(result, platform=resolve_platform(args), brief_section=build_brief_section(args), options={
        "model": getattr(args, "model", None),
        "base_url": getattr(args, "base_url", None),
        "max_tokens": getattr(args, "max_tokens", None),
        "temperature": getattr(args, "temperature", None),
    })


def resolve_platform(args: argparse.Namespace) -> str:
    platform = getattr(args, "platform", None) or "all"
    skills = getattr(args, "skill", None) or []
    if skills and platform == "all":
        plan = build_promotion_skill_plan(skills)
        return plan.get("defaultPlatform") or platform
    return platform


def build_brief_section(args: argparse.Namespace) -> str:
    parts: list[str] = []
    skills = getattr(args, "skill", None) or []
    if skills:
        plan = build_promotion_skill_plan(skills)
        parts.extend([
            "## Task Skill Guidance",
            "",
            f"- Skills: {', '.join(skill['name'] for skill in plan['skills'])}",
        ])
        if plan.get("defaultAudience"):
            parts.append(f"- Audience: {plan['defaultAudience']}")
        if plan.get("defaultTone"):
            parts.append(f"- Tone: {plan['defaultTone']}")
        if plan.get("promptPresets"):
            parts.append(f"- Prompt presets: {', '.join(plan['promptPresets'])}")
        if plan.get("reviewFocus"):
            parts.append(f"- Review focus: {', '.join(plan['reviewFocus'])}")
        for note in plan.get("promptNotes", []):
            parts.append(f"- {note}")
        parts.append("")

    presets = flatten_option_values(getattr(args, "prompt_preset", None) or [])
    if presets:
        parts.extend(["## Prompt Presets", "", ", ".join(presets), ""])

    prompt_notes = getattr(args, "prompt_note", None) or []
    if prompt_notes:
        parts.extend(["## Additional Prompt Notes", ""])
        parts.extend(f"- {note}" for note in prompt_notes)
        parts.append("")

    prompt_files = getattr(args, "prompt_file", None) or []
    if prompt_files:
        parts.extend(["## Prompt File Notes", ""])
        for file_path in prompt_files:
            parts.append(format_context_item(file_path, required=True))
        parts.append("")

    contexts = getattr(args, "context", None) or []
    if contexts:
        parts.extend(["## Related Context", ""])
        for item in contexts:
            parts.append(format_context_item(item, required=False))
        parts.append("")
    return "\n".join(part for part in parts if part is not None).strip()


def flatten_option_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        result.extend(part.strip() for part in str(value or "").split(",") if part.strip())
    return result


def format_context_item(value: str, *, required: bool) -> str:
    raw = str(value or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return f"### Remote context: {raw}\nRemote context URL was provided. Use it as a review note unless its content is also available in the analyzed source."
    path = Path(raw).expanduser()
    if not path.exists():
        if required:
            raise RuntimeError(f"Context file not found: {raw}")
        return f"### Context note: {raw}\nPath was not readable locally; keep this as a review note."
    if path.is_dir():
        return f"### Context directory: {path}\nDirectory context was provided. Use the primary analyzed target for source extraction, and treat this as related material."
    text = path.read_text(encoding="utf-8", errors="replace")
    return f"### Context file: {path.name}\n\n{clip_text(text, 4000)}"


def clip_text(value: str, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[:limit].rstrip()}\n\n...[truncated]"


def format_ai_promo_output(result: dict[str, Any], content: dict[str, Any]) -> str:
    project = result["project"]
    lines = [
        f"# {project.get('name')} · AI Promotion",
        "",
        f"**定位：** {content.get('positioning') or project.get('description') or ''}",
        "",
    ]
    strategy = content.get("promotionStrategy") or {}
    if strategy.get("coreAngle"):
        lines.extend(["## Promotion Strategy", "", strategy["coreAngle"], ""])
    promotions = content.get("promotions") or {}
    for label, key in [("小红书", "xiaohongshu"), ("知乎", "zhihu"), ("微信", "wechatMoments"), ("Show HN", "showHn"), ("Product Hunt", "productHunt")]:
        item = promotions.get(key)
        if isinstance(item, dict) and item.get("markdown"):
            lines.extend([f"## {label}", "", str(item["markdown"]).strip(), ""])
    if len(lines) <= 4:
        lines.append(json.dumps(content, ensure_ascii=False, indent=2))
    return "\n".join(lines).rstrip()


def format_image_plan(plan: dict[str, Any]) -> str:
    return "\n".join([
        "Source2Launch · Image plan",
        "",
        f"Provider  {plan['provider']}",
        f"Platform  {plan['platform']}",
        f"Output    {plan['output']}",
        f"Reference {'yes' if plan['usesReference'] else 'no'}",
        "",
        "Prompt",
        plan["prompt"],
    ])


def format_image_result(result: dict[str, Any]) -> str:
    return "\n".join([
        "Source2Launch · Image generated",
        "",
        f"Provider  {result.get('provider')}",
        f"Model     {result.get('model')}",
        f"Output    {result.get('outputPath')}",
        f"Task      {result.get('taskId')}",
    ])


def run_publish(args: argparse.Namespace) -> int:
    input_data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    plan = build_publish_plan(input_data, {
        "platform": args.platform,
        "publishMode": args.publish_mode,
        "media": args.media,
        "yes": args.yes,
    })
    output = json.dumps(plan, ensure_ascii=False, indent=2) if args.json else format_publish_plan(plan)
    print(output)
    return 0


def format_analysis_summary(result: dict[str, Any]) -> str:
    project = result["project"]
    lines = [
        "Source2Launch · Python local analysis",
        "",
        f"Project  {project.get('name')}",
        f"Score    {result.get('score')} ({result.get('grade')})",
    ]
    if project.get("description"):
        lines.append(f"Summary  {project['description']}")
    if project.get("installCommand"):
        lines.append(f"Try      {project['installCommand']}")
    lines.extend(["", "Top checks"])
    for check in result.get("checks", []):
        lines.append(f"- {check['label']}: {check['score']}/{check['max']} · {check['summary']}")
    return "\n".join(lines)


def write_or_print(output: str, output_path: str | None) -> None:
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.rstrip() + "\n", encoding="utf-8")
        print(f"已写入 {path}")
    else:
        print(output.rstrip())


if __name__ == "__main__":
    raise SystemExit(main())
