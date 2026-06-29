# Prompt Presets

`source2launch` includes reusable prompt presets for steering AI-generated promotion copy. Presets are additive: `grounded`, `author`, `realworld`, `autopr`, `scholardag`, and `human` are enabled by default, and `--prompt-preset` adds more instructions.

If you want a complete ready-to-use workflow, start with [`--skill`](skills.md). Skills choose defaults for task, platform, audience, tone, prompt presets, and review focus. Prompt presets are lower-level writing controls.

## CLI Usage

```sh
source2launch promote paper.md --platform all --prompt-preset paper,visual
source2launch promote . --platform launch --prompt-preset launchkit
source2launch promote paper.md --platform all --prompt-preset autopr,scholardag,paper2web
source2launch promote . --platform twitter --prompt-preset tweet --prompt-preset launch
source2launch promote paper.md --platform zhihu --prompt-preset paper --prompt-preset zhihu
source2launch promote . --prompt-note "Use a dry open-source maintainer voice. Avoid emojis."
source2launch promote paper.md --prompt-file ./prompts/my-paper-style.txt
```

`--prompt-preset` can be repeated or comma-separated. `--prompt-note` can be repeated. `--prompt-file` reads local text files and appends them as custom instructions.

## Built-In Presets

- `grounded`: keep claims tied to repository, paper, URL, text, or image evidence.
- `author`: write like a maintainer or researcher, not like ad copy.
- `realworld`: compare against real technical promotion structure before writing.
- `autopr`: promotion-planning preset inspired by AutoPR-style task formulation: extract source material, synthesize an angle, adapt it to each platform, then review fidelity, engagement, and platform alignment.
- `scholardag`: build a content graph for problem, method, evidence, visual proof, caveat, audience, and next action before writing variants.
- `human`: make each post feel like one person sharing one concrete observation.
- `tweet`: tighten X/Twitter output with one angle per post, early evidence, sparse tags, and compact length.
- `paper`: explain problem, method, evidence, why it matters, and limitations.
- `launch`: produce concrete open-source launch copy with command and reader fit.
- `launchkit`: generate developer launch material for LinkedIn, Product Hunt, Show HN, and maintainer follow-up comments.
- `technical`: keep inputs, outputs, APIs, CLI commands, and workflow boundaries visible.
- `zhihu`: structure output as a credible technical answer.
- `xhs`: structure output as a Xiaohongshu carousel note.
- `wechat`: structure output as a WeChat article and Moments post.
- `visual`: turn source evidence into image and screenshot plans.
- `paper2web`: check presentation completeness and visual navigability for paper-like sources.
- `thread`: structure a thread with hook, context, mechanism, evidence, caveat, and next action.

## Research-Inspired Middle Layer

The AI output now includes `promotionStrategy` before platform variants. This is the planning layer used by the prompt:

- `coreAngle`: the one source-grounded angle worth promoting.
- `contentGraph`: problem, method, evidence, visual, caveat, and action nodes with source evidence.
- `audienceSegments`: who should care and which platforms fit them.
- `platformAdaptation`: how each platform changes format, tone, visual, tags, and avoid-list.
- `visualNarrative`: which source clips or generated social cards should support the claim.
- `qualityRubric`: three review axes before publishing:
  - `fidelity`: factual accuracy, core contribution coverage, terminology consistency, and missing evidence.
  - `engagement`: hook quality, narrative clarity, reader fit, and next action.
  - `alignment`: platform-native tone, format, tags, visual fit, and cross-platform adaptation.
- `reviewGate`: fidelity, engagement, platform alignment, completeness, and manual review questions.

The practical lesson is simple: keep a stable source-grounded strategy first, then render channel-native copy from it.

## Useful Custom Prompt Notes

Use one or more of these with `--prompt-note` when you want tighter output:

```text
Use a dry open-source maintainer voice. No emojis. No marketing adjectives.
```

```text
For every claim, include the exact source evidence in evidenceNotes or citationsToUse.
```

```text
Prefer one concrete command, API route, file name, or paper figure over a general benefit.
```

```text
Generate titles that sound like a researcher sharing a useful reading note, not like a paid promotion.
```

```text
Keep Xiaohongshu cards readable on mobile: one claim per card, under 28 Chinese characters for cover text.
```

```text
For WeChat Official Account output, write short section headings and keep paragraphs under 120 Chinese characters.
```

## Programmatic Use

```python
from source2launch.analyzer import analyze_target
from source2launch.ai import generate_ai_content

source = analyze_target("paper.md")
result = generate_ai_content(
    source,
    platform="all",
    brief_section="Use a researcher reading-note voice.\nFocus on paper figures and limitations.",
)

print(result["content"]["promotionStrategy"]["coreAngle"])
```
