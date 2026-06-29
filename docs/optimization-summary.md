# Source2Launch Optimization Notes

This document records the current product-level optimization work. The main product direction is no longer a Star diagnosis report; it is a source-grounded promotion workflow for open-source projects and papers.

## Current Main Path

```sh
source2launch promote . --platform xhs
source2launch promote paper.pdf --skill paper --platform zhihu
source2launch optimize . --output launch-assets/
source2launch markdown . --markdown-type launch --output LAUNCH.md
source2launch publish promotion.json --platform xhs --publish-mode review
```

## What Changed

### 1. CLI product shape

- Added `promote` as the primary copy-generation command.
- Added `optimize` as the full launch-assets generator.
- Added `markdown` for local Markdown documents.
- Added `publish` for human-reviewed publish plans.
- Removed historical command aliases, standalone diagnosis commands, and HTML report output from the public CLI surface.

### 2. Source-grounded planning layer

AI promotion prompts now ask for a `promotionStrategy` before platform copy:

- `coreAngle`
- `contentGraph`
- `audienceSegments`
- `platformAdaptation`
- `visualNarrative`
- `reviewGate`

This keeps platform copy aligned with source evidence instead of generating unrelated social posts.

### 3. Task skills

The CLI now parses and applies:

- `--skill paper`
- `--skill code`
- `--skill paper-code`
- `--skill social`
- `--skill visual`
- `--skill markdown`

Skills set default audience, tone, prompt presets, and review focus.

### 4. Prompt presets

Prompt presets are now injected into the AI system prompt:

- `grounded`
- `author`
- `realworld`
- `autopr`
- `scholardag`
- `human`

Users can add presets and notes:

```sh
source2launch promote paper.pdf \
  --platform zhihu \
  --prompt-preset paper,visual \
  --prompt-note "Use a researcher reading-note voice."
```

### 5. Evidence handling

- Direct PDF targets are automatically treated as PDF evidence.
- Direct Markdown/text targets are automatically treated as document evidence.
- Local `--context` PDF/Markdown/text files are added to evidence.
- Remote `--context` URLs are kept as review notes unless their content is provided elsewhere.

### 6. Publish safety

`publish` generates a plan only. It does not log in, bypass platform checks, call private APIs, or click publish.

```sh
source2launch publish promotion.json --platform producthunt --publish-mode assist --yes
```

`assist` describes the fields a logged-in browser helper could fill, while the final publish action remains manual.

## Existing Infrastructure Still Useful

- `source2launch/ai.py`: handles OpenAI-compatible / ModelScope text calls.
- `source2launch/image.py`: handles ModelScope and Gradio image generation.
- `source2launch/server.py`: provides the local image API.
- Legacy HTML report output has been removed; `content-review.md` and `campaign.json` are now the durable review artifacts.

These are supporting capabilities; they should not dominate the README first screen.

## Next Recommended Work

1. Add remote context extraction for arXiv, OpenReview, GitHub, and project pages.
2. Add paper figure/table extraction for visual evidence.
3. Add examples generated from known project-paper pairs.
4. Keep `SOURCE2LAUNCH_*` as the documented environment prefix and avoid adding new legacy aliases.
5. Add official-API adapters only where platform APIs are stable and policy-compliant.
