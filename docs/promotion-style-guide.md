# Promotion Style Guide

source2launch generates social copy from source evidence. The intended style is closer to technical paper/project sharing than generic marketing.

## Writing Patterns

- Lead with what the paper or project does in one sentence.
- Put task, method, code, data, or visible result evidence near the top.
- Start from a promotion strategy before writing: source extraction, core angle, content graph, platform adaptation, and review gate.
- Keep product-style taglines short and concrete.
- Add caveats when the source does not provide enough proof.
- Avoid unsupported metrics, broad claims, and vague hype.
- Prefer author voice over advertising voice: concrete input, output, command, evidence, and reader fit.
- Avoid generic words such as "必备", "神器", "高质量", "提升效率", "打造完整", "破圈", "爆款", "颠覆", "最强", and "轻松" unless the source itself uses them.

## Tweet Shapes

1. Problem/context -> contribution -> evidence -> who should read it.
2. Paper title -> method/result from abstract or figure -> why it matters -> caveat.
3. Project workflow -> concrete command or source proof -> what kind of developer should try it.

## Platform Shapes

### Zhihu

- Use answer-first structure: conclusion, background, method, evidence, limitations, and reader fit.
- Keep the tone analytical and restrained. It should read like a useful technical answer, not a sales page.
- Cite the source material explicitly: paper abstract crop, method figure, result table, README excerpt, command, or demo screenshot.
- Good image set: answer header, evidence figure card, limitations/reader-fit card.

### Xiaohongshu

- Generate 2-3 title options and short cover text before writing the body.
- Treat the output as a carousel note: each card should carry one takeaway and one visual suggestion.
- Use lighter Chinese copy and clear tags, but do not invent results, awards, user counts, or benchmark wins.
- Good image set: cover card, source evidence card, thread/takeaway structure card.

### WeChat Official Account

- Generate title, summary, cover text, section outline, and body.
- Prefer article sections such as introduction, problem, method, evidence/results, limitations, and who should read it.
- Place paper screenshots or repository evidence near the claim they support.
- Good image set: article header, evidence explanation image, article/thread outline image.

### WeChat Moments

- Keep the copy compact and conversational.
- Lead with one useful takeaway and one reason to open the source.
- Avoid dense citations; put details in the linked article, Zhihu answer, or thread.

## Visual Patterns

- Abstract crop with the core claim highlighted.
- Method figure or architecture diagram crop with a short caption.
- Result table crop only when the numbers are legible and central to the claim.
- Repository README or terminal screenshot for developer tools.
- Carousel order: hook/cover, source proof, simplified takeaway, method or workflow, caveat, call to read/try.

## Implementation Notes

- `evidence.documentClips` carries candidate snippets for source-grounded visuals.
- `promotionStrategy` is the research-inspired middle layer: it keeps core angle, content graph, audience segments, platform adaptation, visual narrative, and review gate together before platform variants are rendered.
- `promotionStrategy.qualityRubric` stores the publish-time review axes:
  - Fidelity: source faithfulness, core contribution coverage, terminology consistency, and missing evidence.
  - Engagement: concrete hook, narrative clarity, audience fit, and next action.
  - Alignment: platform-native format, tone, tags, image dimensions, and visual-to-claim fit.
- `content-review.md` renders the same rubric as checkboxes so a human reviewer can approve or rewrite generated copy before publishing.
- `visualPlan.recommendedClips` tells downstream image generation which source crop to use.
- `--source-image-url` lets multimodal providers inspect paper screenshots, figures, and other visual evidence.
- `--prompt-preset` adds reusable prompt instructions such as `paper`, `launch`, `visual`, `zhihu`, `xhs`, and `wechat`.
- `--prompt-note` and `--prompt-file` add task-specific prompt instructions without changing source code.
- `qualityReview` asks the model to compare generated copy with real promotion patterns and name risky phrases or missing evidence.
- `--image-provider gradio` can send the resulting image prompt to a local Gradio app.
- `--skill visual` asks the model to keep source clips, figures, screenshots, and generated social cards grounded in evidence.
- JSON repair is enabled by default so providers that return prose can be asked once more to convert the result into the required schema.

## Research-Inspired Workflow

The current prompt borrows practical structure from academic promotion and multimodal presentation papers:

1. Extract source material: title, task, method, evidence, code/demo, visual assets, caveats, and audience signals.
2. Build the middle layer: `promotionStrategy.coreAngle` plus a content graph that connects claims to evidence.
3. Adapt by platform: X/Twitter, LinkedIn, Product Hunt, Show HN, Zhihu, Xiaohongshu, WeChat Official Account, and Moments each get native format rules.
4. Review before publishing: check Fidelity, Engagement, and Alignment as separate axes instead of relying on one generic quality score.

## References

- Hugging Face Papers: https://huggingface.co/papers
- Papers with Code: https://paperswithcode.com/
- Product Hunt launch surface: https://www.producthunt.com/
- Zhihu community and answer surface: https://www.zhihu.com/term/community
- Xiaohongshu creator surface: https://creator.xiaohongshu.com/
- WeChat Official Account / drafts developer docs: https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html
- Prompt Presets: prompt-presets.md
- Promotion Benchmark: promotion-benchmark.md
- Gradio Python client: https://www.gradio.app/guides/getting-started-with-the-python-client
- Gradio cURL API pattern: https://www.gradio.app/guides/querying-gradio-apps-with-curl
- AutoPR project page: https://yzweak.github.io/autopr.github.io/
- AutoPR paper: https://arxiv.org/html/2510.09558v1
- Paper2Web: https://arxiv.org/abs/2510.15842
- PaperX: https://arxiv.org/abs/2602.03866
- Social media influencers and AI research visibility: https://arxiv.org/html/2401.13782v1
