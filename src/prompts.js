const PROMPT_PRESETS = {
  grounded: {
    label: 'Grounded source claims',
    instructions: [
      'Only claim what the repository, paper, URL, text, or provided image evidence supports.',
      'When a claim depends on a paper figure, abstract, table, README snippet, command, or screenshot, name that source in evidenceNotes or citationsToUse.',
      'Use caveats for missing experiments, missing screenshots, unclear install steps, private data, or incomplete paper extraction.'
    ]
  },
  author: {
    label: 'Author voice',
    instructions: [
      'Write like the project author or paper reader sharing a useful finding, not like an ad copywriter.',
      'Prefer first-person only when it feels natural for an open-source maintainer; otherwise use neutral technical sharing.',
      'Avoid generic praise words such as 必备, 神器, 高质量, 提升效率, 打造完整, 爆款, 颠覆, 最强, and 轻松 unless the source itself uses them.'
    ]
  },
  realworld: {
    label: 'Real promotion benchmark',
    instructions: [
      'Match real technical promotion patterns: title or one-line claim first, then task/context, method/workflow, evidence, code/demo/link, reader fit, and caveat.',
      'Prefer TL;DR, “what it does”, “why it matters”, “what to inspect”, and “how to try it” over broad benefit claims.',
      'For Chinese long-form promotion, prefer 导读/一句话总结/背景/方法/实验或证据/代码或项目地址/局限/适合谁读 rather than a continuous sales paragraph.'
    ]
  },
  autopr: {
    label: 'Academic promotion planning',
    instructions: [
      'Use a three-stage workflow before writing: extract faithful source material, synthesize the most promotable angle, then adapt it to each platform.',
      'Evaluate each generated variant along fidelity, engagement, and platform alignment. Engagement means audience fit and clarity, not clickbait or fake metrics.',
      'For papers, keep timing, target audience, tags, and visual assets channel-specific instead of reusing the same paragraph everywhere.'
    ]
  },
  scholardag: {
    label: 'Scholar DAG content graph',
    instructions: [
      'Build an internal content graph before writing: problem, method, evidence, visual proof, caveat, audience, and next action.',
      'Every platform variant should reuse that graph so claims stay semantically consistent across tweets, articles, carousels, and launch posts.',
      'When a claim depends on a figure, table, README command, demo, or project page, connect the claim to that source in promotionStrategy.contentGraph.'
    ]
  },
  human: {
    label: 'Human technical writing',
    instructions: [
      'Make each post feel like one person sharing one concrete observation, not a template trying to cover every feature.',
      'Use a natural rhythm: one short hook, one specific detail, one caveat or next action. Vary sentence length and avoid perfectly symmetric bullet patterns.',
      'Do not claim personal experience, ownership, excitement, or “I built/read/tried” unless the source or user context supports that voice.'
    ]
  },
  tweet: {
    label: 'X/Twitter post',
    instructions: [
      'Write each X/Twitter post around one angle only: launch, command, paper claim, visual proof, caveat, or reader fit.',
      'Put one concrete artifact in the first 80 Chinese characters or first 20 English words: command, repo link, paper title, figure, API route, screenshot, or file name.',
      'Keep single tweets compact and scannable: no more than two hashtags, no emoji by default, and avoid listing more than two platforms in one post.'
    ]
  },
  paper: {
    label: 'Paper promotion',
    instructions: [
      'For papers, structure the claim as: problem -> method or dataset -> evidence from abstract/figure/table -> why readers might care -> limitation.',
      'Do not invent benchmark numbers, baselines, ablation results, acceptance venue, affiliations, or code availability.',
      'Suggest screenshots from abstract, method figure, result table, and limitation paragraph when present.'
    ]
  },
  launch: {
    label: 'Open-source launch',
    instructions: [
      'For repositories, make the launch copy concrete: what it reads, what it generates, one command to try, and who should try it.',
      'Use release-style language only when the source contains release notes or a clear launch context.',
      'Avoid claiming adoption, popularity, or production readiness without evidence.'
    ]
  },
  launchkit: {
    label: 'Developer launch kit',
    instructions: [
      'Prepare channel-native launch material for LinkedIn, Product Hunt, Show HN, Reddit-style communities, and maintainer follow-up comments.',
      'Separate tagline, first comment, demo proof, install command, caveat, and feedback ask instead of compressing them into one social post.',
      'Do not fake traction, testimonials, rankings, votes, benchmarks, waitlists, logos, or customer names.'
    ]
  },
  technical: {
    label: 'Technical readers',
    instructions: [
      'Keep implementation-facing details visible: inputs, outputs, API shape, CLI command, provider integration, file evidence, and workflow boundaries.',
      'Use precise nouns instead of broad adjectives.',
      'Keep one version approachable, but make the technical version useful to engineers or researchers.'
    ]
  },
  zhihu: {
    label: 'Zhihu answer',
    instructions: [
      'Write the Zhihu variant as a credible answer: conclusion first, then context, method/workflow, evidence, limitations, and reader fit.',
      'Use paragraphs and section logic; avoid slogan-like openings.',
      'Include citationsToUse for screenshots, paper clips, result tables, README snippets, or commands.'
    ]
  },
  xhs: {
    label: 'Xiaohongshu note',
    instructions: [
      'Write the Xiaohongshu variant as a carousel note: 2-3 title options, cover text, 3-6 cards, concise body, and tags.',
      'Each carousel card should have one takeaway and one visual suggestion.',
      'Use a lighter Chinese tone, but keep all claims evidence-backed.'
    ]
  },
  wechat: {
    label: 'WeChat article',
    instructions: [
      'Write the WeChat Official Account variant as a complete article package: title, summary, cover text, section outline, and body.',
      'Use sections for introduction, problem, method/workflow, evidence/results, limitations, and reader fit.',
      'Keep Moments copy compact and conversational with one clear reason to open the source.'
    ]
  },
  visual: {
    label: 'Visual assets',
    instructions: [
      'Turn source evidence into visual plans: abstract crop, method figure, result table, README opening, terminal command, or product screenshot.',
      'Image ideas should specify layout, crop/source, caption, and why the visual supports the claim.',
      'Do not ask image models to draw fake logos, fake metrics, fake UI states, or fake paper results.'
    ]
  },
  paper2web: {
    label: 'Paper2Web presentation completeness',
    instructions: [
      'For paper-like sources, check whether the promotion has connectivity between the main claim, method, evidence, visual assets, and next action.',
      'Prefer complete, navigable presentation units: title, TL;DR, source proof, method/result explanation, caveat, and link or command.',
      'Use visualPlan and platformVariants to make the paper feel explorable rather than turning the abstract into one flat paragraph.'
    ]
  },
  thread: {
    label: 'Thread structure',
    instructions: [
      'Threads should have a clear progression: hook, source context, concrete mechanism, evidence, who should care, caveat, and next action.',
      'Every thread post should stand on one idea; avoid repeating the same tagline.',
      'Keep the first post independently publishable.'
    ]
  }
};

const DEFAULT_PROMPT_PRESETS = ['grounded', 'author', 'realworld', 'autopr', 'scholardag', 'human'];

export function promptPresetNames() {
  return Object.keys(PROMPT_PRESETS);
}

export function promptPresetCatalog() {
  return Object.fromEntries(
    Object.entries(PROMPT_PRESETS).map(([name, preset]) => [
      name,
      {
        label: preset.label,
        instructions: [...preset.instructions]
      }
    ])
  );
}

export function selectPromptPresets(value, options = {}) {
  const includeDefaults = options.includeDefaults ?? true;
  const names = [
    ...(includeDefaults ? DEFAULT_PROMPT_PRESETS : []),
    ...normalizePromptPresetNames(value)
  ];
  const seen = new Set();
  const selected = [];

  for (const name of names) {
    if (seen.has(name)) continue;
    const preset = PROMPT_PRESETS[name];
    if (!preset) {
      throw new Error(`Unknown prompt preset: ${name}. Available presets: ${promptPresetNames().join(', ')}`);
    }
    seen.add(name);
    selected.push({
      name,
      label: preset.label,
      instructions: [...preset.instructions]
    });
  }

  return selected;
}

export function normalizePromptPresetNames(value) {
  const values = Array.isArray(value) ? value : [value];
  return values
    .flatMap((item) => String(item ?? '').split(','))
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}
