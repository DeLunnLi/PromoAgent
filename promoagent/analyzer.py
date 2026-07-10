"""Source analysis for PromoAgent - extracts evidence from repos, papers, PDFs, and text."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .logger import logger

__version__ = "0.3.0"

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
_FIRECRAWL_TIMEOUT = 30
_FETCH_TIMEOUT = 10


def analyze_target(input_value: str = ".", *, cwd: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Analyze any source and return promotion-compatible evidence."""
    raw_input = str(input_value or ".").strip()

    if is_remote_url(raw_input):
        return analyze_url_reference(raw_input)

    root = Path(cwd or os.getcwd()).joinpath(raw_input).resolve()
    if root.is_file():
        return analyze_document_path(root)
    if root.is_dir():
        return analyze_repository_path(root)

    if len(raw_input) > 3:
        return analyze_free_text(raw_input)

    raise ValueError(f"Target is not a URL, file, directory, or description: {input_value!r}")


def analyze_free_text(description: str) -> dict[str, Any]:
    """Analyze a plain-text description of anything to promote."""
    name = _extract_name_hint(description)
    return {
        "version": __version__,
        "target": description[:60] + ("…" if len(description) > 60 else ""),
        "source": "text",
        "inputType": "text",
        "project": {
            "name": name,
            "description": description,
            "cta": None,
            "repositoryUrl": None,
            "homepage": None,
            "topics": [],
        },
        "evidence": {
            "opening": description,
            "firstScreen": description,
            "headings": [],
            "keyActions": [],
            "visuals": [],
            "visualUrls": [],
            "launchRisks": [
                {"id": "text-only", "message": "只提供了文字描述。补充图片、网址或更多细节可以显著提升推广质量。"}
            ],
            "proofPoints": [],
            "additionalContext": {},
        },
    }


def _extract_name_hint(description: str) -> str:
    """Heuristically extract a short name from a free-text description."""
    m = re.search(r'[「『"\']([\w\s·\-]+)[」』"\']', description)
    if m:
        return m.group(1).strip()[:40]
    first = re.split(r'[，,。.！!？?、\n]', description.strip())[0].strip()
    return first[:40] if first else description[:20]


def _fetch_with_firecrawl(url: str, api_key: str) -> str:
    """Scrape a URL with the Firecrawl API and return Markdown content."""
    body = json.dumps({"url": url, "formats": ["markdown"], "onlyMainContent": True}).encode("utf-8")
    req = urllib.request.Request(
        FIRECRAWL_SCRAPE_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_FIRECRAWL_TIMEOUT) as resp:
            data = json.loads(resp.read())
        return (data.get("data") or {}).get("markdown") or ""
    except Exception as exc:
        logger.warning("Firecrawl fetch failed", error=str(exc), url=url)
        return ""


def _analyze_from_fetched_markdown(markdown: str, url: str) -> dict[str, Any]:
    """Build an evidence dict from markdown text fetched from a remote URL."""
    title = first_heading(markdown) or url_project_name(url)
    opening = opening_paragraph(markdown) or compact_snippet(strip_markdown(markdown), 300)
    project = {
        "name": title,
        "packageName": None,
        "description": trim_for_summary(opening or f"{title} — remote page."),
        "repositoryUrl": url if "github.com" in url.lower() else None,
        "homepage": url,
        "installCommand": (install_commands(markdown) or [None])[0],
        "topics": [],
    }
    evidence = {
        "readmeOpening": opening,
        "readmeFirstScreen": compact_snippet(markdown[:1800], 1800),
        "headings": readme_headings(markdown)[:16],
        "installCommands": install_commands(markdown)[:5],
        "keyActions": install_commands(markdown)[:3],
        "visuals": visual_references(markdown)[:5],
        "visualUrls": extract_image_urls(markdown)[:3],
        "launchRisks": [],
        "packageScripts": {},
        "examplePaths": [],
        "proofPoints": [],
        "additionalContext": {"sourceUrl": url},
    }
    return {
        "version": __version__,
        "target": url,
        "source": "url",
        "inputType": "url",
        "project": project,
        "evidence": evidence,
        "repository": {"root": None, "filesScanned": 0, "readme": None, "manifest": None, "stars": None, "topics": [], "latestRelease": None},
    }


def analyze_url_reference(url: str, *, _github_api_base: str | None = None, _github_raw_base: str | None = None) -> dict[str, Any]:
    """Fetch a GitHub repository or URL and return a full result dict."""
    if "github.com" in url.lower():
        try:
            return analyze_github_url(url, _github_api_base=_github_api_base, _github_raw_base=_github_raw_base)
        except Exception as exc:
            logger.warning("GitHub fetch failed, falling back", error=str(exc)[:50])

    # Non-GitHub URL: try Firecrawl
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if firecrawl_key:
        markdown = _fetch_with_firecrawl(url, firecrawl_key)
        if markdown and len(markdown) > 100:
            logger.info("Fetched remote URL via Firecrawl", chars=len(markdown))
            return _analyze_from_fetched_markdown(markdown, url)

    # Placeholder fallback
    parsed_name = url_project_name(url)
    return {
        "version": __version__,
        "target": url,
        "source": "url",
        "inputType": "url",
        "project": {
            "name": parsed_name,
            "packageName": None,
            "description": f"{parsed_name} source URL. Provide local README, PDF, or notes for deeper evidence extraction.",
            "repositoryUrl": url if "github.com" in url.lower() else None,
            "homepage": None if "github.com" in url.lower() else url,
            "installCommand": None,
            "topics": [],
        },
        "evidence": {
            "readmeOpening": "",
            "readmeFirstScreen": url,
            "headings": [],
            "installCommands": [],
            "visuals": [],
            "visualUrls": [],
            "launchRisks": [{"id": "remote-url-unfetched", "message": "Remote URL content was not fetched. Set FIRECRAWL_API_KEY for automatic web scraping."}],
            "packageScripts": {},
            "examplePaths": [],
            "documentClips": [{"label": "Source URL", "text": url}],
        },
        "repository": {"root": None, "filesScanned": 0, "readme": None, "manifest": None, "stars": None, "topics": [], "latestRelease": None},
    }


def analyze_document_path(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Analyze a document file (PDF, Markdown, etc.) and return evidence."""
    doc_path = Path(path).resolve()
    raw_text = read_document_text(doc_path)
    title = first_heading(raw_text) or doc_path.stem
    opening = opening_paragraph(raw_text) or compact_snippet(strip_markdown(raw_text), 300)
    input_type = "pdf" if doc_path.suffix.lower() == ".pdf" else "document"

    return {
        "version": __version__,
        "target": str(doc_path),
        "source": "file",
        "inputType": input_type,
        "project": {
            "name": title,
            "packageName": None,
            "description": trim_for_summary(opening or f"{title} source document."),
            "repositoryUrl": None,
            "homepage": None,
            "installCommand": None,
            "topics": [],
        },
        "evidence": {
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
        },
        "repository": {"root": str(doc_path.parent), "filesScanned": 1, "readme": doc_path.name, "manifest": None, "stars": None, "topics": [], "latestRelease": None},
    }


def analyze_repository_path(root: str | os.PathLike[str]) -> dict[str, Any]:
    """Analyze a local repository directory and return evidence."""
    root_path = Path(root).resolve()
    facts = collect_facts(root_path)
    project = project_info(facts, root_path)
    evidence = evidence_info(facts)

    return {
        "version": __version__,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_pyproject_meta(text: str) -> dict[str, Any]:
    """Extract name, description, keywords, and URLs from pyproject.toml."""
    result: dict[str, Any] = {}
    section = re.search(r"\[project\](.*?)(?=^\[|\Z)", text, re.S | re.M)
    if not section:
        return result
    body = section.group(1)

    if m := re.search(r'^name\s*=\s*"([^"]+)"', body, re.M):
        result["name"] = m.group(1)
    if m := re.search(r'^description\s*=\s*"([^"]+)"', body, re.M):
        result["description"] = m.group(1)
    if kw := re.search(r'^keywords\s*=\s*\[(.*?)\]', body, re.S | re.M):
        result["keywords"] = re.findall(r'"([^"]+)"', kw.group(1))

    urls_section = re.search(r"\[project\.urls\](.*?)(?=^\[|\Z)", text, re.S | re.M)
    if urls_section:
        for key, val in re.findall(r'"?(\w[\w\s-]*)"?\s*=\s*"([^"]+)"', urls_section.group(1)):
            if re.search(r"repo|source|code|git", key, re.I):
                result["repositoryUrl"] = val.strip()
            elif re.search(r"home|site|web|doc", key, re.I):
                result["homepage"] = val.strip()

    return result


def collect_facts(root: Path) -> dict[str, Any]:
    """Collect facts about a repository."""
    files = walk(root)
    readme_path = find_root_file(files, re.compile(r"^readme(\.(md|mdx|markdown|rst|txt))?$", re.I))
    package_path = find_root_file(files, re.compile(r"^package\.json$", re.I))
    pyproject_path = find_root_file(files, re.compile(r"^pyproject\.toml$", re.I))
    cargo_path = find_root_file(files, re.compile(r"^Cargo\.toml$"))
    go_mod_path = find_root_file(files, re.compile(r"^go\.mod$"))

    package_json = read_json(root / package_path) if package_path else None
    pyproject_text = read_text(root / pyproject_path) if pyproject_path else ""
    pyproject_meta = parse_pyproject_meta(pyproject_text) if pyproject_text else {}

    topics = unique([
        *(package_json.get("keywords", []) if isinstance(package_json, dict) else []),
        *(pyproject_meta.get("keywords") or []),
    ])

    return {
        "root": root,
        "files": files,
        "readme_path": readme_path,
        "readme_text": read_text(root / readme_path) if readme_path else "",
        "package_path": package_path,
        "package_json": package_json,
        "pyproject_path": pyproject_path,
        "pyproject_text": pyproject_text,
        "pyproject_meta": pyproject_meta,
        "cargo_path": cargo_path,
        "cargo_text": read_text(root / cargo_path) if cargo_path else "",
        "go_mod_path": go_mod_path,
        "go_mod_text": read_text(root / go_mod_path) if go_mod_path else "",
        "manifest_path": package_path or pyproject_path or cargo_path or go_mod_path,
        "tags": git_tags(root),
        "topics": topics,
    }


def project_info(facts: dict[str, Any], root: Path) -> dict[str, Any]:
    """Extract project info from facts."""
    package = facts["package_json"] if isinstance(facts["package_json"], dict) else {}
    pyproject = facts.get("pyproject_meta") or {}
    package_name = str(package.get("name") or pyproject.get("name") or "")
    readme_title = first_heading(facts["readme_text"])
    name = first_present([package_name, readme_title, root.name])

    return {
        "name": name,
        "packageName": package_name or None,
        "description": trim_for_summary(first_present([
            package.get("description"),
            pyproject.get("description"),
            opening_paragraph(facts["readme_text"]),
            f"{name} is an open source project.",
        ])),
        "repositoryUrl": normalize_repository_url(package_repository_url(package)) or pyproject.get("repositoryUrl") or None,
        "homepage": package.get("homepage") or pyproject.get("homepage") or None,
        "installCommand": best_install_command(facts) or None,
        "topics": facts["topics"],
    }


def evidence_info(facts: dict[str, Any]) -> dict[str, Any]:
    """Extract evidence info from facts."""
    readme = facts["readme_text"]
    opening = opening_paragraph(readme)
    cmds = install_commands(readme)[:5]

    return {
        "opening": opening,
        "firstScreen": compact_snippet(readme[:1800], 1800) if readme else "",
        "headings": readme_headings(readme)[:16],
        "keyActions": cmds,
        "visuals": visual_references(readme)[:5],
        "visualUrls": extract_image_urls(readme)[:3],
        "launchRisks": launch_risks(facts),
        "proofPoints": [],
        "additionalContext": {},
        "readmeOpening": opening,
        "installCommands": cmds,
    }


def launch_risks(facts: dict[str, Any]) -> list[dict[str, str]]:
    """Check for launch risks in the repository."""
    readme_plain = strip_code_blocks(facts["readme_text"])
    haystack = "\n".join([
        readme_plain,
        json.dumps(facts["package_json"], ensure_ascii=False) if facts["package_json"] else "",
        facts["pyproject_text"],
        facts["cargo_text"],
        facts["go_mod_text"],
    ])
    risks: list[dict[str, str]] = []

    checks = [
        (bool(re.search(r"\b(TODO|FIXME|TBD|WIP)\b", haystack, re.I)), "placeholder-notes", "Repo text still contains TODO/FIXME/TBD/WIP markers."),
        (bool(re.search(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b", haystack, re.I)), "local-url", "Repo text references local development URLs."),
        (bool(re.search(r"\b(example\.com|your[-_ ]?(project|repo|name)|replace[-_]?(me|with)|lorem ipsum)\b", haystack, re.I)), "template-placeholder", "Repo text still contains template placeholders."),
        (not facts["readme_path"], "missing-readme", "No root README was found."),
        (not install_commands(facts["readme_text"]), "missing-install", "No copy-paste install command was found."),
        (not visual_references(facts["readme_text"]), "missing-visual", "No README visual, GIF, screenshot, or video was found."),
        (len(facts["topics"]) < 3, "few-topics", "Fewer than 3 topic or keyword signals were found."),
        (not has_root_file(facts["files"], re.compile(r"^(license|licence)(\.(md|txt))?$", re.I)) and not package_license(facts["package_json"]), "missing-license", "No obvious license signal was found."),
    ]

    for condition, risk_id, message in checks:
        if condition:
            risks.append({"id": risk_id, "message": message})

    return risks


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def walk(root: Path) -> list[str]:
    """Walk directory and return relative file paths."""
    ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"}
    files: list[str] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".cache")]
        for name in names:
            path = Path(current) / name
            try:
                if path.stat().st_size <= 1_000_000:
                    files.append(path.relative_to(root).as_posix())
            except OSError:
                continue
    return sorted(files)


def find_root_file(files: list[str], pattern: re.Pattern[str]) -> str | None:
    for f in files:
        if "/" not in f and pattern.search(f):
            return f
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
    return extract_pdf_text(path) if path.suffix.lower() == ".pdf" else read_text(path)


# ---------------------------------------------------------------------------
# PDF extraction (3-stage cascade)
# ---------------------------------------------------------------------------

def extract_pdf_text(path: Path) -> str:
    """Extract text from PDF: pypdf → OCR → regex fallback."""
    # Stage 1: pypdf
    text = _extract_pdf_pypdf(path)
    if text:
        logger.info("PDF extracted via pypdf")
        return text

    # Stage 2: OCR
    ocr_mode = os.environ.get("PROMOAGENT_PDF_OCR", "").strip().lower()
    if ocr_mode and ocr_mode != "false":
        text = _extract_pdf_ocr(path, mode=ocr_mode)
        if text:
            return text

    # Stage 3: regex fallback
    logger.info("PDF using regex fallback")
    return _extract_pdf_regex(path)


def _extract_pdf_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
        max_pages = int(os.environ.get("PROMOAGENT_PDF_MAX_PAGES", "60"))
        pages = [p.extract_text() or "" for p in reader.pages[:max_pages] if (p.extract_text() or "").strip()]
        combined = "\n\n".join(pages).strip()
        return compact_snippet(combined, 20_000) if len(combined) >= 100 else ""
    except Exception as exc:
        logger.warning("pypdf extraction failed", error=str(exc))
        return ""


def _extract_pdf_ocr(path: Path, mode: str = "tesseract") -> str:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        logger.warning("OCR skipped - pypdfium2 not installed")
        return ""

    max_pages = int(os.environ.get("PROMOAGENT_PDF_OCR_MAX_PAGES", "12"))
    try:
        doc = pdfium.PdfDocument(str(path))
        images = [page.render(scale=2).to_pil() for i, page in enumerate(doc) if i < max_pages]
    except Exception as exc:
        logger.warning("PDF rendering failed", error=str(exc))
        return ""

    if mode in ("ai", "vision"):
        return _ocr_via_ai_vision(images)
    return _ocr_via_tesseract(images)


def _ocr_via_tesseract(images: list[Any]) -> str:
    try:
        import pytesseract
    except ImportError:
        logger.warning("pytesseract not installed")
        return ""

    lang = os.environ.get("PROMOAGENT_PDF_OCR_LANG", "chi_sim+eng")
    pages = []
    for i, img in enumerate(images):
        try:
            text = pytesseract.image_to_string(img, lang=lang)
            if text.strip():
                pages.append(text.strip())
        except Exception as exc:
            logger.warning("tesseract failed on page", page=i, error=str(exc))

    result = "\n\n".join(pages).strip()
    return compact_snippet(result, 20_000) if result else ""


def _ocr_via_ai_vision(images: list[Any]) -> str:
    import base64
    import io
    from .ai import ai_config, dispatch_chat

    cfg = ai_config()
    if not cfg.get("apiKey") and cfg.get("provider") not in ("ollama",):
        logger.warning("AI OCR skipped - no API key")
        return ""

    pages_text = []
    prompt = "请提取这张 PDF 页面图片中的全部文字内容，保持原有段落结构，不要添加任何解释。"

    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        try:
            provider = cfg.get("provider", "openai")
            if provider == "anthropic":
                messages = [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}, {"type": "text", "text": prompt}]}]
            else:
                messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}, {"type": "text", "text": prompt}]}]

            text = dispatch_chat(messages, cfg)
            if text.strip():
                pages_text.append(text.strip())
        except Exception as exc:
            logger.warning("AI vision OCR failed", error=str(exc))

    result = "\n\n".join(pages_text).strip()
    return compact_snippet(result, 20_000) if result else ""


def _extract_pdf_regex(path: Path) -> str:
    """Legacy regex-based PDF text extraction (zero dependencies)."""
    try:
        data = path.read_bytes()
    except OSError:
        return ""

    text = data.decode("latin-1", errors="ignore")
    chunks = []

    for match in re.finditer(r"\(([^()]|\\[()nrtbf\\]){2,}\)\s*Tj", text):
        chunks.append(unescape_pdf_string(match.group(0).rsplit(")", 1)[0][1:]))

    for array_match in re.finditer(r"\[((?:.|\n)*?)\]\s*TJ", text):
        for item in re.finditer(r"\(([^()]|\\[()nrtbf\\]){2,}\)", array_match.group(1)):
            chunks.append(unescape_pdf_string(item.group(0)[1:-1]))

    fallback = "\n".join(chunks).strip()
    if fallback:
        return compact_snippet(fallback, 20_000)

    printable = re.sub(r"[^A-Za-z0-9一-鿿 .,;:!?()\[\]#/_+\-=]+", " ", text)
    return compact_snippet(printable, 20_000)


def unescape_pdf_string(value: str) -> str:
    replacements = {r"\n": "\n", r"\r": "\r", r"\t": "\t", r"\b": "\b", r"\f": "\f", r"\(": "(", r"\)": ")", r"\\": "\\"}
    out = value
    for raw, replacement in replacements.items():
        out = out.replace(raw, replacement)
    return out


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------

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
    if not text.strip():
        risks.append({"id": "empty-document", "message": "No extractable text was found in the input document."})
    if input_type == "pdf" and len(text.strip()) < 200:
        risks.append({"id": "short-pdf-extraction", "message": "PDF text extraction produced little text; scanned PDFs may need OCR."})
    if not visual_references(text):
        risks.append({"id": "missing-visual-notes", "message": "No explicit figure, screenshot, or visual reference was found."})
    return risks


# ---------------------------------------------------------------------------
# Text processing helpers
# ---------------------------------------------------------------------------

def git_tags(root: Path) -> list[str]:
    try:
        result = subprocess.run(["git", "tag", "--list"], cwd=root, text=True, capture_output=True, timeout=3, check=False)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()][:20]
    except (OSError, subprocess.SubprocessError):
        return []


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
        if clean and not clean.startswith("#") and not (clean.startswith("!") and "](" in clean) and len(clean) >= 20:
            return compact_snippet(clean, 300)
    return ""


def readme_headings(markdown: str) -> list[dict[str, Any]]:
    return [{"level": len(m.group(1)), "text": strip_markdown(m.group(2))} for m in re.finditer(r"^(#{1,4})\s+(.+)$", markdown or "", re.M)]


def install_commands(markdown: str) -> list[str]:
    commands = []
    for block in fenced_blocks(markdown):
        for line in block.splitlines():
            clean = line.strip()
            if re.match(r"^(npm|npx|pnpm|yarn|pipx?|uv|poetry|cargo|go install|docker|git clone|promoagent)\b", clean):
                commands.append(clean)
    for match in re.finditer(r"`([^`]+)`", markdown or ""):
        clean = match.group(1).strip()
        if re.match(r"^(npm|npx|pnpm|yarn|pipx?|uv|poetry|cargo|go install|docker|git clone|promoagent)\b", clean):
            commands.append(clean)
    return unique(commands)


def fenced_blocks(markdown: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"```[\w-]*\n([\s\S]*?)```", markdown or "")]


def visual_references(markdown: str) -> list[str]:
    pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)|<img\b[^>]*>|<video\b[^>]*>|https?://[^\s)]+(?:youtu\.be|youtube\.com|asciinema\.org)[^\s)]*", re.I)
    return [compact_snippet(m.group(0), 180) for m in pattern.finditer(markdown or "")]


def extract_image_urls(markdown: str) -> list[str]:
    urls = []
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", markdown or ""):
        if url := normalize_image_url(m.group(1)):
            urls.append(url)
    for m in re.finditer(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", markdown or "", re.I):
        if url := normalize_image_url(m.group(1)):
            urls.append(url)
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


# ---------------------------------------------------------------------------
# Package helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def is_remote_url(value: str) -> bool:
    return bool(re.match(r"^https?://", str(value or "").strip(), re.I))


def url_project_name(url: str) -> str:
    cleaned = re.sub(r"[?#].*$", "", str(url or "").strip()).rstrip("/")
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) >= 2 and "github.com" in cleaned.lower():
        return re.sub(r"\.git$", "", parts[-1]) or parts[-2]
    return re.sub(r"\.git$", "", parts[-1]) if parts else "remote-source"


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def strip_code_blocks(markdown: str) -> str:
    return re.sub(r"```[\s\S]*?```", "", markdown or "")


def strip_markdown(value: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", value or "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_>#~-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_snippet(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text if len(text) <= limit else f"{text[:limit].rstrip()}..."


def trim_for_summary(value: str) -> str:
    return compact_snippet(value, 240)


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
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _github_headers(env: dict[str, str] | None = None) -> dict[str, str]:
    env = env or os.environ
    token = env.get("GITHUB_TOKEN") or env.get("PROMOAGENT_GITHUB_TOKEN")
    headers: dict[str, str] = {"Accept": "application/vnd.github+json", "User-Agent": "promoagent/0.3"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_text(url: str, headers: dict[str, str] | None = None, timeout: int = _FETCH_TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "promoagent/0.3", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = "utf-8"
        if "charset=" in (resp.headers.get("Content-Type") or ""):
            charset = resp.headers.get("Content-Type", "").split("charset=")[-1].split(";")[0].strip()
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining and remaining.isdigit() and int(remaining) <= 5:
            logger.warning(f"GitHub API rate limit low: {remaining} remaining")
        return resp.read().decode(charset, errors="replace")


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = _FETCH_TIMEOUT) -> dict[str, Any]:
    from . import cache
    if "api.github.com" in url and cache.is_cache_enabled():
        cached = cache.get("github_api", url)
        if cached is not None:
            return cached
        result = json.loads(fetch_text(url, headers=headers, timeout=timeout))
        cache.set("github_api", url, data=result)
        return result
    return json.loads(fetch_text(url, headers=headers, timeout=timeout))


def parse_github_owner_repo(url: str) -> tuple[str, str]:
    cleaned = re.sub(r"[?#].*$", "", url.strip()).rstrip("/")
    cleaned = re.sub(r"\.git$", "", cleaned)
    parts = [p for p in cleaned.split("/") if p]
    try:
        gh_idx = next(i for i, p in enumerate(parts) if "github.com" in p.lower())
        return parts[gh_idx + 1], parts[gh_idx + 2]
    except (StopIteration, IndexError) as exc:
        raise ValueError(f"Cannot parse GitHub owner/repo from URL: {url}") from exc


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def analyze_github_url(url: str, env: dict[str, str] | None = None, *, _github_api_base: str | None = None, _github_raw_base: str | None = None) -> dict[str, Any]:
    """Fetch a GitHub repository via the public API and return a full result dict."""
    owner, repo = parse_github_owner_repo(url)
    headers = _github_headers(env)
    api_base = (_github_api_base or "https://api.github.com").rstrip("/")
    raw_base = (_github_raw_base or "https://raw.githubusercontent.com").rstrip("/")

    # Repository metadata
    try:
        api_data = fetch_json(f"{api_base}/repos/{owner}/{repo}", headers=headers)
    except urllib.error.HTTPError as exc:
        _raise_github_error(exc, url)

    description = str(api_data.get("description") or "")
    topics: list[str] = api_data.get("topics") or []
    stars: int | None = api_data.get("stargazers_count")
    default_branch: str = api_data.get("default_branch") or "main"
    license_name: str | None = (api_data.get("license") or {}).get("spdx_id") or (api_data.get("license") or {}).get("name")
    homepage: str | None = api_data.get("homepage") or None
    repo_url: str = f"https://github.com/{owner}/{repo}"

    # README text
    readme_text = ""
    for branch in unique([default_branch, "main", "master"]):
        try:
            readme_text = fetch_text(f"{raw_base}/{owner}/{repo}/{branch}/README.md", timeout=_FETCH_TIMEOUT)
            break
        except (urllib.error.HTTPError, urllib.error.URLError):
            continue

    # Build result
    name = api_data.get("name") or first_heading(readme_text) or repo
    opening = opening_paragraph(readme_text) or compact_snippet(description, 300)
    install_cmds = install_commands(readme_text)

    return {
        "version": __version__,
        "target": url,
        "source": "github",
        "inputType": "github",
        "project": {
            "name": name,
            "packageName": None,
            "description": trim_for_summary(opening or description or f"{name} is an open source project."),
            "repositoryUrl": repo_url,
            "homepage": homepage,
            "installCommand": min(install_cmds, key=len) if install_cmds else None,
            "topics": topics,
            "stars": stars,
        },
        "evidence": {
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
        },
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
        risks.append({"id": "missing-readme", "message": "No README content could be fetched from GitHub."})
    else:
        plain = strip_code_blocks(readme_text)
        if re.search(r"\b(TODO|FIXME|TBD|WIP)\b", plain, re.I):
            risks.append({"id": "placeholder-notes", "message": "Repo text still contains TODO/FIXME/TBD/WIP markers."})
        if not install_commands(readme_text):
            risks.append({"id": "missing-install", "message": "No copy-paste install command was found in the README."})
        if not visual_references(readme_text):
            risks.append({"id": "missing-visual", "message": "No README visual, GIF, screenshot, or video was found."})
    if len(topics) < 3:
        risks.append({"id": "few-topics", "message": "Fewer than 3 GitHub topic tags were found."})
    if not license_name:
        risks.append({"id": "missing-license", "message": "No license was detected in the repository metadata."})
    return risks


def _raise_github_error(exc: urllib.error.HTTPError, url: str) -> None:
    """Convert GitHub API HTTP error into human-friendly message."""
    import datetime
    body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
    resp_headers = exc.headers

    if exc.code == 403:
        remaining = resp_headers.get("X-RateLimit-Remaining", "?")
        reset_ts = resp_headers.get("X-RateLimit-Reset", "")
        is_rate_limit = remaining == "0" or "rate limit" in body.lower()
        if is_rate_limit:
            reset_hint = ""
            if reset_ts:
                try:
                    reset_dt = datetime.datetime.fromtimestamp(int(reset_ts))
                    reset_hint = f"\n  重置时间：{reset_dt.strftime('%H:%M:%S')}"
                except (ValueError, OSError):
                    pass
            raise RuntimeError(
                f"GitHub API rate limit exceeded (60 requests/hour for unauthenticated).{reset_hint}\n"
                "  Solution: Add GITHUB_TOKEN=ghp_xxx to .env for 5000 requests/hour.\n"
                "  Get Token: https://github.com/settings/tokens"
            ) from exc
        raise RuntimeError(f"GitHub API 403 Forbidden: {url}\n  Response: {body[:200]}") from exc

    if exc.code == 401:
        raise RuntimeError("GitHub API authentication failed (401). Check GITHUB_TOKEN.") from exc
    if exc.code == 404:
        raise RuntimeError(f"GitHub repo not found or private: {url}\n  Set GITHUB_TOKEN for private repos.") from exc
    if exc.code == 429:
        retry_after = resp_headers.get("Retry-After", "")
        raise RuntimeError(f"GitHub API rate limited (429). Retry after {retry_after} seconds.") from exc

    raise RuntimeError(f"GitHub API request failed (HTTP {exc.code}): {body[:300]}") from exc
