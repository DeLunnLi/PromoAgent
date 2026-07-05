"""Gradio web interface for Source2Launch.

Usage:
    source2launch serve
    source2launch serve --port 7860 --share

Requires: pip install gradio
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Generator

# ---------------------------------------------------------------------------
# Custom CSS — dark glassmorphism style
# ---------------------------------------------------------------------------

_CSS = """
/* Dark base */
body, .gradio-container {
    background: #0f1117 !important;
    color: #e8eaf0 !important;
}

/* Card panels */
.panel, .gr-box, .contain {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    backdrop-filter: blur(12px);
}

/* Header */
.header-banner {
    background: linear-gradient(135deg, #1a1f35 0%, #0f1117 100%);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    padding: 20px 32px;
    margin-bottom: 24px;
    border-radius: 12px;
}

.header-banner h1 {
    font-size: 1.8rem;
    font-weight: 700;
    background: linear-gradient(90deg, #7c8cf8, #a78bfa, #ec4899);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}

.header-banner p { color: #94a3b8; margin: 4px 0 0; }

/* Buttons */
.primary-btn button {
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 12px 24px !important;
    border-radius: 8px !important;
    transition: all 0.2s !important;
}
.primary-btn button:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 25px rgba(124, 58, 237, 0.4) !important;
}

.secondary-btn button {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #94a3b8 !important;
    border-radius: 8px !important;
}
.secondary-btn button:hover {
    background: rgba(255,255,255,0.1) !important;
    color: #e8eaf0 !important;
}

/* Inputs */
textarea, input[type=text], .gr-input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #e8eaf0 !important;
    border-radius: 8px !important;
}

/* Tabs */
.tab-nav button {
    color: #64748b !important;
    border-bottom: 2px solid transparent !important;
    font-weight: 500 !important;
}
.tab-nav button.selected {
    color: #a78bfa !important;
    border-bottom-color: #a78bfa !important;
}

/* Status badge */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 500;
}
.status-ok { background: rgba(34,197,94,0.15); color: #4ade80; }
.status-err { background: rgba(239,68,68,0.15); color: #f87171; }

/* Progress */
.progress-text { color: #94a3b8; font-size: 0.85rem; margin-top: 8px; }

/* Markdown output */
.platform-content { line-height: 1.7; }
.platform-content h1, .platform-content h2, .platform-content h3 {
    color: #a78bfa !important;
}
"""

# ---------------------------------------------------------------------------
# Platform display names
# ---------------------------------------------------------------------------

_PLATFORM_ICONS = {
    "xiaohongshu": "📱 小红书",
    "zhihu": "📝 知乎",
    "wechatmoments": "💬 微信",
    "wechatarticle": "📰 微信公众号",
    "showhn": "🖥️ Show HN",
    "producthunt": "🎯 Product Hunt",
    "twitter": "🐦 Twitter / X",
    "linkedin": "💼 LinkedIn",
    "reddit": "🤖 Reddit",
}

_ALL_PLATFORMS = list(_PLATFORM_ICONS.keys())


def _platform_label(key: str) -> str:
    return _PLATFORM_ICONS.get(key.lower(), f"📄 {key}")


# ---------------------------------------------------------------------------
# Core generation logic
# ---------------------------------------------------------------------------

def _check_api_key() -> tuple[bool, str]:
    from .ai import has_ai_key
    if has_ai_key():
        model = os.environ.get("SOURCE2LAUNCH_MODEL") or os.environ.get("OPENAI_MODEL") or "配置中"
        return True, f"✅ API Key 已配置 · 模型：{model}"
    return False, "❌ 未检测到 API Key（请在 .env 中配置）"


def _generate(
    target: str,
    platform: str,
    with_image: bool,
    refine_feedback: str,
    prev_session: dict | None,
    progress=None,
) -> Generator[tuple, None, None]:
    """Main generation generator — yields (status, p1, p2, ..., image, session)."""
    from .analyzer import analyze_target
    from .ai import generate_ai_content, has_ai_key, refine_content
    from .examples import find_examples
    from .promo_prompts import build_evidence_brief, build_promo_payload

    n_platforms = len(_ALL_PLATFORMS)

    def _progress(pct, msg):
        if progress:
            progress(pct, desc=msg)

    try:
        # --- Refine mode ---
        if refine_feedback.strip() and prev_session:
            _progress(0.1, "精炼中…")
            options = {}
            refined = refine_content(prev_session, refine_feedback.strip(), options=options)
            promotions = refined["content"].get("promotions") or {}
            outputs = _promotions_to_outputs(promotions)
            yield ("✓ 精炼完成", *outputs, None, refined)
            return

        # --- Normal generation ---
        if not target.strip():
            empty = [""] * n_platforms
            yield ("请输入推广内容", *empty, None, None)
            return

        if not has_ai_key():
            empty = [""] * n_platforms
            yield ("⚠️ 需要配置 API Key 才能生成内容", *empty, None, None)
            return

        _progress(0.05, "分析来源…")
        result = analyze_target(target.strip())
        project_name = result.get("project", {}).get("name", "")

        _progress(0.20, f"搜索「{project_name}」的参考示例…")
        plat = platform if platform != "全部平台" else "all"
        examples = find_examples(result, platform=plat, verbose=False) or None

        _progress(0.45, "生成推广内容…")
        ai_result = generate_ai_content(
            result,
            platform=plat,
            examples=examples,
            compare_with_examples=bool(examples),
        )

        promotions = ai_result["content"].get("promotions") or {}
        positioning = ai_result["content"].get("positioning") or ""

        _progress(0.90, "整理输出…")
        outputs = _promotions_to_outputs(promotions)

        # Image generation (optional)
        image_path = None
        if with_image and has_ai_key():
            try:
                from .image import generate_platform_images, has_image_key
                if has_image_key():
                    _progress(0.93, "生成封面图…")
                    with tempfile.TemporaryDirectory() as tmp:
                        imgs = generate_platform_images(result, Path(tmp))
                        if imgs:
                            src = imgs[0].get("outputPath")
                            if src and Path(src).exists():
                                # Copy to a persistent temp location
                                dest = Path(tempfile.mktemp(suffix=".jpg"))
                                dest.write_bytes(Path(src).read_bytes())
                                image_path = str(dest)
            except Exception as exc:
                print(f"Image generation failed: {exc}", file=sys.stderr)

        status = f"✓ 生成完成 · {project_name}" if project_name else "✓ 生成完成"
        if positioning:
            status += f"\n**定位：** {positioning}"

        yield (status, *outputs, image_path, ai_result)

    except Exception as exc:  # noqa: BLE001
        empty = [""] * n_platforms
        yield (f"❌ 错误：{exc}", *empty, None, None)


def _promotions_to_outputs(promotions: dict) -> list[str]:
    """Map promotions dict to a fixed-length list matching _ALL_PLATFORMS."""
    outputs = []
    for key in _ALL_PLATFORMS:
        item = promotions.get(key)
        if not item:
            # Try camelCase variants
            for k, v in promotions.items():
                if k.lower().replace("-", "").replace("_", "") == key.lower().replace("-", ""):
                    item = v
                    break
        md = ""
        if isinstance(item, dict):
            md = item.get("markdown") or ""
            if item.get("titles"):
                titles = "\n".join(f"- {t}" for t in item["titles"])
                md = f"**备选标题：**\n{titles}\n\n{md}"
        elif isinstance(item, str):
            md = item
        outputs.append(md.strip())
    return outputs


# ---------------------------------------------------------------------------
# Build the Gradio app
# ---------------------------------------------------------------------------

def build_app() -> Any:
    try:
        import gradio as gr
    except ImportError:
        print("请先安装 Gradio：pip install gradio", file=sys.stderr)
        sys.exit(1)

    has_key, key_status = _check_api_key()

    with gr.Blocks(css=_CSS, title="Source2Launch") as app:

        # Session state
        session_state = gr.State(None)

        # ── Header ──────────────────────────────────────────────────────────
        gr.HTML("""
        <div class="header-banner">
          <h1>🚀 Source2Launch</h1>
          <p>AI 推广内容生成器 · 输入任何描述，生成多平台推广文案</p>
        </div>
        """)

        with gr.Row(equal_height=False):

            # ── Left panel: input ─────────────────────────────────────────
            with gr.Column(scale=1, min_width=320):
                gr.Markdown("### 📥 输入来源")
                target_input = gr.Textbox(
                    label="描述 / GitHub URL / PDF路径",
                    placeholder=(
                        "例如：\n"
                        "• 上海阿强火锅，麻辣鲜香，人均80元，静安区\n"
                        "• https://github.com/user/repo\n"
                        "• /path/to/paper.pdf"
                    ),
                    lines=5,
                )
                file_input = gr.File(
                    label="上传文件（PDF / Markdown）",
                    file_types=[".pdf", ".md", ".txt"],
                )

                gr.Markdown("### ⚙️ 设置")
                platform_dd = gr.Dropdown(
                    label="目标平台",
                    choices=["全部平台", "小红书", "知乎", "微信", "Show HN", "Product Hunt", "Twitter"],
                    value="全部平台",
                )
                with_image_cb = gr.Checkbox(label="同时生成封面图 🖼️", value=False)

                key_status_md = gr.Markdown(
                    f'<span class="status-badge status-{"ok" if has_key else "err"}">{key_status}</span>'
                )

                gr.Markdown("---")
                with gr.Row():
                    generate_btn = gr.Button(
                        "✨ 生成推广内容", variant="primary", elem_classes=["primary-btn"]
                    )
                    clear_btn = gr.Button("🗑️ 清空", elem_classes=["secondary-btn"])

                gr.Markdown("### 💡 精炼")
                refine_input = gr.Textbox(
                    label="反馈（生成后可精炼）",
                    placeholder="例如：小红书那条太广告感了，改得更自然",
                    lines=2,
                )
                refine_btn = gr.Button("🔄 精炼", elem_classes=["secondary-btn"])

            # ── Right panel: output ───────────────────────────────────────
            with gr.Column(scale=2):
                status_md = gr.Markdown("等待生成…")

                with gr.Tabs() as result_tabs:
                    platform_outputs: list[gr.Textbox] = []
                    preview_boxes: list[gr.Markdown] = []
                    fill_btns: list[gr.Button] = []

                    for key in _ALL_PLATFORMS:
                        with gr.Tab(_platform_label(key)):
                            # Editable content area
                            tb = gr.Textbox(
                                value="尚未生成，点击「生成推广内容」开始。",
                                lines=12,
                                max_lines=35,
                                label="内容（可直接编辑）",
                                show_copy_button=True,
                                elem_classes=["platform-content"],
                            )
                            platform_outputs.append(tb)

                            # Live Markdown preview — updates as user edits
                            preview_md = gr.Markdown(
                                label="Markdown 预览",
                                visible=True,
                                elem_classes=["platform-content"],
                            )
                            preview_boxes.append(preview_md)

                            # Sync textbox → preview in real time
                            tb.change(fn=lambda x: x, inputs=[tb], outputs=[preview_md])

                            # Fill-to-browser button
                            fill_btn = gr.Button(
                                f"🌐 在浏览器中填写到 {_platform_label(key)}",
                                elem_classes=["secondary-btn"],
                                size="sm",
                            )
                            fill_btns.append(fill_btn)

                            # Fill to browser — runs in background thread
                            _key = key  # capture loop variable

                            def _fill_browser(content, platform=_key):
                                import threading
                                try:
                                    from .browser import fill_platform
                                    t = threading.Thread(
                                        target=fill_platform,
                                        args=(platform, content),
                                        daemon=True,
                                    )
                                    t.start()
                                    return gr.update()
                                except SystemExit:
                                    return gr.update()

                            fill_btn.click(
                                fn=_fill_browser,
                                inputs=[tb],
                                outputs=[],
                            )

                with gr.Row():
                    image_output = gr.Image(
                        label="封面图预览",
                        visible=False,
                        height=300,
                    )

        # ── Event handlers ───────────────────────────────────────────────

        def _target_from_inputs(target: str, file) -> str:
            if file is not None:
                return file.name if hasattr(file, "name") else str(file)
            return target

        def _run_generate(target, file, platform, with_image, refine_fb, session):
            real_target = _target_from_inputs(target, file)
            for result_tuple in _generate(real_target, platform, with_image, refine_fb, session):
                status = result_tuple[0]
                outputs = list(result_tuple[1: 1 + len(_ALL_PLATFORMS)])
                img = result_tuple[1 + len(_ALL_PLATFORMS)]
                new_session = result_tuple[2 + len(_ALL_PLATFORMS)]
                show_img = img is not None
                yield [status] + outputs + [gr.update(value=img, visible=show_img), new_session]

        all_outputs = [status_md] + platform_outputs + [image_output, session_state]

        generate_btn.click(
            fn=_run_generate,
            inputs=[target_input, file_input, platform_dd, with_image_cb, refine_input, session_state],
            outputs=all_outputs,
        )

        refine_btn.click(
            fn=_run_generate,
            inputs=[target_input, file_input, platform_dd, with_image_cb, refine_input, session_state],
            outputs=all_outputs,
        )

        def _clear():
            empty = ["尚未生成，点击「生成推广内容」开始。"] * len(_ALL_PLATFORMS)
            return ["等待生成…"] + empty + [gr.update(visible=False), None, ""]

        clear_btn.click(
            fn=_clear,
            outputs=[status_md] + platform_outputs + [image_output, session_state, refine_input],
        )

    return app


# ---------------------------------------------------------------------------
# Launch helper
# ---------------------------------------------------------------------------

def launch(host: str = "127.0.0.1", port: int = 7860, share: bool = False) -> None:
    app = build_app()
    print(f"\nSource2Launch Web UI starting at http://{host}:{port}\n", file=sys.stderr)
    app.launch(
        server_name=host,
        server_port=port,
        share=share,
        show_api=False,
        quiet=True,
    )
