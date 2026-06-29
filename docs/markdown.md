# Markdown Generation

`source2launch` can generate local Markdown documents from project evidence. This path does not require an AI provider.

## Usage

```sh
source2launch markdown . --markdown-type project --output PROJECT.md
source2launch markdown . --markdown-type readme --output README.draft.md
source2launch markdown . --markdown-type launch --output LAUNCH.md
source2launch markdown . --markdown-type promo --output PROMO.md
source2launch markdown . --markdown-type all --output project-pack.md
```

The same workflow is available through the task skill:

```sh
source2launch markdown . --markdown-type project --output PROJECT.md
```

## Document Types

| Type | Output |
| --- | --- |
| `project` | Project brief with source snapshot, repository evidence, positioning, suggested next Markdown assets, and review checklist. |
| `readme` | README draft with intro, quickstart, what-it-does section, example, source evidence, limitations, and license placeholder. |
| `launch` | Launch kit with tagline, first proof, X/Twitter draft, Product Hunt draft, Show HN draft, and launch checklist. |
| `promo` | Promotion notes for Zhihu, Xiaohongshu, WeChat, visual assets, and source links. |
| `all` | Combines all document types into one Markdown file. |

## Source Evidence

For repositories, the Markdown generator uses:

- README opening,
- install commands,
- visual references,
- document clips,
- examples and demo paths,
- package metadata,
- topics,
- file highlights.

With `--context`, related sources are included in the project brief:

```sh
source2launch markdown paper.md \
  --markdown-type project \
  --context https://github.com/user/repo \
  --output paper-code-brief.md
```

This is useful when a paper has an accompanying repository or a repository has a paper/project page.

## Boundaries

The local Markdown generator is intentionally conservative. It does not invent benchmarks, user counts, star counts, testimonials, maturity claims, or paper results. Use the AI promotion flow when you need more polished cross-platform copy, then review the generated payload before publishing.
