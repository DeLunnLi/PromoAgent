# Competitor Benchmark

This note tracks adjacent products and turns their useful patterns into `source2launch` prompt and product decisions.

## Adjacent Products

### General Social AI Suites

- Buffer AI Assistant focuses on brainstorming, rewriting, repurposing one idea into multiple formats, and tailoring posts for LinkedIn, Threads, X, Instagram, Bluesky, and more: https://buffer.com/ai-assistant
- Canva's AI social media post generator emphasizes platform-optimized posts, tone/goal/audience controls, repurposing existing content, pairing posts with visuals, and scheduling through a content planner: https://www.canva.com/features/ai-social-media-post-generator/
- Hootsuite Wisdom positions AI as an insight-to-action teammate: trend/risk detection, competitor tracking, content generation, report summaries, and workflow execution: https://www.hootsuite.com/wisdom-ai

### Research-Paper Assistants

- Scholarcy summarizes academic documents into structured flashcards, stores figures/tables, highlights key findings, and helps organize research knowledge: https://www.scholarcy.com/
- SciSummary emphasizes academic structure: abstract, methods, results, conclusions, figure analysis, citations, semantic search, and paper comparison: https://scisummary.com/

### Developer Launch Channels

- Product Hunt's launch guide requires concrete launch fields such as URL, product name, tagline, description, tags, thumbnail, gallery images, optional video/demo, pricing, and first comment. It recommends simple language, clear user fit, and asking for feedback rather than upvotes: https://www.producthunt.com/launch/preparing-for-launch
- Show HN is only for something the maker built and users can try. It asks for a title beginning with `Show HN`, encourages easy trial without barriers, and discourages vote/comment requests: https://news.ycombinator.com/showhn.html
- GitHub social-card generator repositories show that open-source promotion also needs visual proof, not just text: https://github.com/topics/social-card-generator

## Implications For source2launch

- Keep `source2launch` narrower than Buffer or Canva: source-grounded promotion for open-source projects and papers, not generic social scheduling.
- Add channel-native developer launch outputs. Product Hunt needs tagline, description, maker comment, gallery checklist, and feedback ask. Show HN needs a tryable project, plain title, technical context, limitations, and no upvote request. LinkedIn needs a professional build note.
- Keep paper promotion structurally academic: problem, method, evidence, figure/table, limitation, and why a researcher should inspect it.
- Pair every text output with a visual plan. For projects: README opening, command, UI/demo screenshot, GitHub social preview. For papers: abstract crop, method figure, result table, limitation paragraph.
- Add future campaign support: turn one source into a 3-7 day launch sequence, not just one post per platform.

## Changes Already Reflected In The Product

- `promote` is the primary command; `tweet` remains a compatibility alias.
- `--platform launch` focuses the output on LinkedIn, Product Hunt, and Hacker News / Show HN.
- `launchkit` adds prompt rules for tagline, first comment, demo proof, install command, caveat, and feedback ask.

## Next Useful Optimizations

- Add a `campaignPlan` schema with day-by-day posts, follow-up replies, and repost variants.
- Add a lightweight scoring pass that checks generated copy against channel rules: Product Hunt tagline length, Show HN tryability, X hashtag count, Zhihu evidence citations, and Xiaohongshu card length.
- Extract screenshots from PDFs and README/docs automatically, then attach selected clips to image-generation requests.
- Add optional scheduling/export adapters later, but keep posting external; `source2launch` should remain a source-to-promotion generator first.
