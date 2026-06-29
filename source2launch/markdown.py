from __future__ import annotations

from typing import Any

MARKDOWN_TYPES = {"project", "readme", "launch", "promo", "all"}


def markdown_type_names() -> list[str]:
    return sorted(MARKDOWN_TYPES)


def normalize_markdown_type(value: str | None) -> str:
    normalized = (value or "project").strip().lower()
    aliases = {
        "doc": "project",
        "docs": "project",
        "brief": "project",
        "project-brief": "project",
        "readme-draft": "readme",
        "readme-md": "readme",
        "launch-kit": "launch",
        "release": "launch",
        "promotion": "promo",
        "social": "promo",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in MARKDOWN_TYPES:
        raise ValueError(f"Unknown markdown type: {value}. Available types: {', '.join(markdown_type_names())}")
    return normalized


def generate_markdown_document(source: dict[str, Any], *, markdown_type: str = "project", type: str | None = None) -> str:
    doc_type = normalize_markdown_type(type or markdown_type)
    if doc_type == "all":
        return "\n\n---\n\n".join([
            project_brief_markdown(source),
            readme_draft_markdown(source),
            launch_markdown(source),
            promo_markdown(source),
        ])
    if doc_type == "readme":
        return readme_draft_markdown(source)
    if doc_type == "launch":
        return launch_markdown(source)
    if doc_type == "promo":
        return promo_markdown(source)
    return project_brief_markdown(source)


def project_brief_markdown(source: dict[str, Any]) -> str:
    project = source.get("project", {})
    evidence = source.get("evidence", {})
    repository = source.get("repository", {})
    lines: list[str] = [f"# {project.get('name') or 'Project'} Brief", ""]
    if project.get("description"):
        lines.extend([f"> {project['description']}", ""])
    lines.append("## Source Snapshot")
    append_fact(lines, "Target", source.get("target"))
    append_fact(lines, "Input type", source.get("inputType"))
    append_fact(lines, "Repository", project.get("repositoryUrl"))
    append_fact(lines, "Homepage", project.get("homepage"))
    append_fact(lines, "Topics", ", ".join(project.get("topics") or []) or None)
    append_fact(lines, "Install command", project.get("installCommand"))
    append_fact(lines, "README", repository.get("readme"))
    append_fact(lines, "Manifest", repository.get("manifest"))
    append_fact(lines, "Files scanned", repository.get("filesScanned"))
    lines.extend(["", "## What It Does", "", evidence.get("readmeOpening") or project.get("description") or "TODO: summarize the project from source evidence.", ""])
    lines.append("## Source Evidence")
    append_list(lines, "Install commands", evidence.get("installCommands"))
    append_list(lines, "Visual references", evidence.get("visuals"))
    append_clip_list(lines, evidence.get("documentClips"))
    append_list(lines, "Example paths", evidence.get("examplePaths"))
    append_list(lines, "File highlights", (evidence.get("fileHighlights") or [])[:16])
    append_headings(lines, evidence.get("headings"))
    lines.extend([
        "",
        "## Suggested Positioning",
        "",
        f"- One-liner: {project.get('description') or evidence.get('readmeOpening') or 'TODO: write one sentence.'}",
        f"- Best first proof: {best_proof(source)}",
        "- Reader fit: developers, maintainers, researchers, or technical readers who need this workflow.",
        "",
        "## Markdown Assets To Create Next",
        "",
        "- README opening rewrite",
        "- Quickstart section",
        "- Demo or screenshot caption",
        "- Product Hunt / Show HN launch note",
        "- Xiaohongshu or WeChat visual outline",
        "",
        "## Review Checklist",
        "",
        "- [ ] Claims are grounded in README, docs, paper, demo, or code evidence.",
        "- [ ] Install command or try path works.",
        "- [ ] Screenshots or figures are real source evidence.",
        "- [ ] No fake metrics, stars, users, rankings, or testimonials.",
        "- [ ] Caveats are clear where source evidence is incomplete.",
    ])
    return trim_lines(lines)


def readme_draft_markdown(source: dict[str, Any]) -> str:
    project = source.get("project", {})
    evidence = source.get("evidence", {})
    command = project.get("installCommand") or first_value(evidence.get("installCommands"))
    lines = [
        f"# {project.get('name') or 'Project'}",
        "",
        project.get("description") or evidence.get("readmeOpening") or "TODO: one-sentence project description.",
        "",
        "## Why This Exists",
        "",
        "TODO: explain the problem this project solves and who it is for.",
        "",
        "## Quickstart",
        "",
        "```sh",
        command or "# TODO: add install or run command",
        "```",
        "",
        "## What It Does",
        "",
    ]
    append_bullets(lines, [
        evidence.get("readmeOpening") or project.get("description"),
        f"Includes examples such as {first_value(evidence.get('examplePaths'))}." if first_value(evidence.get("examplePaths")) else None,
        f"Has visual proof in {first_value(evidence.get('visuals'))}." if first_value(evidence.get("visuals")) else None,
    ])
    lines.extend(["", "## Example", "", "```sh", command or "# TODO: add usage example", "```", "", "## Evidence From The Repository"])
    append_clip_list(lines, evidence.get("documentClips"))
    append_list(lines, "Examples", evidence.get("examplePaths"))
    append_list(lines, "Relevant files", (evidence.get("fileHighlights") or [])[:12])
    lines.extend(["", "## Limitations", "", "- TODO: name incomplete features, missing examples, benchmark limits, or setup assumptions.", "", "## License", "", "TODO: add license details."])
    return trim_lines(lines)


def launch_markdown(source: dict[str, Any]) -> str:
    project = source.get("project", {})
    evidence = source.get("evidence", {})
    command = project.get("installCommand") or first_value(evidence.get("installCommands")) or "TODO: command"
    description = project.get("description") or evidence.get("readmeOpening") or "TODO: short tagline."
    lines = [
        f"# Launch Kit: {project.get('name') or 'Project'}",
        "",
        "## Tagline",
        "",
        description,
        "",
        "## Proof To Show First",
        "",
    ]
    append_bullets(lines, [
        f"Quickstart command: `{command}`" if command != "TODO: command" else None,
        f"Visual: {first_value(evidence.get('visuals'))}" if first_value(evidence.get("visuals")) else None,
    ])
    lines.extend([
        "",
        "## X / Twitter Draft",
        "",
        f"{description}\n\nTry path: {command}",
        "",
        "## Product Hunt Draft",
        "",
        f"**Tagline:** {description}",
        "",
        "**Description:**",
        "",
        f"{project.get('name') or 'This project'} helps technical users inspect the source, understand the workflow, and try it from repository evidence.",
        "",
        "**Maker comment:**",
        "",
        f"Built around source-grounded evidence. The first thing to try is `{command}`.",
        "",
        "## Show HN Draft",
        "",
        f"Show HN: {project.get('name') or 'Project'} - {description}",
        "",
        f"{project.get('name') or 'This project'}: {ensure_sentence(description)}\n\nTry it with:\n\n```sh\n{command}\n```\n\nKnown limitation: TODO.",
        "",
        "## Launch Checklist",
        "",
        "- [ ] README first screen explains what it does.",
        "- [ ] Install or demo command works.",
        "- [ ] Screenshot/GIF shows the real project.",
        "- [ ] Limitations are stated plainly.",
        "- [ ] Links point to repo, docs, demo, paper, or release notes.",
    ])
    return trim_lines(lines)


def promo_markdown(source: dict[str, Any]) -> str:
    project = source.get("project", {})
    evidence = source.get("evidence", {})
    lines = [
        f"# Promotion Markdown: {project.get('name') or 'Project'}",
        "",
        "## Core Angle",
        "",
        project.get("description") or evidence.get("readmeOpening") or "TODO: core angle.",
        "",
        "## Channel Notes",
        "",
        "### Zhihu",
        "",
        "- Conclusion first.",
        "- Explain background, workflow, evidence, limitation, and who should read it.",
        "",
        "### Xiaohongshu",
        "",
        "- Cover: TODO: short cover text.",
        "- Card 1: problem.",
        "- Card 2: workflow or method.",
        "- Card 3: source proof.",
        "- Card 4: how to try it.",
        "- Card 5: caveat.",
        "",
        "### WeChat",
        "",
        "- Article title: TODO.",
        "- Moments copy: TODO.",
        "",
        "## Visual Plan",
        "",
        f"- Primary proof: {best_proof(source)}",
        "- Generated cover should not invent metrics, UI, logos, or paper results.",
    ]
    return trim_lines(lines)


def append_fact(lines: list[str], label: str, value: Any) -> None:
    if value is not None and value != "":
        lines.append(f"- {label}: {value}")


def append_list(lines: list[str], title: str, values: Any) -> None:
    if not values:
        return
    lines.extend(["", f"### {title}", ""])
    for value in values:
        lines.append(f"- {value}")


def append_clip_list(lines: list[str], clips: Any) -> None:
    if not clips:
        return
    lines.extend(["", "### Document clips", ""])
    for clip in clips[:6]:
        if isinstance(clip, dict):
            label = clip.get("path") or clip.get("source") or "source"
            text = clip.get("text") or clip.get("content") or ""
            lines.append(f"- **{label}:** {text}")
        else:
            lines.append(f"- {clip}")


def append_headings(lines: list[str], headings: Any) -> None:
    if not headings:
        return
    lines.extend(["", "### README headings", ""])
    for heading in headings[:12]:
        if isinstance(heading, dict):
            lines.append(f"- h{heading.get('level', 2)} {heading.get('text', '')}")
        else:
            lines.append(f"- {heading}")


def append_bullets(lines: list[str], values: list[str | None]) -> None:
    written = False
    for value in values:
        if value:
            lines.append(f"- {value}")
            written = True
    if not written:
        lines.append("- TODO: add source-grounded details.")


def best_proof(source: dict[str, Any]) -> str:
    evidence = source.get("evidence", {})
    return (
        first_value(evidence.get("visuals"))
        or first_value(evidence.get("installCommands"))
        or first_value(evidence.get("examplePaths"))
        or evidence.get("readmeOpening")
        or "TODO: add screenshot, figure, command, or source clip."
    )


def first_value(values: Any) -> str:
    if isinstance(values, list) and values:
        return str(values[0])
    return ""


def ensure_sentence(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return text if text.endswith((".", "!", "?", "。", "！", "？")) else f"{text}."


def trim_lines(lines: list[str]) -> str:
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(str(item) for item in lines) + "\n"
