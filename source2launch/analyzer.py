from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

VERSION = "0.2.0"


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


def analyze_url_reference(
    url: str,
    *,
    _github_api_base: str | None = None,
    _github_raw_base: str | None = None,
) -> dict[str, Any]:
    if "github.com" in url.lower():
        try:
            return analyze_github_url(url, _github_api_base=_github_api_base, _github_raw_base=_github_raw_base)
        except Exception:  # noqa: BLE001 — network/parse failure → fall through to placeholder
            pass
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
    return {
        "version": VERSION,
        "target": str(doc_path),
        "source": "file",
        "inputType": input_type,
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
    }


def analyze_repository_path(root: str | os.PathLike[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    facts = collect_facts(root_path)
    project = project_info(facts, root_path)
    evidence = evidence_info(facts)

    return {
        "version": VERSION,
        "target": str(root_path),
        "source": "local",
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


# ---------------------------------------------------------------------------
# Network helpers (zero external dependencies — stdlib urllib only)
# ---------------------------------------------------------------------------

_FETCH_TIMEOUT = 10  # seconds


def _github_headers(env: dict[str, str] | None = None) -> dict[str, str]:
    """Return headers for GitHub API requests, including auth token if available."""
    env = env or os.environ
    token = env.get("GITHUB_TOKEN") or env.get("SOURCE2LAUNCH_GITHUB_TOKEN")
    headers: dict[str, str] = {"Accept": "application/vnd.github+json", "User-Agent": "source2launch/0.2"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_text(url: str, headers: dict[str, str] | None = None, timeout: int = _FETCH_TIMEOUT) -> str:
    """Fetch a URL and return the response body as text. Raises on HTTP error."""
    req = urllib.request.Request(url, headers={"User-Agent": "source2launch/0.2", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = "utf-8"
        content_type = resp.headers.get("Content-Type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        return resp.read().decode(charset, errors="replace")


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = _FETCH_TIMEOUT) -> dict[str, Any]:
    """Fetch a URL and parse the response body as JSON."""
    return json.loads(fetch_text(url, headers=headers, timeout=timeout))


def parse_github_owner_repo(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL. Raises ValueError if not parseable."""
    cleaned = re.sub(r"[?#].*$", "", url.strip()).rstrip("/")
    # Remove .git suffix
    cleaned = re.sub(r"\.git$", "", cleaned)
    parts = [p for p in cleaned.split("/") if p]
    try:
        gh_idx = next(i for i, p in enumerate(parts) if "github.com" in p.lower())
        owner = parts[gh_idx + 1]
        repo = parts[gh_idx + 2]
    except (StopIteration, IndexError) as exc:
        raise ValueError(f"Cannot parse GitHub owner/repo from URL: {url}") from exc
    return owner, repo


def analyze_github_url(
    url: str,
    env: dict[str, str] | None = None,
    *,
    _github_api_base: str | None = None,
    _github_raw_base: str | None = None,
) -> dict[str, Any]:
    """Fetch a GitHub repository via the public API and return a full result dict."""
    owner, repo = parse_github_owner_repo(url)
    headers = _github_headers(env)
    api_base = (_github_api_base or "https://api.github.com").rstrip("/")
    raw_base = (_github_raw_base or "https://raw.githubusercontent.com").rstrip("/")

    # 1. Repository metadata
    api_data = fetch_json(f"{api_base}/repos/{owner}/{repo}", headers=headers)
    description = str(api_data.get("description") or "")
    topics: list[str] = api_data.get("topics") or []
    stars: int | None = api_data.get("stargazers_count")
    default_branch: str = api_data.get("default_branch") or "main"
    license_name: str | None = (api_data.get("license") or {}).get("spdx_id") or (api_data.get("license") or {}).get("name")
    homepage: str | None = api_data.get("homepage") or None
    repo_url: str = f"https://github.com/{owner}/{repo}"

    # 2. README text — try default branch, then main/master
    readme_text = ""
    for branch in unique([default_branch, "main", "master"]):
        try:
            raw_url = f"{raw_base}/{owner}/{repo}/{branch}/README.md"
            readme_text = fetch_text(raw_url, timeout=_FETCH_TIMEOUT)
            break
        except (urllib.error.HTTPError, urllib.error.URLError):
            continue

    # 3. Build result using existing heuristic helpers
    # Prefer the authoritative API name over the README heading (strip_markdown removes hyphens)
    name = api_data.get("name") or first_heading(readme_text) or repo
    opening = opening_paragraph(readme_text) or compact_snippet(description, 300)
    install_cmds = install_commands(readme_text)

    project = {
        "name": name,
        "packageName": None,
        "description": trim_for_summary(opening or description or f"{name} is an open source project."),
        "repositoryUrl": repo_url,
        "homepage": homepage,
        "installCommand": min(install_cmds, key=len) if install_cmds else None,
        "topics": topics,
        "stars": stars,
    }

    evidence: dict[str, Any] = {
        "readmeOpening": opening,
        "readmeFirstScreen": compact_snippet(readme_text[:1800], 1800) if readme_text else "",
        "headings": readme_headings(readme_text)[:16],
        "installCommands": install_cmds[:5],
        "visuals": visual_references(readme_text)[:5],
        "visualUrls": extract_image_urls(readme_text)[:3],
        "launchRisks": _github_launch_risks(readme_text, topics, license_name),
        "packageScripts": {},
        "examplePaths": [],
        "documentClips": [],
    }

    return {
        "version": VERSION,
        "target": url,
        "source": "github",
        "inputType": "github",
        "project": project,
        "evidence": evidence,
        "repository": {
            "root": None,
            "filesScanned": 0,
            "readme": "README.md" if readme_text else None,
            "manifest": None,
            "stars": stars,
            "topics": topics,
            "latestRelease": None,
        },
    }


def _github_launch_risks(readme_text: str, topics: list[str], license_name: str | None) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if not readme_text:
        add_risk(risks, True, "missing-readme", "No README content could be fetched from GitHub.")
    else:
        plain = strip_code_blocks(readme_text)
        add_risk(risks, bool(re.search(r"\b(TODO|FIXME|TBD|WIP)\b", plain, re.I)), "placeholder-notes", "Repo text still contains TODO/FIXME/TBD/WIP markers.")
        add_risk(risks, not install_commands(readme_text), "missing-install", "No copy-paste install command was found in the README.")
        add_risk(risks, not visual_references(readme_text), "missing-visual", "No README visual, GIF, screenshot, or video was found.")
    add_risk(risks, len(topics) < 3, "few-topics", "Fewer than 3 GitHub topic tags were found.")
    add_risk(risks, not license_name, "missing-license", "No license was detected in the repository metadata.")
    return risks




