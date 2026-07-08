"""MCP server exposing the PromoAgent draft pipeline to AI tools.

Tools (all prefixed ``s2l_``):

- ``s2l_analyze(target)``               — analyze a source, return evidence + source_id
- ``s2l_list_platforms()``             — supported platforms
- ``s2l_research(target, search, ...)`` — run the research stage, return facts/strategy/gaps
- ``s2l_blueprint(source_id, ...)``    — generate the editable blueprint
- ``s2l_edit_blueprint(source_id, edits)`` — apply edits to a blueprint
- ``s2l_produce(source_id, platforms, ...)`` — generate platform-native content
- ``s2l_draft(target, ...)``           — one-shot full pipeline

State is shared across tool calls via ``source_id``: the analysis ``result`` is
cached in :class:`PipelineState` under key ``"result"``, so follow-up tools can
recover it without re-analyzing. ``pipeline.py`` is left untouched — all
adaptation lives in this module.

The server speaks MCP over stdio (the default FastMCP transport), which is what
Claude Desktop / Cursor expect. It never reads stdin directly and never calls
CLI-only UI helpers (Prompt.ask / progress_spinner / fill_platform).
"""
from __future__ import annotations

import sys
from dataclasses import asdict
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised when mcp extra not installed
    FastMCP = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False

from .analyzer import analyze_target
from .platforms import list_platforms
from .pipeline import (
    PipelineState,
    _source_id,
    stage_research,
    stage_blueprint,
    stage_produce,
    edit_blueprint,
    preview_blueprint,
    run_pipeline,
)
from .image import build_image_prompt, image_brief

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_options(model: str = "", base_url: str = "", api_key: str = "") -> dict[str, Any]:
    """Assemble AI options, dropping empty values so defaults apply."""
    options: dict[str, Any] = {}
    if model:
        options["model"] = model
    if base_url:
        options["base_url"] = base_url
    if api_key:
        options["api_key"] = api_key
    return options


def _ok(**payload: Any) -> dict[str, Any]:
    payload["ok"] = True
    return payload


# Cap error messages surfaced to MCP clients. Exception strings may carry
# upstream API response bodies (prompt fragments, account hints); keep enough
# to debug, never the full text.
_ERROR_MSG_LIMIT = 300


def _err(message: str, **extra: Any) -> dict[str, Any]:
    text = " ".join(str(message or "").split())
    if len(text) > _ERROR_MSG_LIMIT:
        text = text[:_ERROR_MSG_LIMIT] + "…"
    result: dict[str, Any] = {"ok": False, "error": text}
    result.update(extra)
    return result


def _store_result(result: dict[str, Any]) -> tuple[str, PipelineState]:
    """Compute source_id and cache the analysis result in a fresh PipelineState."""
    source_id = _source_id(result)
    state = PipelineState(source_id)
    state.set("result", result)
    return source_id, state


def _load_state(source_id: str) -> PipelineState:
    """Reconstruct a PipelineState from a previously cached source_id."""
    return PipelineState(source_id)


def _require_result(state: PipelineState) -> dict[str, Any] | None:
    """Return the cached analysis result, or None if missing."""
    return state.get("result")


# ---------------------------------------------------------------------------
# Tool implementations (pure functions, directly testable)
# ---------------------------------------------------------------------------

def _impl_analyze(target: str) -> dict[str, Any]:
    try:
        result = analyze_target(target)
    except Exception as exc:  # noqa: BLE001 — never crash the server
        return _err(f"analyze failed: {exc}")
    source_id, _state = _store_result(result)
    project = result.get("project", {})
    evidence = result.get("evidence", {})
    return _ok(
        source_id=source_id,
        source=result.get("source", ""),
        inputType=result.get("inputType", ""),
        project={
            "name": project.get("name", ""),
            "description": project.get("description", ""),
            "topics": project.get("topics", []),
            "installCommand": project.get("installCommand", ""),
        },
        evidence={
            "launchRisks": evidence.get("launchRisks", []),
            "visuals": bool(evidence.get("visuals")),
        },
    )


def _impl_list_platforms() -> dict[str, Any]:
    # Wrap in _ok(platforms=[...]) so the shape matches every other tool and
    # FastMCP serializes it as a single TextContent (a bare list[dict] would
    # emit one content item per element, which AI tools can't reassemble).
    return _ok(platforms=[asdict(spec) for spec in list_platforms()])


def _impl_research(target: str, search: bool = True,
                   model: str = "", base_url: str = "", api_key: str = "") -> dict[str, Any]:
    try:
        result = analyze_target(target)
    except Exception as exc:  # noqa: BLE001
        return _err(f"analyze failed: {exc}")
    source_id, state = _store_result(result)
    options = _build_options(model, base_url, api_key)
    try:
        out = stage_research(result, state, options, search=search)
    except Exception as exc:  # noqa: BLE001
        return _err(f"research failed: {exc}", source_id=source_id)
    data = out.get("data", {}) or {}
    facts = data.get("facts", {}) or {}
    strategy = data.get("strategy", {}) or {}
    return _ok(
        source_id=source_id,
        facts=facts,
        strategy=strategy,
    )


def _impl_blueprint(source_id: str, model: str = "", base_url: str = "",
                    api_key: str = "") -> dict[str, Any]:
    state = _load_state(source_id)
    result = _require_result(state)
    if result is None:
        return _err("No analysis result for this source_id. Run s2l_analyze or s2l_research first.",
                    source_id=source_id)
    research = state.get("research")
    if research is None:
        return _err("No research stage cached. Run s2l_research first.",
                    source_id=source_id)
    options = _build_options(model, base_url, api_key)
    try:
        out = stage_blueprint(research, state, result, options)
    except Exception as exc:  # noqa: BLE001
        return _err(f"blueprint failed: {exc}", source_id=source_id)
    data = out.get("data", {}) or {}
    return _ok(
        source_id=source_id,
        positioning=data.get("positioning", {}),
        elements=data.get("elements", []),
        structure=data.get("structure", {}),
        metrics=data.get("metrics", {}),
    )


def _impl_edit_blueprint(source_id: str, edits: dict[str, Any]) -> dict[str, Any]:
    state = _load_state(source_id)
    blueprint = state.get("blueprint")
    if blueprint is None:
        return _err("No blueprint cached. Run s2l_blueprint first.",
                    source_id=source_id)
    try:
        updated = edit_blueprint(blueprint, edits)
    except Exception as exc:  # noqa: BLE001
        return _err(f"edit failed: {exc}", source_id=source_id)
    state.set("blueprint", updated)
    try:
        preview = preview_blueprint(updated)
    except Exception:  # noqa: BLE001 — preview is best-effort
        preview = ""
    data = updated.get("data", {}) or {}
    return _ok(
        source_id=source_id,
        preview=preview,
        elements=data.get("elements", []),
    )


def _impl_produce(source_id: str, platforms: list[str] | None = None,
                  model: str = "", base_url: str = "", api_key: str = "",
                  quality: str = "fast") -> dict[str, Any]:
    state = _load_state(source_id)
    blueprint = state.get("blueprint")
    research = state.get("research")
    if blueprint is None or research is None:
        return _err("Missing blueprint or research. Run s2l_research then s2l_blueprint first.",
                    source_id=source_id)
    options = _build_options(model, base_url, api_key)
    options["quality_mode"] = quality
    # result is needed so polished-mode backflow can re-run research when the
    # critic flags fact insufficiency. It was cached by s2l_analyze/research.
    result = state.get("result")
    try:
        out = stage_produce(blueprint, research, state, options,
                            platforms=platforms, parallel=True, result=result)
    except Exception as exc:  # noqa: BLE001
        return _err(f"produce failed: {exc}", source_id=source_id)
    return _ok(
        source_id=source_id,
        produce=out.get("data", {}) or {},
        platforms=out.get("platforms", []),
    )


def _impl_draft(target: str, platforms: list[str] | None = None,
                search: bool = True, model: str = "", base_url: str = "",
                api_key: str = "", quality: str = "fast") -> dict[str, Any]:
    try:
        result = analyze_target(target)
    except Exception as exc:  # noqa: BLE001
        return _err(f"analyze failed: {exc}")
    source_id, state = _store_result(result)
    options = _build_options(model, base_url, api_key)
    options["quality_mode"] = quality
    try:
        outputs = run_pipeline(result, options, state=state, search=search)
    except Exception as exc:  # noqa: BLE001
        return _err(f"draft pipeline failed: {exc}", source_id=source_id)
    research_data = (outputs.get("research", {}) or {}).get("data", {}) or {}
    produce_data = (outputs.get("produce", {}) or {}).get("data", {}) or {}
    return _ok(
        source_id=source_id,
        produce=produce_data,
        recommended_platforms=research_data.get("strategy", {}).get("recommended_platforms", []),
    )


# ---------------------------------------------------------------------------
# Image prompt tools (text-only — no file system, no image API calls)
# ---------------------------------------------------------------------------

def _brief_options(title: str, subtitle: str, cta: str, badges: str) -> dict[str, Any]:
    """Collect non-empty ad-copy fields into an image_brief options dict."""
    options: dict[str, Any] = {}
    if title:
        options["title"] = title
    if subtitle:
        options["subtitle"] = subtitle
    if cta:
        options["cta"] = cta
    if badges:
        options["badges"] = badges
    return options


def _impl_image_brief(source_id: str, title: str = "", subtitle: str = "",
                      cta: str = "", badges: str = "") -> dict[str, Any]:
    """Resolve the ad-copy brief (title/subtitle/cta/badges) for image overlay."""
    state = _load_state(source_id)
    result = _require_result(state)
    if result is None:
        return _err("No analysis result for this source_id. Run s2l_analyze first.",
                    source_id=source_id)
    try:
        # env={} isolates from the host environment so behavior is deterministic.
        brief = image_brief(result, options=_brief_options(title, subtitle, cta, badges), env={})
    except Exception as exc:  # noqa: BLE001
        return _err(f"image_brief failed: {exc}", source_id=source_id)
    return _ok(source_id=source_id, brief=brief)


def _impl_build_image_prompt(source_id: str, platform: str = "xhs",
                             skill: str = "auto", model: str = "",
                             title: str = "", subtitle: str = "",
                             cta: str = "", badges: str = "") -> dict[str, Any]:
    """Build a text image-generation prompt for the given platform.

    Returns the prompt string plus the resolved brief. The prompt can be fed to
    any external image model (DALL·E, Qwen-Image, etc.) — PromoAgent does not
    call the image API itself here. Pass ``model`` matching the target image
    model so the prompt uses the right language (Chinese for Qwen, English for
    DALL·E).
    """
    state = _load_state(source_id)
    result = _require_result(state)
    if result is None:
        return _err("No analysis result for this source_id. Run s2l_analyze first.",
                    source_id=source_id)
    options = _brief_options(title, subtitle, cta, badges)
    try:
        brief = image_brief(result, options=options, env={}) if options else None
        prompt = build_image_prompt(
            result, platform=platform, skill=skill or None,
            brief=brief, model=model,
        )
    except Exception as exc:  # noqa: BLE001
        return _err(f"build_image_prompt failed: {exc}", source_id=source_id)
    return _ok(
        source_id=source_id,
        platform=platform,
        prompt=prompt,
        brief=brief or {},
    )


# ---------------------------------------------------------------------------
# FastMCP registration
# ---------------------------------------------------------------------------

def _register(mcp: "FastMCP") -> None:
    @mcp.tool()
    def s2l_analyze(target: str) -> dict:
        """Analyze a source (GitHub URL, local path, file, or free text) and return
        extracted evidence plus a ``source_id`` handle for follow-up tools."""
        return _impl_analyze(target)

    @mcp.tool()
    def s2l_list_platforms() -> dict:
        """List all supported platforms with their format, style, and API support flags."""
        return _impl_list_platforms()

    @mcp.tool()
    def s2l_research(target: str, search: bool = True,
                     model: str = "", base_url: str = "", api_key: str = "") -> dict:
        """Run the research stage: extract facts, strategy, and information gaps (gaps)
        from a source. Returns a ``source_id`` for use with s2l_blueprint.
        Set ``search=False`` to skip reference-ad search."""
        return _impl_research(target, search=search, model=model, base_url=base_url, api_key=api_key)

    @mcp.tool()
    def s2l_blueprint(source_id: str, model: str = "",
                      base_url: str = "", api_key: str = "") -> dict:
        """Generate an editable blueprint (structured content elements + variants)
        from a prior research stage. Requires the ``source_id`` from s2l_research."""
        return _impl_blueprint(source_id, model=model, base_url=base_url, api_key=api_key)

    @mcp.tool()
    def s2l_edit_blueprint(source_id: str, edits: dict) -> dict:
        """Apply edits to a blueprint. ``edits`` supports:
        {element_id: "new content"}, {"_selectVariant": {id: idx}},
        {"_reorder": [ids]}, {"_addElement": {...}}, {"_removeElement": id},
        {"_setStructure": "name"}. Returns a markdown preview."""
        return _impl_edit_blueprint(source_id, edits)

    @mcp.tool()
    def s2l_produce(source_id: str, platforms: list[str] | None = None,
                    model: str = "", base_url: str = "", api_key: str = "",
                    quality: str = "fast") -> dict:
        """Generate platform-native content (markdown, hashtags, threads) from a
        blueprint. ``quality`` controls enrichment: fast (facts only, 1 call),
        balanced (+playbook+few-shot), polished (+critic rewrite, 2-3 calls)."""
        return _impl_produce(source_id, platforms=platforms, model=model,
                             base_url=base_url, api_key=api_key, quality=quality)

    @mcp.tool()
    def s2l_draft(target: str, platforms: list[str] | None = None,
                  search: bool = True, model: str = "",
                  base_url: str = "", api_key: str = "",
                  quality: str = "fast") -> dict:
        """One-shot full pipeline (research → blueprint → produce). Returns
        platform content directly. ``quality``: fast/balanced/polished (see
        s2l_produce). Use the staged tools for interactive editing."""
        return _impl_draft(target, platforms=platforms, search=search,
                           model=model, base_url=base_url, api_key=api_key,
                           quality=quality)

    @mcp.tool()
    def s2l_image_brief(source_id: str, title: str = "", subtitle: str = "",
                        cta: str = "", badges: str = "") -> dict:
        """Resolve the ad-copy brief (title/subtitle/cta/badges) used for image
        text overlay. Requires the ``source_id`` from s2l_analyze."""
        return _impl_image_brief(source_id, title=title, subtitle=subtitle,
                                 cta=cta, badges=badges)

    @mcp.tool()
    def s2l_build_image_prompt(source_id: str, platform: str = "xhs",
                               skill: str = "auto", model: str = "",
                               title: str = "", subtitle: str = "",
                               cta: str = "", badges: str = "") -> dict:
        """Build a text image-generation prompt for a platform. The prompt can be
        fed to any external image model (DALL·E, Qwen-Image). Pass ``model``
        matching the target image model so the prompt uses the right language.
        ``skill`` defaults to "auto" (picked from recommendation kind)."""
        return _impl_build_image_prompt(source_id, platform=platform, skill=skill,
                                        model=model, title=title, subtitle=subtitle,
                                        cta=cta, badges=badges)


def create_server() -> "FastMCP":
    """Build and return the FastMCP server instance (for testing)."""
    if not _MCP_AVAILABLE:
        raise RuntimeError("mcp package is not installed. Install with: pip install 'promoagent[mcp]'")
    mcp = FastMCP("promoagent")
    _register(mcp)
    return mcp


def main() -> None:
    """Start the MCP server over stdio."""
    if not _MCP_AVAILABLE:
        print("promoagent-mcp: missing 'mcp' dependency. "
              "Install with: pip install 'promoagent[mcp]'", file=sys.stderr)
        sys.exit(1)
    # MCP stdio uses stdout for JSON-RPC; suppress INFO log noise on stderr so
    # AI tools don't surface it as errors. set_level mutates the global logger
    # instance, so pipeline modules holding an imported reference also quiet down.
    from .logger import LogLevel, logger
    logger.set_level(LogLevel.WARNING)
    mcp = create_server()
    mcp.run()


if __name__ == "__main__":
    main()
