# Task Skills

`source2launch` task skills are user-facing workflows. A skill chooses the default platform, audience, tone, prompt presets, prompt notes, and review focus for a real promotion task.

Prompt presets still control writing behavior. Skills control the job to be done.

## Available Skills

| Skill | Use it for | Default platform |
| --- | --- | --- |
| `paper` | Promote a paper, abstract, PDF, OpenReview page, arXiv page, or paper note. | `all` |
| `code` | Launch a GitHub repository or local open-source project. | `launch` |
| `paper-code` | Promote a paper and its runnable code together. | `all` |
| `social` | Generate a cross-platform social pack from one source. | `all` |
| `visual` | Plan source-grounded paper figures, README screenshots, demos, and social cards. | `all` |
| `markdown` | Generate local Markdown documents from project evidence. | none |

Aliases are supported. For example, `paper-promo` maps to `paper`, `repo` and `oss` map to `code`, `repo-paper` maps to `paper-code`, and `readme` maps to `markdown`.

## Paper Promotion

```sh
source2launch promote paper.md --skill paper
source2launch promote https://openreview.net/forum?id=0xiPcuWdl5 --skill paper --platform zhihu
source2launch promote https://arxiv.org/abs/2304.02643 --skill paper --json --output examples/generated/paper.json
```

The `paper` skill asks the model to extract:

- problem,
- method or dataset,
- evidence from abstract, figure, table, or result,
- visual clips,
- limitations,
- reader fit.

## Code Promotion

```sh
source2launch promote https://github.com/user/repo --skill code
source2launch promote . --skill code --platform launch
source2launch promote . --skill code --platform hn
```

The `code` skill emphasizes:

- what the project reads,
- what it generates,
- one install or try command,
- README/demo evidence,
- Product Hunt, Show HN, and LinkedIn launch structure,
- caveats around maturity and missing evidence.

## Paper Plus Code

Use `--context` when the promotion needs more than one source. This is the main workflow for a paper with an accompanying repository:

```sh
source2launch promote paper.md \
  --skill paper-code \
  --context https://github.com/user/repo \
  --platform all \
  --json \
  --output examples/generated/paper-code.json
```

The reverse also works:

```sh
source2launch promote https://github.com/user/repo \
  --skill paper-code \
  --context https://arxiv.org/abs/xxxx.xxxxx
```

With `paper-code`, the model must keep source provenance visible:

- paper claims come from the paper, abstract, figures, or tables,
- runnable claims come from README, docs, examples, or install commands,
- visual suggestions should say whether the source is a paper figure, result table, README screenshot, or demo screenshot,
- caveats should name missing code, missing paper text, unclear benchmark evidence, or incomplete extraction.

Current CLI behavior: local `--context` PDF/Markdown/text files are added to evidence. Remote URL contexts are passed as review notes unless their content is also provided through a readable file or the primary target.

## Social Pack

```sh
source2launch promote . --skill social
source2launch promote paper.md --skill social --platform xhs
```

The `social` skill is useful when you want one source rendered into channel-native outputs: X/Twitter, LinkedIn, Product Hunt, Show HN, Zhihu, Xiaohongshu, WeChat Official Account, and Moments.

## Visual Pack

```sh
source2launch promote paper.md --skill visual --platform xhs
source2launch optimize . --skill visual --output launch-assets/
```

The `visual` skill keeps visual evidence grounded in the source. It should not invent benchmark charts, fake UI states, fake logos, or fake paper results.

## Markdown Documents

```sh
source2launch markdown . --markdown-type project --output PROJECT.md
source2launch markdown . --markdown-type readme --output README.draft.md
source2launch markdown . --markdown-type all --output project-pack.md
```

The `markdown` skill uses local source extraction and does not require an AI provider. It can generate:

- `project`: project brief with source snapshot, evidence, positioning, and checklist,
- `readme`: README draft with quickstart, evidence, examples, and limitations,
- `launch`: launch kit with tagline, Product Hunt draft, Show HN draft, and checklist,
- `promo`: promotion notes for Zhihu, Xiaohongshu, WeChat, visuals, and source links,
- `all`: all Markdown documents in one file.

## Review Gate

Skills feed the same `promotionStrategy` middle layer used by the AI prompt:

- `coreAngle`: the main source-grounded promotion angle,
- `contentGraph`: problem, method, evidence, visual proof, caveat, and action,
- `audienceSegments`: who should care and where they should see it,
- `platformAdaptation`: per-platform format, tone, visual, tags, and avoid-list,
- `visualNarrative`: source clips and generated-card ideas,
- `reviewGate`: fidelity, engagement, alignment, completeness, and manual review questions.

The output is still meant for human review before publication:

```sh
source2launch publish examples/generated/paper-code.json --platform xhs --publish-mode review
source2launch publish examples/generated/paper-code.json --platform xhs --publish-mode assist --yes
```

Assist mode may prepare a draft fill payload for logged-in pages, but the final publish or submit click remains manual.
