"""Generate a launch-assets directory from source evidence and optional AI content."""
from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIR = "launch-assets"


def _platform_filename(key: str) -> str:
    """Derive a safe filename from an AI-returned platform key."""
    slug = re.sub(r"[A-Z]", lambda m: f"-{m.group().lower()}", key).lstrip("-")
    slug = re.sub(r"[^a-z0-9-]", "-", slug).strip("-")
    return f"promo-{slug}.md"


def run_optimize(
    result: dict[str, Any],
    *,
    cwd: str | Path | None = None,
    output_dir: str | Path | None = None,
    ai_content: dict[str, Any] | None = None,
    ai_model: str | None = None,
    generate_images: bool = False,
    image_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(cwd or ".").resolve()
    out = Path(output_dir or DEFAULT_OUTPUT_DIR)
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []
    images: list[dict[str, Any]] = []
    project = result.get("project", {})
    evidence = result.get("evidence", {})

    if generate_images:
        from .image import generate_platform_images

        def _write_text() -> None:
            _write_promo_files(out, project, evidence, ai_content, generated)

        def _write_images() -> list[dict[str, Any]]:
            # Pass ai_content as produce_data so card rendering works via the
            # optimize path (not just the CLI draft path).
            produce_data = ai_content if isinstance(ai_content, dict) else None
            return generate_platform_images(result, out, image_options,
                                            produce_data=produce_data,
                                            image_style=image_options.get("image_style", "auto"))

        with ThreadPoolExecutor(max_workers=2) as executor:
            text_future  = executor.submit(_write_text)
            image_future = executor.submit(_write_images)
            text_future.result()
            try:
                images = image_future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"promoagent: image generation failed: {exc}", file=sys.stderr)
    else:
        _write_promo_files(out, project, evidence, ai_content, generated)

    image_names = [Path(img["outputPath"]).name for img in images if img.get("outputPath")]
    write_file(out / "INDEX.md", _index(project, generated, ai_model, image_names), generated)

    return {
        "project": project.get("name"),
        "outputDir": str(out),
        "promoSource": "ai" if ai_content else "unavailable",
        "promoModel": ai_model,
        "generated": generated,
        "images": images,
    }


def _write_promo_files(
    out: Path,
    project: dict[str, Any],
    evidence: dict[str, Any],
    ai_content: dict[str, Any] | None,
    generated: list[str],
) -> None:
    """Write promotional content to files.

    Supports both old format (with 'promotions' key) and new pipeline format.
    """
    write_file(out / "evidence-summary.md", _evidence_summary(project, evidence), generated)

    if not ai_content:
        # No AI content — write a single placeholder
        write_file(
            out / "promo-draft.md",
            f"# {project.get('name', 'Project')} · Draft\n\n"
            "> Run `promoagent draft` to generate platform copy.\n",
            generated,
        )
        return

    # Try new pipeline format first (platform as top-level key)
    platforms_written = False
    for key, item in ai_content.items():
        # Skip non-platform keys
        if key in ("positioning", "strategy", "research", "blueprint"):
            continue

        content = _format_platform_content(item)
        if content:
            filename = _platform_filename(key)
            write_file(out / filename, content, generated)
            platforms_written = True

    # Try old format (nested under 'promotions')
    if not platforms_written:
        promotions = ai_content.get("promotions") or {}
        for key, item in promotions.items():
            content = _format_platform_content(item)
            if content:
                filename = _platform_filename(key)
                write_file(out / filename, content, generated)
                platforms_written = True

    if not platforms_written:
        # No recognizable content format
        write_file(
            out / "promo-draft.md",
            f"# {project.get('name', 'Project')} · Draft\n\n"
            "> No content generated.\n",
            generated,
        )


def write_file(path: Path, content: str, manifest: list[str]) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    manifest.append(path.name)


def _format_platform_content(item: Any) -> str:
    """Render a platform's produce output into a full markdown file.

    Surfaces title / hashtags / thread / publish_notes alongside the markdown
    body — previously these fields were generated but discarded, wasting the
    model's output (notably Twitter threads and per-platform publish advice).
    """
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""

    parts: list[str] = []
    title = str(item.get("title") or "").strip()
    if title:
        parts.append(f"# {title}")

    # Twitter/X threads: render as a numbered thread block. Fall back to the
    # markdown body when the thread is absent OR non-empty but all-blank
    # (models occasionally emit thread: [""] — don't drop the body for that).
    thread = [t for t in (item.get("thread") or []) if t]
    if thread:
        parts.append("\n".join(f"{i+1}/ {t}" for i, t in enumerate(thread)))
    else:
        body = str(item.get("markdown") or "").strip()
        if body:
            parts.append(body)

    hashtags = item.get("hashtags") or []
    if isinstance(hashtags, list) and hashtags:
        parts.append(" ".join(h for h in hashtags if h))

    # publish_notes is an internal advisory, NOT content to publish.
    # Write it to a separate .notes file instead of polluting the promo .md
    # (which gets loaded by fill/publish and sent to public platforms).

    return "\n\n".join(p for p in parts if p).strip()



def _evidence_summary(project: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = [
        f"# {project.get('name', 'Project')} · Evidence Summary",
        "",
        "> Auto-generated by Source2Launch. Review before using in promotional content.",
        "",
    ]
    for label, value in [
        ("Description", project.get("description")),
        ("CTA", project.get("cta") or project.get("installCommand")),
        ("Repository", project.get("repositoryUrl")),
        ("Homepage", project.get("homepage")),
        ("Stars", project.get("stars")),
        ("Topics", ", ".join(project.get("topics") or [])),
    ]:
        if value:
            lines.append(f"**{label}:** {value}")
    lines.append("")

    opening = evidence.get("opening") or evidence.get("readmeOpening", "")
    if opening:
        lines += ["## Content Overview", "", opening, ""]

    ctx = evidence.get("additionalContext") or {}
    if ctx:
        lines += ["## Additional Context", ""]
        for k, v in ctx.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    risks = evidence.get("launchRisks") or []
    if risks:
        lines += ["## Notes", ""]
        for r in risks:
            msg = r.get("message") if isinstance(r, dict) else str(r)
            lines.append(f"- {msg}")
        lines.append("")

    return "\n".join(lines)


def _index(
    project: dict[str, Any],
    generated: list[str],
    model: str | None,
    image_names: list[str] | None = None,
) -> str:
    name = project.get("name", "Project")
    model_str = f" · {model}" if model else ""
    lines = [
        f"# {name} · Launch Assets",
        "",
        f"Generated by Source2Launch{model_str}",
        "",
        "## Files",
        "",
    ]
    for f in generated:
        if f != "INDEX.md":
            lines.append(f"- [{f}]({f})")
    if image_names:
        lines += ["", "## Images", ""]
        for img in image_names:
            lines.append(f"- [images/{img}](images/{img})")
    lines += [
        "",
        "## Before Publishing",
        "",
        "- Verify all facts against the original source.",
        "- Remove unsupported claims.",
        "- Adapt tone to match your account voice.",
        "- Review each draft before publishing.",
        "",
    ]
    return "\n".join(lines)
