import { appendCoverImageSection } from './promo-shared.js';

const PLATFORM_LABELS = {
  all: 'All platforms',
  wechat: 'WeChat',
  xhs: 'Xiaohongshu',
  zhihu: 'Zhihu'
};

export function formatPromoUnavailable(projectName, platformLabel) {
  return [
    `# ${projectName} · ${platformLabel}`,
    '',
    '> 尚未生成',
    '',
    '推广文案由 AI 根据 README 与仓库证据生成，不使用固定模板。',
    '',
    '请配置 API Key 后重新运行：',
    '',
    '```sh',
    'export SOURCE2LAUNCH_MODELSCOPE_API_KEY="ms-your-token"',
    'source2launch optimize . --output launch-assets/',
    '# 或单独生成',
    'source2launch promote . --platform xhs',
    '```',
    '',
    '需要全平台内容时使用 `source2launch promote . --platform all`。'
  ].join('\n');
}

export function formatXhsPromoMarkdown(result, options = {}) {
  const ai = options.ai;
  if (ai?.markdown) {
    return appendCoverToMarkdown(ai.markdown, options.coverImage, '小红书');
  }
  if (ai) return appendCoverToMarkdown(formatXhsFromFields(result, ai), options.coverImage, '小红书');
  return formatPromoUnavailable(result.project.name, '小红书');
}

export function formatWechatPromoMarkdown(result, options = {}) {
  const ai = options.ai;
  if (ai?.markdown) {
    return appendCoverToMarkdown(ai.markdown, options.coverImage, '微信');
  }
  if (ai?.body) {
    return appendCoverToMarkdown(formatWechatFromBody(result, ai.body), options.coverImage, '微信');
  }
  return formatPromoUnavailable(result.project.name, '微信');
}

export function formatZhihuPromoMarkdown(result, options = {}) {
  const ai = options.ai;
  if (ai?.markdown) return ai.markdown.trim();
  if (ai) return formatZhihuFromFields(result, ai);
  return formatPromoUnavailable(result.project.name, '知乎');
}

export function formatPromoEnMarkdown(result, promotions = {}) {
  const lines = [];
  const project = result.project.name;

  lines.push(`# ${project} · 英文平台推广`);
  lines.push('');
  lines.push('> AI 生成 · Show HN / Twitter / Reddit / Product Hunt');

  if (promotions.showHn?.markdown) {
    lines.push('');
    lines.push(promotions.showHn.markdown.trim());
  } else if (promotions.showHn) {
    lines.push('');
    lines.push('## Show HN');
    if (promotions.showHn.title) lines.push(`**Title:** ${promotions.showHn.title}`);
    if (promotions.showHn.body) lines.push('', promotions.showHn.body);
  }

  if (promotions.twitter?.markdown) {
    lines.push('');
    lines.push(promotions.twitter.markdown.trim());
  }

  if (promotions.reddit?.markdown) {
    lines.push('');
    lines.push(promotions.reddit.markdown.trim());
  }

  if (promotions.productHunt?.markdown) {
    lines.push('');
    lines.push(promotions.productHunt.markdown.trim());
  }

  if (lines.length <= 4) {
    return formatPromoUnavailable(project, '英文平台');
  }

  return lines.join('\n');
}

export function formatPromoCopyMarkdown(result, aiContent, options = {}) {
  const lines = [];
  const promotions = aiContent?.promotions ?? {};
  const project = result.project.name;

  lines.push(`# ${project} · 推广文案索引`);
  lines.push('');
  lines.push('> AI 生成 · 各平台完整正文见对应文件');

  if (aiContent?.positioning) {
    lines.push('');
    lines.push(`**定位：** ${aiContent.positioning}`);
  }

  if (Array.isArray(aiContent?.targetUsers) && aiContent.targetUsers.length > 0) {
    lines.push(`**目标用户：** ${aiContent.targetUsers.join('、')}`);
  }

  if (Array.isArray(aiContent?.strongestAngles) && aiContent.strongestAngles.length > 0) {
    lines.push('');
    lines.push('**推广角度：**');
    for (const angle of aiContent.strongestAngles) lines.push(`- ${angle}`);
  }

  if (aiContent?.promotionStrategy?.coreAngle) {
    lines.push('');
    lines.push('## Promotion Strategy');
    lines.push('');
    lines.push(`**Core angle:** ${aiContent.promotionStrategy.coreAngle}`);
    appendQualityRubric(lines, aiContent.promotionStrategy.qualityRubric);
    const reviewGate = aiContent.promotionStrategy.reviewGate ?? {};
    const reviewQuestions = [
      ...(reviewGate.fidelityQuestions ?? []),
      ...(reviewGate.engagementQuestions ?? []),
      ...(reviewGate.platformQuestions ?? [])
    ];
    if (reviewQuestions.length > 0) {
      lines.push('');
      lines.push('**人工审核问题：**');
      for (const question of reviewQuestions.slice(0, 8)) lines.push(`- ${question}`);
    }
  }

  lines.push('');
  lines.push('## 平台文件');
  lines.push('');
  lines.push('- [platform/xhs.md](./platform/xhs.md) — 小红书');
  lines.push('- [platform/wechat.md](./platform/wechat.md) — 微信朋友圈');
  lines.push('- [platform/zhihu.md](./platform/zhihu.md) — 知乎');
  lines.push('- [platform/show-hn.md](./platform/show-hn.md) — Show HN');
  lines.push('- [platform/producthunt-kit.md](./platform/producthunt-kit.md) — Product Hunt');
  lines.push('');
  lines.push('兼容旧路径：`promo-xhs.md` / `promo-wechat.md` / `promo-zhihu.md` / `promo-en.md` 仍会生成。');

  if (promotions.xiaohongshu?.titles?.length > 0) {
    lines.push('');
    lines.push('## 小红书标题备选');
    for (const title of promotions.xiaohongshu.titles) lines.push(`- ${title}`);
  }

  if (Array.isArray(aiContent?.launchSequence) && aiContent.launchSequence.length > 0) {
    lines.push('');
    lines.push('## 建议发布顺序');
    for (const step of aiContent.launchSequence) {
      const wait = step.ready === false ? '（暂缓）' : '';
      lines.push(`${step.order}. **${step.channel}**${wait} — ${step.reason}`);
    }
  }

  if (options.coverImage) {
    appendCoverImageSection(lines, options.coverImage, '小红书');
  }

  return lines.join('\n');
}

function appendQualityRubric(lines, qualityRubric = {}) {
  const axes = [
    ['Fidelity', qualityRubric.fidelity],
    ['Engagement', qualityRubric.engagement],
    ['Alignment', qualityRubric.alignment]
  ];
  if (!axes.some(([, axis]) => axis)) return;

  lines.push('');
  lines.push('**Quality rubric:**');
  for (const [label, axis] of axes) {
    if (!axis) continue;
    const checks = Array.isArray(axis.checks) ? axis.checks : [];
    const risks = Array.isArray(axis.risks) ? axis.risks : [];
    const improvements = Array.isArray(axis.improvements) ? axis.improvements : [];
    lines.push(`- ${label}: ${checks.slice(0, 2).join('；') || '待人工确认'}`);
    if (risks[0]) lines.push(`  - Risk: ${risks[0]}`);
    if (improvements[0]) lines.push(`  - Improve: ${improvements[0]}`);
  }
}

/** @deprecated 保留 CLI 兼容，optimize 已改用 AI markdown */
export function generatePromotion(result, platform = 'all') {
  return {
    platform,
    project: result.project.name,
    unavailable: true,
    message: '请使用 source2launch promote 或 source2launch optimize 生成 AI 推广文案'
  };
}

/** @deprecated */
export function formatPromotion(promotion) {
  return promotion.message ?? '请配置 API Key 后运行 source2launch optimize . --output launch-assets/';
}

function formatXhsFromFields(result, ai) {
  const lines = [];
  lines.push(`# ${result.project.name} · 小红书推广`);
  lines.push('');
  lines.push('> AI 生成');
  if (Array.isArray(ai.titles) && ai.titles.length > 0) {
    lines.push('');
    lines.push('## 标题备选');
    for (const title of ai.titles) lines.push(`- ${title}`);
  }
  lines.push('');
  lines.push('## 正文');
  lines.push('');
  lines.push(ai.body ?? '');
  if (Array.isArray(ai.tags) && ai.tags.length > 0) {
    lines.push('');
    lines.push(`**标签：** ${ai.tags.join(' ')}`);
  }
  return lines.join('\n');
}

function formatWechatFromBody(result, body) {
  return [
    `# ${result.project.name} · 微信朋友圈`,
    '',
    '> AI 生成',
    '',
    body
  ].join('\n');
}

function formatZhihuFromFields(result, ai) {
  const lines = [];
  lines.push(`# ${result.project.name} · 知乎`);
  lines.push('');
  lines.push('> AI 生成');
  if (Array.isArray(ai.suggestedQuestions) && ai.suggestedQuestions.length > 0) {
    lines.push('');
    lines.push('## 建议回答的问题');
    for (const question of ai.suggestedQuestions) lines.push(`- ${question}`);
  }
  if (ai.title) {
    lines.push('');
    lines.push(`## ${ai.title}`);
  }
  lines.push('');
  lines.push(ai.body ?? '');
  if (Array.isArray(ai.tags) && ai.tags.length > 0) {
    lines.push('');
    lines.push(ai.tags.join(' '));
  }
  return lines.join('\n');
}

function appendCoverToMarkdown(markdown, coverImage, platformLabel) {
  const trimmed = String(markdown).trimEnd();
  if (!coverImage) return `${trimmed}\n`;
  const lines = trimmed.split('\n');
  appendCoverImageSection(lines, coverImage, platformLabel);
  return `${lines.join('\n')}\n`;
}
