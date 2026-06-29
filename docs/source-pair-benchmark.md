# Source Pair Benchmark

This benchmark keeps a small set of open-source projects that also have public launch, paper, product, or technical promotion material. Use it to compare `source2launch` output with real-world writing patterns without copying the original text.

The machine-readable sample list lives in [`examples/source-pairs.json`](../examples/source-pairs.json).

## Goal

`source2launch` should be able to take a repository, paper, PDF, article, or local project and produce channel-ready promotion content. These source pairs help test whether the model can:

- extract a concrete hook from real source material,
- ground claims in repo, paper, blog, demo, or docs evidence,
- produce different structures for X/Twitter, LinkedIn, Product Hunt, Show HN, Zhihu, Xiaohongshu, WeChat Official Account, and WeChat Moments,
- suggest visual assets from paper figures, README screenshots, demo frames, and product pages,
- keep the final result human-reviewed before publishing.

## Recommended Workflow

1. Pick an item from `examples/source-pairs.json`.
2. Generate a promotion pack from the repository or local project.
3. Compare the generated pack with the official blog, paper page, product page, or project page listed under `promotionReferences`.
4. Revise prompt presets or add a prompt note when the generated content misses the real-world angle.
5. Use `source2launch publish ... --publish-mode review` or `--publish-mode assist` only after the generated payload has been reviewed.

Example:

```sh
mkdir -p examples/generated

source2launch promote https://github.com/facebookresearch/segment-anything \
  --platform launch \
  --prompt-preset paper,visual \
  --prompt-preset launchkit \
  --json \
  --output examples/generated/segment-anything.json

source2launch publish examples/generated/segment-anything.json \
  --platform producthunt \
  --publish-mode review
```

For a local self-check:

```sh
mkdir -p examples/generated

source2launch promote . \
  --platform all \
  --prompt-preset launchkit \
  --prompt-preset visual \
  --json \
  --output examples/generated/source2launch-local.json

source2launch publish examples/generated/source2launch-local.json \
  --platform xhs \
  --publish-mode assist
```

## Evaluation Rubric

Use this rubric when comparing generated output with the real reference material.

| Dimension | What to check |
| --- | --- |
| First-line claim | The opening line should name the project, problem, method, result, command, or demo immediately. |
| Source grounding | Claims should trace back to repo README, paper, official blog, docs, demo, or project page evidence. |
| Channel fit | Product Hunt should have tagline, maker comment, demo/gallery proof, and feedback ask. Show HN should be plain and tryable. Zhihu should read like a credible answer. Xiaohongshu should become a carousel plan. |
| Visual evidence | The output should name source clips such as abstract crop, method figure, result table, README quickstart, demo screenshot, or product workflow image. |
| Human voice | The copy should avoid generic hype, excessive feature inventory, broad slogans, and unsupported superlatives. |
| Caveats | Missing source evidence, incomplete extraction, old repository status, benchmark limitations, or model capability limits should be visible. |
| Publish safety | Generated content should pass through review mode or assist mode. Assist mode fills drafts only and leaves final publish/submit clicks to the user. |

## Current Benchmark Items

| ID | Source type | Why it is useful |
| --- | --- | --- |
| `source2launch-local` | local repo plus local docs | Self-checks whether this project still presents itself as a promotion-copy generator rather than the older diagnosis tool. |
| `segment-anything` | repo, paper, official blog, demo | Tests research-launch writing with strong visual evidence and a clear demo. |
| `whisper` | repo, paper, official blog | Tests concise developer/research positioning with model, paper, code, and practical use cases. |
| `vllm` | repo, paper, technical blog | Tests systems writing around a named mechanism and performance evidence. |
| `autogen` | repo, paper, research blog | Tests agent-framework explanation, human-in-the-loop framing, and long-form technical copy. |
| `llava` | repo, paper, project page | Tests multimodal research promotion, visual examples, and carousel-friendly source evidence. |
| `dify` | repo, product page | Tests product-led open-source launch copy where the reference is more SaaS-like than paper-like. |

## Prompt Tuning Loop

When generated content is weaker than the reference material, prefer small, source-grounded prompt notes instead of broad style instructions.

Good prompt notes:

```sh
source2launch promote https://github.com/vllm-project/vllm \
  --platform hn \
  --prompt-preset launchkit,technical \
  --prompt-note "Open with PagedAttention or the serving bottleneck. Do not use throughput numbers unless found in the source."
```

```sh
source2launch promote https://github.com/haotian-liu/LLaVA \
  --platform xhs \
  --prompt-preset paper,visual,xhs \
  --prompt-note "Make the Xiaohongshu output a 6-card carousel: problem, method, demo, code, paper figure, caveat."
```

Avoid prompt notes that ask the model to imitate a source verbatim. The benchmark is for structure, evidence selection, and channel fit, not copying official wording.

## Publish Review

The benchmark should end in a reviewable publish plan, not direct posting:

```sh
source2launch publish examples/generated/llava.json --platform xhs --publish-mode review
source2launch publish examples/generated/llava.json --platform xhs --publish-mode assist --yes
```

`review` creates a plan for human inspection. `assist` prepares a browser-assisted draft fill payload for logged-in pages, but the browser layer must not log in, bypass captchas, call private APIs, or click the final publish button.
