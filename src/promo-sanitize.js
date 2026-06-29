/**
 * 推广文案后处理：修复 AI 常见硬伤，对齐真实平台写法
 */

const BANNED_PHRASES = [
  [/首先[,，]/g, ''],
  [/其次[,，]/g, ''],
  [/最后[,，]/g, ''],
  [/综上所述[,，]?/g, ''],
  [/值得一提的是[,，]?/g, ''],
  [/在当今数字化/g, ''],
  [/赋能/g, '帮'],
  [/助力/g, '帮'],
  [/浅谈/g, '聊'],
  [/分享一个/g, '发现个'],
  [/推荐一个/g, '最近在用'],
  [/一键神器/g, '挺省事'],
  [/必备/g, ''],
  [/必备工具/g, '小工具'],
  [/数据显示[,，]/g, '说实话，'],
  [/tanpa\s+V/gi, 'without V'],
  [/without\s+V/gi, 'without extra friction']
];

const UNVERIFIED_PATTERNS = [
  /第二天(?:就)?多了\s*\d+\s*个\s*[Ss]tar/g,
  /省了(?:我)?(?:半|一)?(?:个)?小时/g,
  /(?:涨了|多了)\s*\d+\s*万(?:用户|star)/gi
];

export function sanitizePromoContent(content, result = {}) {
  if (!content || typeof content !== 'object') return content;

  const installCommand = result.project?.installCommand ?? 'npx source2launch promote . --platform all';
  const promotions = content.promotions ?? {};
  const sanitized = { ...content, promotions: { ...promotions } };

  if (promotions.xiaohongshu) {
    sanitized.promotions.xiaohongshu = sanitizeXhs(
      { ...promotions.xiaohongshu },
      { installCommand, titles: promotions.xiaohongshu.titles }
    );
  }

  if (promotions.wechatMoments) {
    sanitized.promotions.wechatMoments = sanitizeWechat(
      { ...promotions.wechatMoments },
      { installCommand, repoUrl: result.project?.repositoryUrl }
    );
  }

  if (promotions.zhihu) {
    sanitized.promotions.zhihu = sanitizeZhihu(
      { ...promotions.zhihu },
      { installCommand }
    );
  }

  if (promotions.showHn?.markdown) {
    sanitized.promotions.showHn = {
      ...promotions.showHn,
      markdown: sanitizeMarkdown(promotions.showHn.markdown, { installCommand })
    };
  }

  return sanitized;
}

function sanitizeXhs(xhs, ctx) {
  let md = sanitizeMarkdown(xhs.markdown ?? '', ctx);
  md = normalizeCommandBlock(md, ctx.installCommand);
  md = ensureXhsStructure(md, ctx.titles, ctx.installCommand);
  md = ensureShortParagraphs(md);
  md = ensureXhsEmoji(md);
  if (Array.isArray(xhs.titles)) {
    xhs.titles = xhs.titles.map((title) => sanitizeMarkdown(title, ctx));
  }
  return { ...xhs, titles: xhs.titles, markdown: md };
}

function sanitizeWechat(wechat, ctx) {
  let md = sanitizeMarkdown(wechat.markdown ?? '', ctx);
  md = normalizeCommandBlock(md, ctx.installCommand);
  md = formatWechatLineBreaks(md);
  md = md.replace(/\bstar_up\s{2,}audit\b/gi, 'Source2Launch 扫了一下');
  md = md.replace(/8\s*维(?:评分|体检)?/g, '几个检查项');
  return { ...wechat, markdown: md };
}

function sanitizeZhihu(zhihu, ctx) {
  let md = sanitizeMarkdown(zhihu.markdown ?? '', ctx);
  md = normalizeCommandBlock(md, ctx.installCommand);
  md = md.replace(/star_up\s*\.\s*--boost/g, 'source2launch optimize . --output launch-assets/');
  md = md.replace(/star_up\s*\.\s*--optimize/g, 'source2launch optimize . --output launch-assets/');
  md = md.replace(/8\s*维(?:评分|体检)?/g, '多维度检查');
  md = ensureZhihuStructure(md, zhihu.suggestedQuestions);
  return { ...zhihu, markdown: md };
}

export function sanitizeMarkdown(text, ctx = {}) {
  let value = String(text ?? '');

  for (const pattern of UNVERIFIED_PATTERNS) {
    value = value.replace(pattern, '');
  }

  for (const [pattern, replacement] of BANNED_PHRASES) {
    value = value.replace(pattern, replacement);
  }

  value = value.replace(/8\s*个维(?:度)?/g, '几个关键检查项');
  value = value.replace(/8\s*维(?:评分|体检)?/g, '几个检查项');
  value = value.replace(/8-dim(?:ension)?(?:\s+audit)?/gi, 'multi-check audit');
  value = value.replace(/8\s*dims/gi, 'key checks');

  value = value.replace(/\s{3,}/g, ' ');
  value = value.replace(/\n{3,}/g, '\n\n');
  return value.trim();
}

function normalizeCommandBlock(md, installCommand) {
  const cmd = String(installCommand ?? 'npx source2launch promote . --platform all').trim();
  let out = md.replace(/```sh\n[\s\S]*?```/g, (block) => {
    const lines = [
      '```sh',
      cmd,
      'source2launch optimize . --output launch-assets/   # 生成发布资料包',
      '```'
    ];
    return lines.join('\n');
  });
  out = out.replace(/star_up\s*\.\s*--boost/g, 'source2launch optimize . --output launch-assets/');
  out = out.replace(/star_up\s*\.\s*--optimize/g, 'source2launch optimize . --output launch-assets/');
  return dedupeCommandBlocks(out, cmd);
}

function ensureXhsStructure(md, titles, installCommand = 'npx source2launch promote . --platform all') {
  let out = md;
  const cmdBlock = ['```sh', installCommand, 'source2launch optimize . --output launch-assets/', '```'].join('\n');

  if (!/```sh/m.test(out)) {
    if (/##\s*标签/m.test(out)) {
      out = out.replace(/(##\s*标签)/, `${cmdBlock}\n\n$1`);
    } else if (/##\s*发布提示/m.test(out)) {
      out = out.replace(/(##\s*发布提示)/, `${cmdBlock}\n\n$1`);
    } else {
      out += `\n\n${cmdBlock}\n`;
    }
  }

  out = out.replace(/\n(```sh[\s\S]*?```)\n\n(##\s*推广配图)/g, '\n\n$2');
  out = dedupeCommandBlocks(out, installCommand);
  if (!/##\s*标题备选/m.test(out) && Array.isArray(titles) && titles.length > 0) {
    const titleBlock = ['## 标题备选', ...titles.slice(0, 3).map((t) => `- ${t}`), ''].join('\n');
    out = out.replace(/(##\s*正文)/, `${titleBlock}$1`);
  }
  if (!/^#\s/m.test(out)) {
    out = `# Source2Launch · 小红书推广\n> 可直接复制发布\n\n${out}`;
  }
  if (!/##\s*标签/m.test(out)) {
    out += '\n\n## 标签\n#开源 #GitHub #程序员 #独立开发 #README\n';
  }
  return out;
}

function ensureXhsEmoji(md) {
  if (/[\u{1F300}-\u{1FAFF}]/u.test(md)) return md;
  return md.replace(/(##\s*正文\n\n?)([^\n#`]+)/m, (match, header, line) => {
    if (/[\u{1F300}-\u{1FAFF}]/u.test(line)) return match;
    const trimmed = line.trimEnd();
    const suffix = trimmed.endsWith('？') || trimmed.endsWith('?') ? ' 😅' : ' 😭';
    return `${header}${trimmed}${suffix}`;
  });
}

function dedupeCommandBlocks(md, installCommand) {
  const blocks = [...md.matchAll(/```sh\n[\s\S]*?```/g)];
  if (blocks.length <= 1) return md;
  let first = true;
  return md.replace(/```sh\n[\s\S]*?```/g, (block) => {
    if (first) {
      first = false;
      return block;
    }
    return '';
  }).replace(/\n{3,}/g, '\n\n');
}

function ensureShortParagraphs(md) {
  return md.split('\n\n').map((block) => {
    if (block.startsWith('#') || block.startsWith('```') || block.startsWith('>')) return block;
    const sentences = block.split(/(?<=[。！？!?])\s*/).filter(Boolean);
    if (sentences.length <= 3) return block;
    return sentences.map((s) => s.trim()).join('\n\n');
  }).join('\n\n');
}

function formatWechatLineBreaks(md) {
  return md.replace(
    /(##\s*风格\s*[ABC]\s*·[^\n]+\n)([^\n#]+)/g,
    (_, header, body) => {
      const urlMatch = body.match(/(https?:\/\/[^\s]+)\s*$/);
      const url = urlMatch?.[1] ?? '';
      const text = body.replace(/\s*https?:\/\/[^\s]+\s*$/, '').trim();
      const parts = text.split(/(?<=[。！？!?])\s*/).filter(Boolean);
      const lines = parts.length > 1 ? parts : splitWechatSentences(text);
      const formatted = lines.map((line) => line.trim()).join('\n\n');
      return `${header}${formatted}${url ? `\n\n${url}` : ''}`;
    }
  );
}

function splitWechatSentences(text) {
  const chunks = [];
  let rest = text;
  while (rest.length > 80) {
    const cut = rest.lastIndexOf('。', 80);
    const idx = cut > 20 ? cut + 1 : 80;
    chunks.push(rest.slice(0, idx).trim());
    rest = rest.slice(idx).trim();
  }
  if (rest) chunks.push(rest);
  return chunks;
}

function ensureZhihuStructure(md, suggestedQuestions) {
  let out = md;
  if (!/##\s*快速上手/m.test(out)) {
    const quickStart = [
      '## 快速上手',
      '',
      '```sh',
      'npx source2launch promote . --platform zhihu',
      'source2launch optimize . --output launch-assets/',
      '```',
      ''
    ].join('\n');
    if (/##\s*升华/m.test(out)) {
      out = out.replace(/(##\s*升华)/, `${quickStart}$1`);
    } else {
      out = `${out.trim()}\n\n${quickStart}`;
    }
  }
  if (Array.isArray(suggestedQuestions) && suggestedQuestions.length > 0 && !/##\s*建议回答的问题/m.test(out)) {
    const block = [
      '## 建议回答的问题',
      ...suggestedQuestions.slice(0, 3).map((q) => `- ${q}`),
      ''
    ].join('\n');
    out = `${out.trim()}\n\n${block}`;
  }
  if (!/#(?:开源|GitHub)/m.test(out)) {
    out += '\n\n#开源 #GitHub #程序员 #独立开发\n';
  }
  return out;
}

export function resolveEffectiveImageModel(env = process.env, hasReference = false) {
  const configured = env.SOURCE2LAUNCH_IMAGE_MODEL || env.STAR_UP_IMAGE_MODEL || env.MODELSCOPE_IMAGE_MODEL || 'Qwen/Qwen-Image';
  if (/edit|firered/i.test(configured) && !hasReference) {
    return 'Qwen/Qwen-Image';
  }
  return configured;
}
