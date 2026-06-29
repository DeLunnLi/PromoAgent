# Promotion Benchmark

This note captures the comparison used to tune `source2launch` prompts after testing generated copy against public technical promotion patterns.

## Observed Real Promotion Patterns

- Technical paper surfaces usually lead with a title-level claim or TL;DR, then expose task, method, result evidence, code/data, and why the reader should inspect it.
- Repository launches usually show what the tool reads, what it generates, one command/API call, who should try it, and a concrete screenshot or README proof.
- X/Twitter launch posts are usually narrower than product pages: one first-line claim, one artifact such as a command or link, one reason to inspect it, and sparse tags.
- X/Twitter paper posts often use a compact chain: problem or title, method/result signal, project/paper/code link, then a short reader cue.
- LinkedIn developer posts usually read like build notes: problem, what changed, concrete artifact, reader fit, and a modest discussion prompt.
- Product Hunt launch copy needs a short tagline, description, maker comment, demo/gallery proof, and feedback request.
- Show HN copy should be plain and tryable: title, what it does, how to try it, implementation note, limitations, and no vote request.
- Zhihu-style promotion is closer to a credible answer: conclusion first, then background, method/workflow, evidence, limitation, and reader fit.
- Xiaohongshu-style technical notes depend on cover text and carousel structure: one takeaway per card, one visual per card, concise tags.
- WeChat Official Account posts need article packaging: title, summary, cover text, sections, body, and source links or screenshots near the claim.

## Generated Copy Failure Modes

- It can overuse general benefits such as "提升效率", "高质量", "必备", or "神器".
- It can bury the concrete command, figure, dataset, API route, or source clip below a broad introduction.
- It can sound like a product ad instead of a maintainer or researcher sharing a useful source.
- It can suggest visuals without naming the exact source crop or evidence.
- It can omit caveats when the source extraction is incomplete.
- It can sound machine-written by covering every feature in one paragraph, using balanced lists, repeating the project name, or ending with a generic benefit.
- It can use a platform inventory as the hook, for example "supports X/Twitter, Zhihu, Xiaohongshu, WeChat", which reads less like a real tweet than a README feature list.

## Prompt Changes

- `realworld` and `human` are now enabled by default with `grounded` and `author`.
- `autopr` and `scholardag` are enabled by default so generation follows a source-extraction, strategy-synthesis, platform-adaptation, and review-gate workflow.
- The schema now includes `promotionStrategy`, a middle layer with `coreAngle`, `contentGraph`, `audienceSegments`, `platformAdaptation`, `visualNarrative`, and `reviewGate`.
- The Twitter/X platform guide now asks for one angle per post, one concrete artifact in the first 80 Chinese characters or first 20 English words, 140-220 Chinese characters where possible, and at most two hashtags.
- The optional `tweet` preset adds stronger X/Twitter constraints for launch and paper posts.
- `--platform launch` adds LinkedIn, Product Hunt, and Hacker News / Show HN output, with `launchkit` for tagline, first comment, demo proof, caveat, and feedback-ask guidance.
- The schema includes `qualityReview`, where the model must name fit, risky phrases, missing evidence, template smells, human-similarity notes, and rewrite notes.
- The prompt asks the model to internally compare against real promotion structure before finalizing.

## Research-Inspired Updates

- Academic promotion work suggests a three-stage flow: source extraction, promotion synthesis, and platform adaptation. `source2launch` maps that into `promotionStrategy` before generating platform variants.
- Scholar-DAG-style presentation generation motivates keeping claims, evidence, visuals, caveats, audience, and action connected in a graph so X/Twitter, Zhihu, Xiaohongshu, WeChat, Product Hunt, and Show HN do not drift into different claims.
- Paper2Web-style presentation work reinforces that paper promotion should not be only a rewritten abstract; it should expose source proof, visual anchors, and a reader path.
- Engagement-oriented social generation is treated as a review signal, not a reason to fabricate metrics or use clickbait.

See also [Competitor Benchmark](competitor-benchmark.md) for adjacent product references.

## Generated vs Real Tweet Checks

| Check | Real technical tweet pattern | Generated copy should do |
| --- | --- | --- |
| First line | Names the project, paper, problem, command, or result immediately | Avoid opening with broad category claims like "open-source promotion is hard" unless followed by concrete evidence |
| Scope | One angle per post | Split repo launch, paper workflow, image assets, and multi-platform output into separate alternatives |
| Evidence | Shows a link, command, figure, table, screenshot, or code artifact | Put `npx source2launch promote ...`, README crop, paper abstract, or API route near the top |
| Tone | Maintainer/researcher voice, often slightly provisional | Prefer "适合想快速试一次的人" over "必备神器" or "一键提升传播效果" |
| CTA | Gives one next action | Use "试试这个命令", "看 README 预览图", or "打开论文方法图" instead of generic conversion copy |

## Human-Writing Heuristics

- One post should usually have one angle, not every feature.
- A concrete detail should appear early: command, figure, API route, file, dataset, screenshot, or source clip.
- Caveats should sound like normal technical caution, not compliance boilerplate.
- Do not use first-person claims unless the input supports author or reader voice.
- Keep hashtags sparse and avoid default emojis.

## Practical Checks

Use these commands to inspect the benchmark-oriented prompt:

```sh
source2launch promote . --prompt-preset paper,visual --json
source2launch promote paper.md --platform all --prompt-preset paper --prompt-preset zhihu
source2launch promote . --platform launch --prompt-preset launchkit
source2launch promote . --platform twitter --prompt-preset launch --prompt-note "Name one exact command in every X/Twitter post."
```
