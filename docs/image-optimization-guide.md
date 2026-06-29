# Image Generation Guide

Source2Launch can prepare promotion images for Xiaohongshu, WeChat, Product Hunt, launch notes, and paper/code explainers. The image workflow should stay source-grounded: use README screenshots, paper figures, result tables, terminal output, or generated cards based on verified evidence.

## Main Commands

```sh
source2launch image . --platform xhs --dry-run
source2launch image . --platform xhs --provider modelscope --output cover.png
source2launch image paper.pdf --platform zhihu --provider gradio --base-url http://127.0.0.1:7860 --output paper-card.png
source2launch optimize . --output launch-assets/
```

`image --dry-run` shows the source-grounded prompt without calling a model. `optimize` still writes reviewable image prompts and launch assets under `launch-assets/`.

## Providers

Use ModelScope-compatible image generation:

```sh
SOURCE2LAUNCH_MODELSCOPE_API_KEY=ms-your-token
SOURCE2LAUNCH_IMAGE_MODEL=Qwen/Qwen-Image
source2launch image . --platform xhs --provider modelscope --output cover.png
```

Use a local Gradio endpoint:

```sh
SOURCE2LAUNCH_IMAGE_PROVIDER=gradio
SOURCE2LAUNCH_GRADIO_URL=http://127.0.0.1:7860
source2launch image . --platform wechat --provider gradio --output wechat-cover.png
```

Use an image editing model with a reference image:

```sh
SOURCE2LAUNCH_IMAGE_MODEL=FireRedTeam/FireRed-Image-Edit-1.1
source2launch image . \
  --platform xhs \
  --image-url https://example.com/source-screenshot.png \
  --prompt "Turn this source screenshot into a credible Xiaohongshu technical cover" \
  --output xhs-edit.png
```

## Recommended Visual Pack

| Platform | Suggested assets |
| --- | --- |
| Xiaohongshu | cover card, terminal screenshot, source evidence screenshot, generated copy screenshot |
| Zhihu | paper/project cover, method/result figure, limitation or comparison card |
| WeChat | 16:9 cover, article lead image, source evidence image |
| Product Hunt | hero card, short demo screenshot, launch checklist |
| Show HN | real terminal/demo screenshot; avoid decorative-only images |

## Style Controls

```sh
SOURCE2LAUNCH_IMAGE_STYLE=poster
SOURCE2LAUNCH_IMAGE_BADGES="证据先行,多平台文案,人工审核"
SOURCE2LAUNCH_IMAGE_TEXT_OVERLAY=true
SOURCE2LAUNCH_IMAGE_NEGATIVE_PROMPT="fake charts, unreadable UI text, invented metrics"
```

Common styles:

| Style | Use case |
| --- | --- |
| `poster` | social cover and launch card |
| `beforeafter` | show source evidence transformed into platform content |
| `terminal` | developer-facing CLI launch |
| `paper` | paper abstract, figure, method, and result summary |

## Review Checklist

- The image should not show fake benchmarks, fake user counts, fake star growth, or invented logos.
- Any chart-like visual should be traceable to a real paper figure, table, README metric, or user-provided source.
- Cover text should stay short enough for mobile previews.
- Xiaohongshu and WeChat covers should use different crop assumptions.
- Keep source screenshots available so a human reviewer can verify the generated image.
