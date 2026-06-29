const PROMOTION_SKILLS = {
  paper: {
    aliases: ['paper-promo', 'academic', 'academic-promo', 'research'],
    label: 'Paper promotion',
    description: 'Generate grounded promotion copy from a paper, PDF, abstract, or paper page.',
    platform: 'all',
    audience: 'researchers, engineers, and technical readers who may want to inspect the paper',
    tone: 'credible researcher reading note',
    promptPresets: ['paper', 'visual', 'paper2web', 'autopr', 'scholardag'],
    promptNotes: [
      'Treat the source as a paper-first promotion task. Extract problem, method, evidence, figures/tables, limitations, and reader fit before writing.',
      'For Chinese platforms, make Zhihu explanatory, Xiaohongshu carousel-oriented, and WeChat article-like. Do not turn the abstract into one flat paragraph.'
    ],
    reviewFocus: [
      'Paper claim fidelity',
      'Method/result evidence',
      'Figure or table selection',
      'Limitations and missing code caveats'
    ]
  },
  code: {
    aliases: ['repo', 'repository', 'code-launch', 'open-source', 'oss'],
    label: 'Open-source code launch',
    description: 'Generate launch copy from a GitHub repository or local code project.',
    platform: 'launch',
    audience: 'developers, maintainers, and technical early adopters',
    tone: 'open-source maintainer launch note',
    promptPresets: ['launch', 'launchkit', 'technical', 'visual', 'autopr', 'scholardag'],
    promptNotes: [
      'Treat the source as an open-source launch task. Keep input, output, install command, demo path, examples, and limitations visible.',
      'Product Hunt, Show HN, and LinkedIn variants must be structurally different instead of reusing one generic paragraph.'
    ],
    reviewFocus: [
      'Install or try path',
      'Concrete workflow',
      'README or demo proof',
      'No fake traction or production-readiness claims'
    ]
  },
  'paper-code': {
    aliases: ['code-paper', 'repo-paper', 'paper+code', 'research-code', 'joint'],
    label: 'Paper plus code promotion',
    description: 'Generate a unified promotion pack when a paper and its code/project are both available.',
    platform: 'all',
    audience: 'researchers, engineers, and builders who want both the idea and the runnable artifact',
    tone: 'research-to-code launch note',
    promptPresets: ['paper', 'launchkit', 'technical', 'visual', 'paper2web', 'autopr', 'scholardag'],
    promptNotes: [
      'Treat the primary target and --context sources as one release story. Explain the paper contribution and the runnable code path together.',
      'Do not merge facts blindly: say which claims come from the paper and which come from the repository, README, docs, or demo.',
      'Every platform variant should include both a research reason to read and a practical reason to try the code when evidence exists.'
    ],
    reviewFocus: [
      'Paper-to-code alignment',
      'Claim provenance',
      'Runnable path',
      'Visual evidence from paper figures and README/demo screenshots'
    ]
  },
  social: {
    aliases: ['social-pack', 'cross-platform', 'platform-pack'],
    label: 'Cross-platform social pack',
    description: 'Generate one source-grounded campaign across social platforms.',
    platform: 'all',
    audience: 'technical readers across social platforms',
    tone: 'platform-native technical sharing',
    promptPresets: ['tweet', 'zhihu', 'xhs', 'wechat', 'visual', 'autopr', 'scholardag'],
    promptNotes: [
      'Optimize for platform-native structure. Each platform should have its own hook, format, visual plan, and avoid-list.',
      'Keep the same factual content graph across platforms while adapting tone and layout.'
    ],
    reviewFocus: [
      'Platform alignment',
      'Shared factual graph',
      'Channel-specific hooks',
      'No platform-inappropriate copy reuse'
    ]
  },
  visual: {
    aliases: ['visual-pack', 'image-pack', 'asset-pack'],
    label: 'Visual promotion pack',
    description: 'Plan source-grounded visuals for paper figures, README screenshots, demos, and social cards.',
    platform: 'all',
    audience: 'readers who scan visuals before opening a source link',
    tone: 'visual-first technical explanation',
    promptPresets: ['visual', 'paper2web', 'paper', 'technical'],
    promptNotes: [
      'Prioritize visualNarrative and visualPlan. Name exact source clips, figures, tables, README snippets, or demo screenshots before suggesting generated images.',
      'Do not ask image models to invent results, logos, screenshots, UI states, or benchmark numbers.'
    ],
    reviewFocus: [
      'Source clip selection',
      'Visual-to-claim fit',
      'Platform image dimensions',
      'No fabricated visual evidence'
    ]
  },
  markdown: {
    aliases: ['project-doc', 'project-markdown', 'readme', 'docs', 'markdown-doc'],
    label: 'Project markdown generator',
    description: 'Generate a local Markdown document from project, repository, paper, or related-source evidence.',
    platform: null,
    audience: 'project maintainers and technical readers who need a reusable Markdown artifact',
    tone: 'clear source-grounded project documentation',
    promptPresets: ['technical', 'launch', 'visual'],
    promptNotes: [
      'Generate a Markdown artifact from source evidence before writing short-form social copy.',
      'Keep claims traceable to README, package metadata, examples, docs, paper, or related sources.'
    ],
    reviewFocus: [
      'Source-grounded sections',
      'README or launch-document completeness',
      'Install and demo accuracy',
      'No invented metrics or fake project status'
    ]
  }
};

const ALIAS_TO_SKILL = new Map();
for (const [name, skill] of Object.entries(PROMOTION_SKILLS)) {
  ALIAS_TO_SKILL.set(name, name);
  for (const alias of skill.aliases) ALIAS_TO_SKILL.set(alias, name);
}

export function promotionSkillNames() {
  return Object.keys(PROMOTION_SKILLS);
}

export function promotionSkillCatalog() {
  return Object.fromEntries(
    Object.entries(PROMOTION_SKILLS).map(([name, skill]) => [
      name,
      {
        aliases: [...skill.aliases],
        label: skill.label,
        description: skill.description,
        platform: skill.platform,
        audience: skill.audience,
        tone: skill.tone,
        promptPresets: [...skill.promptPresets],
        promptNotes: [...skill.promptNotes],
        reviewFocus: [...skill.reviewFocus]
      }
    ])
  );
}

export function normalizePromotionSkillNames(value) {
  const values = Array.isArray(value) ? value : [value];
  return values
    .flatMap((item) => String(item ?? '').split(','))
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

export function resolvePromotionSkills(value) {
  const names = normalizePromotionSkillNames(value);
  const seen = new Set();
  const resolved = [];

  for (const name of names) {
    const canonical = ALIAS_TO_SKILL.get(name);
    if (!canonical) {
      throw new Error(`Unknown skill: ${name}. Available skills: ${promotionSkillNames().join(', ')}`);
    }
    if (seen.has(canonical)) continue;
    seen.add(canonical);
    const skill = PROMOTION_SKILLS[canonical];
    resolved.push({
      name: canonical,
      aliases: [...skill.aliases],
      label: skill.label,
      description: skill.description,
      platform: skill.platform,
      audience: skill.audience,
      tone: skill.tone,
      promptPresets: [...skill.promptPresets],
      promptNotes: [...skill.promptNotes],
      reviewFocus: [...skill.reviewFocus]
    });
  }

  return resolved;
}

export function buildPromotionSkillPlan(value) {
  const skills = resolvePromotionSkills(value);
  return {
    skills,
    promptPresets: unique(skills.flatMap((skill) => skill.promptPresets)),
    promptNotes: skills.flatMap((skill) => skill.promptNotes),
    reviewFocus: unique(skills.flatMap((skill) => skill.reviewFocus)),
    defaultPlatform: firstPresent(skills.map((skill) => skill.platform)),
    defaultAudience: firstPresent(skills.map((skill) => skill.audience)),
    defaultTone: firstPresent(skills.map((skill) => skill.tone))
  };
}

export function applyPromotionSkills(options = {}) {
  const skillPlan = buildPromotionSkillPlan(options.skills ?? options.skill);
  if (skillPlan.skills.length === 0) {
    return {
      ...options,
      appliedSkills: [],
      skillPlan
    };
  }

  return {
    ...options,
    appliedSkills: skillPlan.skills,
    skillPlan,
    audience: options.audience ?? skillPlan.defaultAudience,
    platform: options.platform ?? options.promo ?? skillPlan.defaultPlatform ?? null,
    promptNotes: [
      ...skillPlan.promptNotes,
      ...(options.promptNotes ?? [])
    ],
    promptPresets: [
      ...skillPlan.promptPresets,
      ...(options.promptPresets ?? [])
    ],
    tone: options.tone ?? skillPlan.defaultTone
  };
}

export function formatPromotionSkillPlan(skillPlan) {
  if (!skillPlan?.skills?.length) return '';
  const lines = [];
  lines.push('Promotion skills');
  for (const skill of skillPlan.skills) {
    lines.push(`- ${skill.name}: ${skill.label}`);
    lines.push(`  ${skill.description}`);
  }
  if (skillPlan.defaultPlatform) lines.push(`Default platform: ${skillPlan.defaultPlatform}`);
  if (skillPlan.defaultAudience) lines.push(`Default audience: ${skillPlan.defaultAudience}`);
  if (skillPlan.defaultTone) lines.push(`Default tone: ${skillPlan.defaultTone}`);
  if (skillPlan.promptPresets.length > 0) lines.push(`Prompt presets: ${skillPlan.promptPresets.join(', ')}`);
  if (skillPlan.reviewFocus.length > 0) lines.push(`Review focus: ${skillPlan.reviewFocus.join(', ')}`);
  return lines.join('\n');
}

function firstPresent(values) {
  return values.find((value) => value !== undefined && value !== null && value !== '') ?? null;
}

function unique(values) {
  const seen = new Set();
  const result = [];
  for (const value of values) {
    if (!value || seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }
  return result;
}
