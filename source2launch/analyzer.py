from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

VERSION = "0.2.0"


CHECK_DEFS = {
    "readme-pitch": {"label": "README pitch", "max": 18},
    "visual-demo": {"label": "Visual proof", "max": 12},
    "install-command": {"label": "Install command", "max": 12},
    "demo-usage": {"label": "Demo / usage", "max": 12},
    "topics": {"label": "Topics / keywords", "max": 10},
    "examples": {"label": "Examples", "max": 10},
    "first-screen": {"label": "First screen", "max": 12},
    "package-release": {"label": "Package / release", "max": 14},
}


def analyze_target(input_value: str = ".", *, cwd: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Analyze a local repository and return Source2Launch-compatible evidence."""

    raw_input = str(input_value or ".").strip()
    if is_remote_url(raw_input):
        return analyze_url_reference(raw_input)

    root = Path(cwd or os.getcwd()).joinpath(raw_input).resolve()
    if root.is_file():
        return analyze_document_path(root)
    if not root.is_dir():
        raise ValueError(f"Target is not a local directory or readable file: {input_value}")
    return analyze_repository_path(root)


def analyze_url_reference(url: str) -> dict[str, Any]:
    parsed_name = url_project_name(url)
    project = {
        "name": parsed_name,
        "packageName": None,
        "description": f"{parsed_name} source URL. Provide local README, PDF, or notes for deeper evidence extraction.",
        "repositoryUrl": url if "github.com" in url.lower() else None,
        "homepage": None if "github.com" in url.lower() else url,
        "installCommand": None,
        "topics": [],
    }
    evidence = {
        "readmeOpening": "",
        "readmeFirstScreen": url,
        "headings": [],
        "installCommands": [],
        "visuals": [],
        "visualUrls": [],
        "launchRisks": [
            {"id": "remote-url-unfetched", "message": "Remote URL content was not fetched by the Python local analyzer. Add --context notes or pass a local clone/PDF for stronger evidence."}
        ],
        "packageScripts": {},
        "examplePaths": [],
        "documentClips": [{"label": "Source URL", "text": url}],
    }
    return {
        "version": VERSION,
        "target": url,
        "source": "url",
        "inputType": "url",
        "score": 0,
        "grade": "N/A",
        "project": project,
        "evidence": evidence,
        "repository": {
            "root": None,
            "filesScanned": 0,
            "readme": None,
            "manifest": None,
            "stars": None,
            "topics": [],
            "latestRelease": None,
        },
        "checks": [],
        "topFixes": [
            finding("medium", "Only a remote URL was provided.", "Pass a local repository, README, PDF, or --context file so Source2Launch can ground the copy in source evidence.")
        ],
    }


def analyze_document_path(path: str | os.PathLike[str]) -> dict[str, Any]:
    doc_path = Path(path).resolve()
    raw_text = read_document_text(doc_path)
    title = first_heading(raw_text) or doc_path.stem
    opening = opening_paragraph(raw_text) or compact_snippet(strip_markdown(raw_text), 300)
    input_type = "pdf" if doc_path.suffix.lower() == ".pdf" else "document"
    project = {
        "name": title,
        "packageName": None,
        "description": trim_for_summary(opening or f"{title} source document."),
        "repositoryUrl": None,
        "homepage": None,
        "installCommand": None,
        "topics": [],
    }
    evidence = {
        "readmeOpening": opening,
        "readmeFirstScreen": compact_snippet(raw_text[:1800], 1800),
        "headings": readme_headings(raw_text)[:16],
        "installCommands": install_commands(raw_text)[:5],
        "visuals": visual_references(raw_text)[:5],
        "visualUrls": extract_image_urls(raw_text)[:3],
        "launchRisks": document_launch_risks(raw_text, input_type),
        "packageScripts": {},
        "examplePaths": [],
        "documentClips": document_clips(doc_path, raw_text),
    }
    top_fixes = []
    if not opening:
        top_fixes.append(finding("medium", "Document opening is hard to summarize.", "Add an abstract, README-style overview, or notes with problem/method/evidence."))
    if not evidence["visuals"] and input_type == "pdf":
        top_fixes.append(finding("medium", "No visual references were extracted from the document text.", "Provide screenshots or figure notes with --context in a later AI run."))

    return {
        "version": VERSION,
        "target": str(doc_path),
        "source": "file",
        "inputType": input_type,
        "score": 0,
        "grade": "N/A",
        "project": project,
        "evidence": evidence,
        "repository": {
            "root": str(doc_path.parent),
            "filesScanned": 1,
            "readme": doc_path.name,
            "manifest": None,
            "stars": None,
            "topics": [],
            "latestRelease": None,
        },
        "checks": [],
        "topFixes": top_fixes,
    }


def analyze_repository_path(root: str | os.PathLike[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    facts = collect_facts(root_path)
    project = project_info(facts, root_path)
    evidence = evidence_info(facts)
    checks = [
        check_readme_pitch(facts),
        check_visual_demo(facts),
        check_install_command(facts),
        check_demo_usage(facts),
        check_topics(facts),
        check_examples(facts),
        check_first_screen(facts),
        check_package_release(facts),
    ]
    score = sum(item["score"] for item in checks)
    top_fixes = sorted(
        (
            {**finding, "check": check["id"], "impact": check["max"] - check["score"]}
            for check in checks
            for finding in check["findings"]
        ),
        key=lambda item: ({"high": 0, "medium": 1, "low": 2}.get(item["severity"], 3), -item["impact"]),
    )[:6]
    for item in top_fixes:
        item.pop("impact", None)

    return {
        "version": VERSION,
        "target": str(root_path),
        "source": "local",
        "score": score,
        "grade": grade(score),
        "project": project,
        "evidence": evidence,
        "repository": {
            "root": str(root_path),
            "filesScanned": len(facts["files"]),
            "readme": facts["readme_path"],
            "manifest": facts["manifest_path"],
            "stars": None,
            "topics": facts["topics"],
            "latestRelease": latest_release(facts["tags"]),
        },
        "checks": checks,
        "topFixes": top_fixes,
    }


def collect_facts(root: Path) -> dict[str, Any]:
    files = walk(root)
    readme_path = find_root_file(files, re.compile(r"^readme(\.(md|mdx|markdown|rst|txt))?$", re.I))
    package_path = find_root_file(files, re.compile(r"^package\.json$", re.I))
    pyproject_path = find_root_file(files, re.compile(r"^pyproject\.toml$", re.I))
    cargo_path = find_root_file(files, re.compile(r"^Cargo\.toml$"))
    go_mod_path = find_root_file(files, re.compile(r"^go\.mod$"))
    package_json = read_json(root / package_path) if package_path else None
    topics = unique([
        *(package_json.get("keywords", []) if isinstance(package_json, dict) and isinstance(package_json.get("keywords"), list) else []),
    ])
    return {
        "root": root,
        "files": files,
        "readme_path": readme_path,
        "readme_text": read_text(root / readme_path) if readme_path else "",
        "package_path": package_path,
        "package_json": package_json,
        "pyproject_path": pyproject_path,
        "pyproject_text": read_text(root / pyproject_path) if pyproject_path else "",
        "cargo_path": cargo_path,
        "cargo_text": read_text(root / cargo_path) if cargo_path else "",
        "go_mod_path": go_mod_path,
        "go_mod_text": read_text(root / go_mod_path) if go_mod_path else "",
        "manifest_path": package_path or pyproject_path or cargo_path or go_mod_path,
        "tags": git_tags(root),
        "topics": topics,
    }


def project_info(facts: dict[str, Any], root: Path) -> dict[str, Any]:
    package = facts["package_json"] if isinstance(facts["package_json"], dict) else {}
    package_name = str(package.get("name") or "")
    readme_title = first_heading(facts["readme_text"])
    name = first_present([package_name, readme_title, root.name])
    description = trim_for_summary(first_present([
        package.get("description"),
        opening_paragraph(facts["readme_text"]),
        f"{name} is an open source project.",
    ]))
    return {
        "name": name,
        "packageName": package_name or None,
        "description": description,
        "repositoryUrl": normalize_repository_url(package_repository_url(package)) or None,
        "homepage": package.get("homepage") or None,
        "installCommand": best_install_command(facts) or None,
        "topics": facts["topics"],
    }


def evidence_info(facts: dict[str, Any]) -> dict[str, Any]:
    readme = facts["readme_text"]
    return {
        "readmeOpening": opening_paragraph(readme),
        "readmeFirstScreen": compact_snippet(readme[:1800], 1800) if readme else "",
        "headings": readme_headings(readme)[:16],
        "installCommands": install_commands(readme)[:5],
        "visuals": visual_references(readme)[:5],
        "visualUrls": extract_image_urls(readme)[:3],
        "launchRisks": launch_risks(facts),
        "packageScripts": package_scripts(facts["package_json"]),
        "examplePaths": [
            file for file in facts["files"]
            if re.search(r"^(examples?|samples?|demos?|playground|templates)/", normalize_path(file), re.I)
        ][:12],
    }


def launch_risks(facts: dict[str, Any]) -> list[dict[str, str]]:
    readme_plain = strip_code_blocks(facts["readme_text"])
    haystack = "\n".join([
        readme_plain,
        json.dumps(facts["package_json"], ensure_ascii=False) if facts["package_json"] else "",
        facts["pyproject_text"],
        facts["cargo_text"],
        facts["go_mod_text"],
    ])
    risks: list[dict[str, str]] = []
    add_risk(risks, bool(re.search(r"\b(TODO|FIXME|TBD|WIP)\b", haystack, re.I)), "placeholder-notes", "Repo text still contains TODO/FIXME/TBD/WIP markers.")
    add_risk(risks, bool(re.search(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b", haystack, re.I)), "local-url", "Repo text references local development URLs.")
    add_risk(risks, bool(re.search(r"\b(example\.com|your[-_ ]?(project|repo|name)|replace[-_ ]?(me|with)|lorem ipsum)\b", haystack, re.I)), "template-placeholder", "Repo text still contains template placeholders.")
    add_risk(risks, not facts["readme_path"], "missing-readme", "No root README was found.")
    add_risk(risks, not install_commands(facts["readme_text"]), "missing-install", "No copy-paste install command was found.")
    add_risk(risks, not visual_references(facts["readme_text"]), "missing-visual", "No README visual, GIF, screenshot, or video was found.")
    add_risk(risks, len(facts["topics"]) < 3, "few-topics", "Fewer than 3 topic or keyword signals were found.")
    add_risk(risks, not has_root_file(facts["files"], re.compile(r"^(license|licence)(\.(md|txt))?$", re.I)) and not package_license(facts["package_json"]), "missing-license", "No obvious license signal was found.")
    return risks


def add_risk(risks: list[dict[str, str]], condition: bool, risk_id: str, message: str) -> None:
    if condition:
        risks.append({"id": risk_id, "message": message})


def create_check(check_id: str) -> dict[str, Any]:
    definition = CHECK_DEFS[check_id]
    return {
        "id": check_id,
        "label": definition["label"],
        "score": 0,
        "max": definition["max"],
        "summary": "",
        "findings": [],
    }


def finding(severity: str, message: str, fix: str) -> dict[str, str]:
    return {"severity": severity, "message": message, "fix": fix}


def check_readme_pitch(facts: dict[str, Any]) -> dict[str, Any]:
    check = create_check("readme-pitch")
    readme = facts["readme_text"]
    if not readme:
        check["summary"] = "No root README found"
        check["findings"].append(finding("high", "Add a root README with a plain-language pitch.", "Start with a H1 and one sentence that says who it is for, what it does, and why it is different."))
        return check
    title = first_heading(readme)
    opening = opening_paragraph(readme)
    words = word_count(opening)
    score = 0
    if title:
        score += 3
    else:
        check["findings"].append(finding("medium", "The README does not start with a clear H1 title.", "Add a product-style H1 before badges or setup details."))
    if opening:
        score += 4
    else:
        check["findings"].append(finding("high", "The README opening does not contain a usable one-sentence pitch.", "Put a concise value proposition directly below the title."))
    if 8 <= words <= 35:
        score += 4
    if re.search(r"\b(for|to|helps?|lets?|without|with|build|scan|generate|deploy|monitor|test|debug|analy[sz]e|convert|ship|automate)\b", opening, re.I):
        score += 5
    if not check["findings"] and score < check["max"]:
        score += 2
    check["score"] = min(check["max"], score)
    check["summary"] = "README communicates a launch pitch" if check["score"] >= 14 else "README pitch needs sharper source-grounded positioning"
    return check


def check_visual_demo(facts: dict[str, Any]) -> dict[str, Any]:
    check = create_check("visual-demo")
    refs = visual_references(facts["readme_text"])
    if refs:
        check["score"] = 12 if len(refs) >= 2 else 8
        check["summary"] = "README has visual proof"
    else:
        check["summary"] = "No visual proof found"
        check["findings"].append(finding("medium", "Add a screenshot, GIF, demo video, or terminal output image.", "Show the real output a visitor should expect."))
    return check


def check_install_command(facts: dict[str, Any]) -> dict[str, Any]:
    check = create_check("install-command")
    commands = install_commands(facts["readme_text"])
    if not commands:
        check["summary"] = "No copy-paste install command found"
        check["findings"].append(finding("high", "Add one copy-paste install or run command.", "Put the shortest command in the README first screen."))
        return check
    shortest = min(commands, key=len)
    check["score"] = 12 if len(shortest) <= 60 else 10 if len(shortest) <= 90 else 7 if len(shortest) <= 130 else 4
    check["summary"] = "Install command is visible" if check["score"] >= 10 else "Install command is present but long"
    return check


def check_demo_usage(facts: dict[str, Any]) -> dict[str, Any]:
    check = create_check("demo-usage")
    readme = facts["readme_text"]
    score = 0
    if re.search(r"^##+\s+(usage|quickstart|example|demo|get started)", readme, re.I | re.M):
        score += 4
    if fenced_blocks(readme):
        score += 4
    if re.search(r"\b(demo|example|quickstart|usage)\b", readme, re.I):
        score += 2
    if any(re.search(r"^(examples?|demos?|samples?)/", normalize_path(file), re.I) for file in facts["files"]):
        score += 2
    check["score"] = min(check["max"], score)
    check["summary"] = "Usage path is visible" if score >= 9 else "Usage path needs more proof"
    if score < 8:
        check["findings"].append(finding("medium", "Add a short usage example.", "Show the exact command and expected output."))
    return check


def check_topics(facts: dict[str, Any]) -> dict[str, Any]:
    check = create_check("topics")
    count = len(facts["topics"])
    check["score"] = 10 if count >= 5 else 8 if count >= 3 else 5 if count >= 1 else 0
    check["summary"] = f"{count} topic or keyword signals"
    if count < 3:
        check["findings"].append(finding("low", "Add more searchable topics or package keywords.", "Use terms a target reader would search for."))
    return check


def check_examples(facts: dict[str, Any]) -> dict[str, Any]:
    check = create_check("examples")
    example_files = [file for file in facts["files"] if re.search(r"^(examples?|demos?|samples?)/", normalize_path(file), re.I)]
    blocks = len(fenced_blocks(facts["readme_text"]))
    score = 0
    if example_files:
        score += 5
    if len(example_files) >= 2:
        score += 2
    score += 3 if blocks >= 2 else 1 if blocks == 1 else 0
    check["score"] = min(check["max"], score)
    check["summary"] = "Examples are easy to inspect" if check["score"] >= 8 else "Examples need more concrete proof"
    if check["score"] < 8:
        check["findings"].append(finding("medium", "Add examples or a demo path.", "Include a minimal example and expected output."))
    return check


def check_first_screen(facts: dict[str, Any]) -> dict[str, Any]:
    check = create_check("first-screen")
    first = facts["readme_text"][:1800]
    score = 0
    if first_heading(first):
        score += 2
    if word_count(opening_paragraph(first)) >= 8:
        score += 3
    if visual_references(first):
        score += 3
    if install_commands(first):
        score += 3
    if not re.search(r"(\[!\[|shields\.io|badgen\.net)", first, re.I):
        score += 1
    check["score"] = min(check["max"], score)
    check["summary"] = "First screen has core launch signals" if check["score"] >= 9 else "First screen is missing launch signals"
    if check["score"] < 9:
        check["findings"].append(finding("medium", "Improve README first screen.", "Put pitch, proof, and try command before deep details."))
    return check


def check_package_release(facts: dict[str, Any]) -> dict[str, Any]:
    check = create_check("package-release")
    package = facts["package_json"] if isinstance(facts["package_json"], dict) else {}
    score = 0
    if has_root_file(facts["files"], re.compile(r"^(license|licence)(\.(md|txt))?$", re.I)) or package.get("license"):
        score += 3
    if package.get("name") or facts["pyproject_path"] or facts["cargo_path"] or facts["go_mod_path"]:
        score += 5
    if package.get("bin") or package.get("main") or package.get("exports"):
        score += 3
    if facts["tags"]:
        score += 3
    check["score"] = min(check["max"], score)
    check["summary"] = "Package identity is visible" if check["score"] >= 10 else "Package identity or release metadata is incomplete"
    if check["score"] < 10:
        check["findings"].append(finding("low", "Complete package identity and release metadata.", "Add license, entrypoint, repository link, and release notes where applicable."))
    return check


def walk(root: Path) -> list[str]:
    ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"}
    files: list[str] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [item for item in dirs if item not in ignored and not item.startswith(".cache")]
        for name in names:
            path = Path(current) / name
            try:
                if path.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue
            files.append(path.relative_to(root).as_posix())
    return sorted(files)


def find_root_file(files: list[str], pattern: re.Pattern[str]) -> str | None:
    for file in files:
        if "/" not in file and pattern.search(file):
            return file
    return None


def has_root_file(files: list[str], pattern: re.Pattern[str]) -> bool:
    return find_root_file(files, pattern) is not None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(read_text(path))
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def read_document_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path)
    return read_text(path)


def extract_pdf_text(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    text = data.decode("latin-1", errors="ignore")
    chunks: list[str] = []
    for match in re.finditer(r"\(([^()]|\\[()nrtbf\\]){2,}\)\s*Tj", text):
        chunks.append(unescape_pdf_string(match.group(0).rsplit(")", 1)[0][1:]))
    for array_match in re.finditer(r"\[((?:.|\n)*?)\]\s*TJ", text):
        for item in re.finditer(r"\(([^()]|\\[()nrtbf\\]){2,}\)", array_match.group(1)):
            chunks.append(unescape_pdf_string(item.group(0)[1:-1]))
    fallback = "\n".join(chunks).strip()
    if fallback:
        return compact_snippet(fallback, 20_000)
    printable = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff .,;:!?()\[\]#/_+\-=]+", " ", text)
    return compact_snippet(printable, 20_000)


def unescape_pdf_string(value: str) -> str:
    replacements = {
        r"\n": "\n",
        r"\r": "\r",
        r"\t": "\t",
        r"\b": "\b",
        r"\f": "\f",
        r"\(": "(",
        r"\)": ")",
        r"\\": "\\",
    }
    out = value
    for raw, replacement in replacements.items():
        out = out.replace(raw, replacement)
    return out


def document_clips(path: Path, text: str) -> list[dict[str, str]]:
    paragraphs = [
        compact_snippet(strip_markdown(item), 500)
        for item in re.split(r"\n\s*\n", text or "")
        if len(strip_markdown(item)) >= 40
    ][:6]
    if not paragraphs and text:
        paragraphs = [compact_snippet(strip_markdown(text), 500)]
    return [{"path": path.name, "text": item} for item in paragraphs]


def document_launch_risks(text: str, input_type: str) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    add_risk(risks, not text.strip(), "empty-document", "No extractable text was found in the input document.")
    add_risk(risks, input_type == "pdf" and len(text.strip()) < 200, "short-pdf-extraction", "PDF text extraction produced little text; scanned PDFs may need OCR or user-provided notes.")
    add_risk(risks, not visual_references(text), "missing-visual-notes", "No explicit figure, screenshot, or visual reference was found in extracted text.")
    return risks


def git_tags(root: Path) -> list[str]:
    try:
        result = subprocess.run(["git", "tag", "--list"], cwd=root, text=True, capture_output=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()][:20]


def latest_release(tags: list[str]) -> str | None:
    return tags[-1] if tags else None


def first_heading(markdown: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown or "", re.M)
    return strip_markdown(match.group(1)).strip() if match else ""


def opening_paragraph(markdown: str) -> str:
    text = strip_code_blocks(markdown or "")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for block in re.split(r"\n\s*\n", text):
        clean = strip_markdown(block).strip()
        if not clean or clean.startswith("#") or re.fullmatch(r"\[?!?\[?.*", clean):
            continue
        if len(clean) >= 20:
            return compact_snippet(clean, 300)
    return ""


def readme_headings(markdown: str) -> list[dict[str, Any]]:
    result = []
    for match in re.finditer(r"^(#{1,4})\s+(.+)$", markdown or "", re.M):
        result.append({"level": len(match.group(1)), "text": strip_markdown(match.group(2))})
    return result


def install_commands(markdown: str) -> list[str]:
    commands: list[str] = []
    for block in fenced_blocks(markdown):
        for line in block.splitlines():
            clean = line.strip()
            if re.match(r"^(npm|npx|pnpm|yarn|pipx?|uv|poetry|cargo|go install|docker|git clone|source2launch)\b", clean):
                commands.append(clean)
    for match in re.finditer(r"`([^`]+)`", markdown or ""):
        clean = match.group(1).strip()
        if re.match(r"^(npm|npx|pnpm|yarn|pipx?|uv|poetry|cargo|go install|docker|git clone|source2launch)\b", clean):
            commands.append(clean)
    return unique(commands)


def fenced_blocks(markdown: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"```[\w-]*\n([\s\S]*?)```", markdown or "")]


def visual_references(markdown: str) -> list[str]:
    pattern = re.compile(r"!\[([^\]]*)]\(([^)]+)\)|<img\b[^>]*>|<video\b[^>]*>|https?://[^\s)]+(?:youtu\.be|youtube\.com|asciinema\.org)[^\s)]*", re.I)
    return [compact_snippet(match.group(0), 180) for match in pattern.finditer(markdown or "")]


def extract_image_urls(markdown: str) -> list[str]:
    urls: list[str] = []
    for match in re.finditer(r"!\[[^\]]*]\(([^)]+)\)", markdown or ""):
        candidate = normalize_image_url(match.group(1))
        if candidate:
            urls.append(candidate)
    for match in re.finditer(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", markdown or "", re.I):
        candidate = normalize_image_url(match.group(1))
        if candidate:
            urls.append(candidate)
    return unique(urls)


def normalize_image_url(value: str) -> str | None:
    raw = str(value or "").strip().split()[0]
    if not re.match(r"^https?://", raw, re.I):
        return None
    if re.search(r"\.(png|jpe?g|webp|gif|svg)(?:[?#]|$)", raw, re.I):
        return raw
    if re.search(r"githubusercontent\.com|modelscope\.|aliyuncs\.com|shields\.io|img\.shields", raw, re.I):
        return raw
    return None


def package_scripts(package_json: Any) -> dict[str, str]:
    if not isinstance(package_json, dict) or not isinstance(package_json.get("scripts"), dict):
        return {}
    return dict(list(package_json["scripts"].items())[:8])


def package_license(package_json: Any) -> str | None:
    return package_json.get("license") if isinstance(package_json, dict) else None


def best_install_command(facts: dict[str, Any]) -> str:
    commands = install_commands(facts["readme_text"])
    if commands:
        return min(commands, key=len)
    package = facts["package_json"] if isinstance(facts["package_json"], dict) else {}
    if package.get("name") and package.get("bin"):
        return f"npx {package['name']}"
    return ""


def package_repository_url(package_json: dict[str, Any]) -> str:
    repo = package_json.get("repository")
    if isinstance(repo, str):
        return repo
    if isinstance(repo, dict):
        return str(repo.get("url") or "")
    return ""


def normalize_repository_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("git@github.com:"):
        raw = raw.replace("git@github.com:", "https://github.com/")
    return re.sub(r"\.git$", "", re.sub(r"^git\+", "", raw))


def is_remote_url(value: str) -> bool:
    return bool(re.match(r"^https?://", str(value or "").strip(), re.I))


def url_project_name(url: str) -> str:
    cleaned = re.sub(r"[?#].*$", "", str(url or "").strip()).rstrip("/")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) >= 2 and "github.com" in cleaned.lower():
        return re.sub(r"\.git$", "", parts[-1]) or parts[-2]
    if parts:
        return re.sub(r"\.git$", "", parts[-1]) or "remote-source"
    return "remote-source"


def strip_code_blocks(markdown: str) -> str:
    return re.sub(r"```[\s\S]*?```", "", markdown or "")


def strip_markdown(value: str) -> str:
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", value or "")
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_>#~-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_snippet(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text if len(text) <= limit else f"{text[:limit].rstrip()}..."


def trim_for_summary(value: str) -> str:
    return compact_snippet(value, 240)


def word_count(value: str) -> int:
    return len(re.findall(r"[\w\u4e00-\u9fff]+", value or ""))


def normalize_path(value: str) -> str:
    return value.replace("\\", "/")


def first_present(values: list[Any]) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"
