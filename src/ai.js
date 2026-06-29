import {
  agentConfig,
  buildAgentToolSystemAddendum,
  createDefaultToolExecutor,
  runToolAgent
} from './agent.js';
import {
  generateCacheKey,
  getCache,
  isCacheEnabled,
  setCache
} from './cache.js';
import { buildPromoBriefSection, resolvePromoBrief } from './promo-brief.js';
import { buildPromoSystemPrompt, buildPromoUserPrompt } from './promo-prompts.js';
import { selectPromptPresets } from './prompts.js';

const DEFAULT_BASE_URL = 'https://api.openai.com/v1';
const DEFAULT_MODEL = 'gpt-4.1-mini';
const MODELSCOPE_BASE_URL = 'https://api-inference.modelscope.cn/v1';
const MODELSCOPE_DEFAULT_MODEL = 'Qwen/Qwen3.5-397B-A17B';

export async function generateAiContent(result, options = {}) {
  const config = aiConfig(options);
  if ((options.audit || options.promo || options.brief) && !options.maxTokens) {
    config.maxTokens = Math.max(
      config.maxTokens,
      options.promo ? 5000 : options.brief ? 3200 : 2800
    );
  }

  // 缓存键生成（排除不稳定的选项）
  const cacheKey = generateCacheKey('ai', {
    projectName: result.project.name,
    projectDescription: result.project.description,
    readmeFirstScreen: result.evidence?.readmeFirstScreen?.slice(0, 500),
    score: result.score,
    mode: options.audit ? 'audit' : options.promo ? 'promo' : options.brief ? 'brief' : 'default',
    platform: options.platform ?? 'all',
    skills: options.skills ?? options.appliedSkills?.map?.((skill) => skill.name) ?? [],
    promptPresets: options.promptPresets ?? [],
    promptNotes: options.promptNotes ?? [],
    audience: options.audience ?? null,
    tone: options.tone ?? null,
    model: config.model,
    vision: config.vision
  });

  // 检查缓存
  if (isCacheEnabled() && !options.skipCache) {
    const cached = await getCache(cacheKey);
    if (cached) {
      return { ...cached, cached: true };
    }
  }

  const agent = agentConfig(options, options.env);
  const useAgentTools = Boolean(options.promo && agent.enabled && !config.stream);

  if (useAgentTools) {
    config.timeoutMs = Number(
      options.agentTimeoutMs
      ?? options.env?.SOURCE2LAUNCH_AGENT_TIMEOUT_MS
      ?? options.env?.STAR_UP_AGENT_TIMEOUT_MS
      ?? Math.max(config.timeoutMs, 240_000)
    );
    config.maxTokens = Math.max(config.maxTokens, 5000);
    const messages = buildAiMessages(result, { ...options, agentTools: true });
    const agentResult = await runToolAgent({
      callChat: (chatMessages, chatOptions = {}) => callChatCompletions(config, chatMessages, chatOptions),
      messages,
      executeTool: options.executeTool || createDefaultToolExecutor(options.agentContext ?? {}),
      tools: agent.enabledTools,
      maxSteps: agent.maxSteps
    });

    const aiResult = {
      provider: config.baseUrl,
      model: config.model,
      vision: config.vision,
      stream: config.stream,
      agentTools: true,
      toolCalls: agentResult.toolCalls,
      toolSteps: agentResult.steps,
      content: parseJsonContent(agentResult.content)
    };

    // 缓存结果（排除流式输出）
    if (isCacheEnabled() && !config.stream && !options.skipCache) {
      await setCache(cacheKey, aiResult);
    }

    return aiResult;
  }

  const messages = buildAiMessages(result, options);
  const response = await callChatCompletions(config, messages);
  const content = response.choices?.[0]?.message?.content;

  if (!content) {
    throw new Error('AI provider returned an empty response');
  }

  const aiResult = {
    provider: config.baseUrl,
    model: config.model,
    vision: config.vision,
    stream: config.stream,
    content: parseJsonContent(content)
  };

  // 缓存结果（排除流式输出）
  if (isCacheEnabled() && !config.stream && !options.skipCache) {
    await setCache(cacheKey, aiResult);
  }

  return aiResult;
}

export function aiConfig(options = {}, env = process.env) {
  const apiKey = options.apiKey
    || env.SOURCE2LAUNCH_API_KEY
    || env.STAR_UP_API_KEY
    || env.OPENAI_API_KEY
    || env.SOURCE2LAUNCH_MODELSCOPE_API_KEY
    || env.STAR_UP_MODELSCOPE_API_KEY
    || env.MODELSCOPE_API_KEY;

  if (!apiKey) {
    throw new Error('Missing API key. Set SOURCE2LAUNCH_API_KEY, OPENAI_API_KEY, or SOURCE2LAUNCH_MODELSCOPE_API_KEY.');
  }

  const modelscopeKey = Boolean(env.SOURCE2LAUNCH_MODELSCOPE_API_KEY || env.STAR_UP_MODELSCOPE_API_KEY || env.MODELSCOPE_API_KEY);
  const explicitBaseUrl = options.baseUrl || env.SOURCE2LAUNCH_BASE_URL || env.STAR_UP_BASE_URL || env.OPENAI_BASE_URL || '';
  const baseUrl = trimTrailingSlash(
    explicitBaseUrl
      || (modelscopeKey && !env.SOURCE2LAUNCH_API_KEY && !env.STAR_UP_API_KEY && !env.OPENAI_API_KEY ? MODELSCOPE_BASE_URL : DEFAULT_BASE_URL)
  );
  const modelscope = isModelScopeBaseUrl(baseUrl);
  const model = options.model
    || env.SOURCE2LAUNCH_MODEL
    || env.STAR_UP_MODEL
    || env.OPENAI_MODEL
    || (modelscope ? MODELSCOPE_DEFAULT_MODEL : DEFAULT_MODEL);

  const visionDefault = (env.SOURCE2LAUNCH_VISION ?? env.STAR_UP_VISION) !== 'false';
  const vision = options.vision ?? (options.noVision ? false : visionDefault);
  const stream = options.stream ?? (env.SOURCE2LAUNCH_STREAM ?? env.STAR_UP_STREAM) === 'true';
  const jsonMode = options.jsonMode ?? ((env.SOURCE2LAUNCH_JSON_MODE ?? env.STAR_UP_JSON_MODE) === 'false' ? false : !stream);

  return {
    apiKey,
    baseUrl,
    maxTokens: Number(options.maxTokens || env.SOURCE2LAUNCH_MAX_TOKENS || env.STAR_UP_MAX_TOKENS || (modelscope ? 4096 : 1800)),
    model,
    temperature: Number(options.temperature ?? env.SOURCE2LAUNCH_TEMPERATURE ?? env.STAR_UP_TEMPERATURE ?? 0.7),
    timeoutMs: Number(options.timeoutMs || env.SOURCE2LAUNCH_TIMEOUT_MS || env.STAR_UP_TIMEOUT_MS || (modelscope ? 120_000 : 45_000)),
    provider: modelscope ? 'modelscope' : 'openai-compatible',
    vision,
    stream,
    jsonMode
  };
}

export function extractImageUrlsFromEvidence(evidence) {
  if (Array.isArray(evidence?.visualUrls) && evidence.visualUrls.length > 0) {
    return evidence.visualUrls.slice(0, 3);
  }

  const urls = [];
  for (const visual of evidence?.visuals ?? []) {
    const markdownMatch = visual.match(/!\[[^\]]*]\(([^)]+)\)/);
    if (markdownMatch) {
      const candidate = markdownMatch[1].trim().split(/\s/)[0];
      if (/^https?:\/\//i.test(candidate)) urls.push(candidate);
      continue;
    }
    const htmlMatch = visual.match(/\bsrc=["']([^"']+)["']/i);
    if (htmlMatch && /^https?:\/\//i.test(htmlMatch[1])) urls.push(htmlMatch[1]);
  }

  return [...new Set(urls)].slice(0, 3);
}

export function buildUserMessageContent(text, options = {}) {
  const imageUrls = options.imageUrls ?? [];
  if (!options.vision || imageUrls.length === 0) {
    return text;
  }

  const parts = [{ type: 'text', text }];
  for (const url of imageUrls) {
    parts.push({
      type: 'image_url',
      image_url: { url }
    });
  }
  return parts;
}

export function buildAiMessages(result, options = {}) {
  const platform = normalizePlatform(options.platform ?? 'all');
  const promo = Boolean(options.promo);
  const audit = Boolean(options.audit);
  const projectBrief = Boolean(options.brief);
  const vision = resolveVisionEnabled(options);
  const imageUrls = vision ? extractImageUrlsFromEvidence(result.evidence) : [];
  const payload = {
    platform,
    project: result.project,
    heuristicScore: {
      score: result.score,
      grade: result.grade,
      note: '以下规则评分为辅助信号，请结合 README 原文与证据独立判断，不必照搬。'
    },
    repository: {
      stars: result.repository.stars,
      topics: result.repository.topics,
      latestRelease: result.repository.latestRelease,
      filesScanned: result.repository.filesScanned,
      readme: result.repository.readme
    },
    evidence: result.evidence ?? {},
    checks: result.checks.map((check) => ({
      id: check.id,
      label: check.label,
      score: check.score,
      max: check.max,
      summary: check.summary,
      findings: check.findings
    })),
    topFixes: result.topFixes
  };

  if (options.projectIntake?.summary) {
    payload.projectIntake = {
      summary: options.projectIntake.summary,
      documents: (options.projectIntake.documents ?? []).map((doc) => ({
        fileName: doc.fileName,
        method: doc.method,
        excerpt: doc.excerpt,
        markdown: doc.markdown?.slice(0, 4_000),
        sections: (doc.sections ?? []).slice(0, 8).map((section) => ({
          title: section.title ?? section.heading,
          excerpt: section.excerpt ?? section.content?.slice(0, 400)
        }))
      }))
    };
  }

  if (projectBrief) {
    const userText = [
      '请阅读以下开源仓库证据（及可选 PDF/文档），完成「项目理解与介绍」。',
      '你的任务是像资深维护者一样向新访客介绍这个项目：是什么、解决谁的问题、如何试用、与 README 相比还缺什么。',
      imageUrls.length > 0 ? '已附带 README 远程截图，请结合视觉首屏理解项目定位。' : '',
      options.projectIntake?.documents?.length ? '已附带 PDF/文本文档，请提炼可核实要点，勿编造文档未出现的能力。' : '',
      'heuristicScore 与 checks 仅作辅助信号，请独立阅读 evidence.readmeFirstScreen / readmeOpening，不要机械复述规则分数。',
      '',
      'JSON 输出结构必须是：',
      '{',
      '  "projectBrief": {',
      '    "oneLiner": "8-35 字中文一句话定位",',
      '    "overview": "2-4 句项目介绍",',
      '    "targetUsers": ["目标用户1", "目标用户2"],',
      '    "problem": "用户痛点",',
      '    "solution": "项目如何解决",',
      '    "howItWorks": "核心工作流（plain language）",',
      '    "differentiators": ["与同类差异1"],',
      '    "tryItNow": "访客第一步该做什么",',
      '    "starBlockers": [{"stage": "discovery|first-impression|trial|trust", "issue": "问题", "fix": "建议", "priority": "high|medium|low"}],',
      '    "promoHooks": [{"platform": "xhs|wechat|zhihu", "angle": "角度", "hook": "一句钩子"}],',
      '    "honestLimits": ["工具不能做什么"],',
      '    "confidence": "high|medium|low"',
      '  },',
      '  "documentInsights": [{"fileName": "文件名", "keyPoints": ["要点"]}],',
      '  "readmeSuggestions": {"oneLiner": "建议首屏一句话", "firstScreenMarkdown": "首屏 Markdown 草稿"}',
      '}',
      '',
      '要求：不编造收藏数/用户数/媒体报道；installCommand 若存在须原样写入 tryItNow 或 overview；不使用 emoji；只输出 JSON。',
      '',
      JSON.stringify(payload, null, 2)
    ].filter(Boolean).join('\n');

    return [
      {
        role: 'system',
        content: [
          '你是资深开源项目分析师与技术写作者，专门「读懂仓库并向访客介绍项目」。',
          '你会收到 README 原文、安装命令、目录信号、可选 PDF/文档，以及本地规则扫描的结构化证据。',
          '重点：用自然语言讲清项目价值与试用路径，而不是罗列体检维度或分数。',
          '只输出严格 JSON，不要 Markdown 代码块。'
        ].join('\n')
      },
      {
        role: 'user',
        content: buildUserMessageContent(userText, { imageUrls, vision })
      }
    ];
  }

  if (audit) {
    const userText = [
      '请对以下仓库做 AI 发布资料检查。',
      imageUrls.length > 0 ? '已附带 README 中的远程截图，请结合视觉首屏判断发布表达效果。' : '',
      options.projectIntake?.summary ? '已附带 PDF/文档阅读摘要（见 payload.projectIntake），请结合文档理解项目定位后再审计。' : '',
      '',
      'JSON 输出结构必须是：',
      '{',
      '  "audit": {',
      '    "confidence": "high|medium|low",',
      '    "summary": "一句话总结当前发布资料最大的表达瓶颈",',
      '    "visitorExperience": "模拟访客前 10 秒的真实感受",',
      '    "evidenceGap": "当前证据链最需要补齐的地方"',
      '  },',
      '  "dimensions": [',
      '    {"id": "readme-pitch", "label": "README 定位", "assessment": "评价", "fix": "建议"},',
      '    {"id": "visual-demo", "label": "视觉演示", "assessment": "评价", "fix": "建议"},',
      '    {"id": "install-command", "label": "安装路径", "assessment": "评价", "fix": "建议"},',
      '    {"id": "demo-usage", "label": "Demo 与使用", "assessment": "评价", "fix": "建议"},',
      '    {"id": "topics", "label": "发现性", "assessment": "评价", "fix": "建议"},',
      '    {"id": "examples", "label": "示例", "assessment": "评价", "fix": "建议"},',
      '    {"id": "first-screen", "label": "首屏表达", "assessment": "评价", "fix": "建议"},',
      '    {"id": "package-release", "label": "发布完整度", "assessment": "评价", "fix": "建议"}',
      '  ],',
      '  "blockers": [{"stage": "discovery|first-impression|trial|trust", "issue": "问题", "impact": "影响", "fix": "建议", "priority": "high|medium|low"}],',
      '  "improvementPlan": [{"priority": "high|medium|low", "issue": "问题", "fix": "建议", "estimatedImpact": "预期影响"}],',
      '  "readmeRewrite": {"oneLiner": "一句话定位", "firstScreenMarkdown": "首屏 Markdown 草稿"}',
      '}',
      '',
      JSON.stringify(payload, null, 2)
    ].filter(Boolean).join('\n');

    return [
      {
        role: 'system',
        content: [
          '你是资深开源发布顾问，专门判断「为什么访客看了仓库却不理解、不试用、不继续阅读」。',
          '你会收到 README 原文片段、安装命令、视觉引用、规则扫描结果等证据。',
          '请独立阅读 evidence.readmeFirstScreen 和 evidence.readmeOpening，不要展示分数或等级。',
          imageUrls.length > 0 ? '用户还附上了 README 截图，请结合视觉首屏评估转化效果。' : '',
          '重点关注：10 秒内能否看懂价值、是否想试用、是否有可信证据支撑发布文案。',
          '要求：具体、可执行、不编造功能、不承诺增长结果、不使用 emoji。',
          '只输出严格 JSON，不要 Markdown 代码块。'
        ].filter(Boolean).join('\n')
      },
      {
        role: 'user',
        content: buildUserMessageContent(userText, { imageUrls, vision })
      }
    ];
  }

  if (promo) {
    const promoBrief = resolvePromoBrief(options, options.env);
    const briefSection = buildPromoBriefSection(promoBrief);
    const systemParts = [buildPromoSystemPrompt()];
    const promptGuidance = buildPromptGuidance(options);
    if (promptGuidance) {
      systemParts.push('');
      systemParts.push('---');
      systemParts.push('');
      systemParts.push(promptGuidance);
    }
    if (options.agentTools) {
      systemParts.push('');
      systemParts.push('---');
      systemParts.push('');
      systemParts.push(buildAgentToolSystemAddendum());
    }

    return [
      { role: 'system', content: systemParts.join('\n') },
      {
        role: 'user',
        content: buildUserMessageContent(
          [
            buildPromoUserPrompt(payload, { platform, briefSection }),
            imageUrls.length > 0 ? '已附带 README 远程截图，请结合视觉首屏撰写更有画面感的推广文案。' : '',
            options.projectIntake?.summary ? '已附带 PDF/文档阅读摘要（见 payload.projectIntake），请优先从中提炼可核实卖点。' : '',
            options.agentTools ? '请先按需调用工具收集证据与参考，再输出最终 JSON。' : ''
          ].filter(Boolean).join('\n\n'),
          { imageUrls, vision }
        )
      }
    ];
  }

  const systemPrompt = [
    '你是一个资深开源项目分析师和中文技术内容编辑。',
    '你的任务是根据 Source2Launch 收集的仓库证据，给出仓库改进分析，并生成可以直接发布到小红书、微信朋友圈、微信公众号、知乎的中文推广文本。',
    '本地资料检查 heuristicScore 仅作参考；请独立阅读 README 与 evidence，不要机械复述分数或维度列表。',
    '推广文案写作规范：',
    '- 小红书：标题≤20字，正文300-800字，钩子开头，第一人称，聚焦1个场景',
    '- 微信：80-200字，朋友安利口吻',
    '- 知乎：1000-1800字，回答体，附 suggestedQuestions',
    '要求：具体、克制、可信，不夸大，不编造功能，不承诺增长结果，不使用 emoji。',
    '只输出严格 JSON，不要 Markdown 代码块，不要解释 JSON 之外的内容。'
  ].join('\n');

  const jsonSchema = [
    '{',
    '  "analysis": {',
    '    "summary": "一句话总结仓库当前传播状态",',
    '    "positioning": "更清晰的一句话定位",',
    '    "targetUsers": ["目标用户1", "目标用户2"],',
    '    "strongestAngles": ["最适合推广的角度1", "角度2"],',
    '    "improvementPlan": [{"priority": "high|medium|low", "issue": "问题", "fix": "修复建议"}]',
    '  },',
    '  "readmeRewrite": {',
    '    "oneLiner": "可以直接替换 README 首段的一句话定位",',
    '    "firstScreenMarkdown": "README 首屏 Markdown 草稿",',
    '    "quickstartMarkdown": "Quickstart 段落 Markdown 草稿"',
    '  },',
    '  "promotions": {',
    '    "xiaohongshu": {"titles": ["标题1", "标题2", "标题3"], "body": "正文", "tags": ["#标签"], "imageIdeas": ["配图建议"]},',
    '    "wechatMoments": {"body": "朋友圈正文"},',
    '    "wechatOfficial": {"title": "公众号标题", "summary": "摘要", "body": "公众号正文"},',
    '    "zhihu": {"title": "标题", "suggestedQuestions": ["适合回答的问题"], "body": "正文", "tags": ["#标签"]}',
    '  }',
    '}'
  ].join('\n');

  const platformHint = `只需要重点生成平台：${platform}。如果平台不是 all，其他平台字段也要给出简短可用版本。`;

  const promoBrief = resolvePromoBrief(options, options.env);
  const briefSection = buildPromoBriefSection(promoBrief);

  const userText = [
    '请基于以下仓库体检数据生成内容。',
    imageUrls.length > 0 ? '已附带 README 远程截图，请结合视觉首屏一起分析。' : '',
    '',
    briefSection,
    briefSection ? '' : null,
    'JSON 输出结构必须是：',
    jsonSchema,
    '',
    platformHint,
    '',
    JSON.stringify(payload, null, 2)
  ].filter(Boolean).join('\n');

  return [
    { role: 'system', content: systemPrompt },
    {
      role: 'user',
      content: buildUserMessageContent(userText, { imageUrls, vision })
    }
  ];
}

function buildPromptGuidance(options = {}) {
  const selectedPresets = selectPromptPresets(options.promptPresets ?? [], {
    includeDefaults: options.includeDefaultPromptPresets !== false
  });
  const lines = [];

  lines.push('## Source2Launch 任务控制层');
  lines.push('');
  lines.push('先形成稳定的推广策略，再生成各平台正文：source evidence -> core angle -> content graph -> platform adaptation -> review gate。');

  if (Array.isArray(options.appliedSkills) && options.appliedSkills.length > 0) {
    lines.push('');
    lines.push('### 已启用 Skill');
    for (const skill of options.appliedSkills) {
      lines.push(`- ${skill.name}: ${skill.label}`);
      if (skill.description) lines.push(`  - ${skill.description}`);
    }
  }

  if (options.audience || options.tone) {
    lines.push('');
    lines.push('### 受众与语气');
    if (options.audience) lines.push(`- Audience: ${options.audience}`);
    if (options.tone) lines.push(`- Tone: ${options.tone}`);
  }

  if (selectedPresets.length > 0) {
    lines.push('');
    lines.push('### Prompt Presets');
    for (const preset of selectedPresets) {
      lines.push(`- ${preset.name}: ${preset.label}`);
      for (const instruction of preset.instructions) {
        lines.push(`  - ${instruction}`);
      }
    }
  }

  if (Array.isArray(options.promptNotes) && options.promptNotes.length > 0) {
    lines.push('');
    lines.push('### 用户补充提示词');
    for (const note of options.promptNotes) {
      lines.push(`- ${String(note).trim()}`);
    }
  }

  if (Array.isArray(options.reviewFocus) && options.reviewFocus.length > 0) {
    lines.push('');
    lines.push('### Review Focus');
    for (const item of options.reviewFocus) lines.push(`- ${item}`);
  }

  return lines.join('\n');
}

export function hasAiKey(env = process.env) {
  return Boolean(
    env.SOURCE2LAUNCH_API_KEY
    || env.STAR_UP_API_KEY
    || env.OPENAI_API_KEY
    || env.SOURCE2LAUNCH_MODELSCOPE_API_KEY
    || env.STAR_UP_MODELSCOPE_API_KEY
    || env.MODELSCOPE_API_KEY
  );
}

export function pickAiKey(env = process.env) {
  return env.SOURCE2LAUNCH_API_KEY
    || env.STAR_UP_API_KEY
    || env.OPENAI_API_KEY
    || env.SOURCE2LAUNCH_MODELSCOPE_API_KEY
    || env.STAR_UP_MODELSCOPE_API_KEY
    || env.MODELSCOPE_API_KEY;
}

export function formatAiProjectBriefMarkdown(aiResult, result, intake = {}) {
  const content = aiResult?.content ?? {};
  const brief = content.projectBrief ?? {};
  const lines = [];

  lines.push('# 项目理解（AI）');
  lines.push('');
  lines.push(`> 项目：${result.project.name ?? 'unknown'} · 模型 ${aiResult?.model ?? 'unknown'} · 置信度 ${brief.confidence ?? '?'}`);
  if (Number.isFinite(result.score)) {
    lines.push('> 本地资料检查仅供 CI；正文由大模型独立阅读生成');
  }
  lines.push('');

  if (brief.oneLiner) {
    lines.push('## 一句话');
    lines.push(brief.oneLiner);
    lines.push('');
  }

  if (brief.overview) {
    lines.push('## 项目介绍');
    lines.push(brief.overview);
    lines.push('');
  }

  if (Array.isArray(brief.targetUsers) && brief.targetUsers.length > 0) {
    lines.push('## 适合谁');
    for (const user of brief.targetUsers) lines.push(`- ${user}`);
    lines.push('');
  }

  if (brief.problem || brief.solution) {
    lines.push('## 痛点与方案');
    if (brief.problem) lines.push(`- **痛点**：${brief.problem}`);
    if (brief.solution) lines.push(`- **方案**：${brief.solution}`);
    lines.push('');
  }

  if (brief.howItWorks) {
    lines.push('## 怎么工作');
    lines.push(brief.howItWorks);
    lines.push('');
  }

  if (result.project.installCommand || brief.tryItNow) {
    lines.push('## 立即试用');
    if (brief.tryItNow) lines.push(brief.tryItNow);
    if (result.project.installCommand) {
      lines.push('');
      lines.push('```sh');
      lines.push(result.project.installCommand);
      lines.push('```');
    }
    lines.push('');
  }

  if (Array.isArray(brief.differentiators) && brief.differentiators.length > 0) {
    lines.push('## 差异点');
    for (const item of brief.differentiators) lines.push(`- ${item}`);
    lines.push('');
  }

  if (Array.isArray(brief.starBlockers) && brief.starBlockers.length > 0) {
    lines.push('## Star 转化阻碍');
    for (const blocker of brief.starBlockers) {
      lines.push(`- [${blocker.priority ?? 'medium'}] ${blocker.stage ?? ''} · ${blocker.issue}`);
      if (blocker.fix) lines.push(`  → ${blocker.fix}`);
    }
    lines.push('');
  }

  if (Array.isArray(content.documentInsights) && content.documentInsights.length > 0) {
    lines.push('## 文档要点');
    for (const doc of content.documentInsights) {
      lines.push(`### ${doc.fileName ?? '文档'}`);
      for (const point of doc.keyPoints ?? []) lines.push(`- ${point}`);
      lines.push('');
    }
  }

  if (Array.isArray(brief.promoHooks) && brief.promoHooks.length > 0) {
    lines.push('## 推广切入点');
    for (const hook of brief.promoHooks) {
      lines.push(`- **${hook.platform ?? 'general'}** · ${hook.angle ?? ''}：${hook.hook ?? ''}`);
    }
    lines.push('');
  }

  if (Array.isArray(brief.honestLimits) && brief.honestLimits.length > 0) {
    lines.push('## 诚实边界');
    for (const limit of brief.honestLimits) lines.push(`- ${limit}`);
    lines.push('');
  }

  const rewrite = content.readmeSuggestions ?? {};
  if (rewrite.oneLiner || rewrite.firstScreenMarkdown) {
    lines.push('## README 首屏建议');
    if (rewrite.oneLiner) lines.push(`- 一句话：${rewrite.oneLiner}`);
    if (rewrite.firstScreenMarkdown) {
      lines.push('');
      lines.push(rewrite.firstScreenMarkdown);
    }
    lines.push('');
  }

  const localDocs = intake.documents ?? [];
  if (localDocs.length > 0 && (!content.documentInsights || content.documentInsights.length === 0)) {
    lines.push('## 附加文档摘录');
    for (const doc of localDocs) {
      lines.push(`### ${doc.fileName}`);
      if (doc.excerpt) lines.push(doc.excerpt);
      lines.push('');
    }
  }

  return lines.join('\n').trim();
}

export function resolveAiScore(aiResult, fallbackResult) {
  const audit = aiResult.content?.audit;
  if (audit && Number.isFinite(Number(audit.score))) {
    return {
      score: Number(audit.score),
      grade: audit.grade || gradeFromScore(Number(audit.score)),
      source: 'ai'
    };
  }

  const diagnosis = aiResult.content?.starDiagnosis;
  if (diagnosis && Number.isFinite(Number(diagnosis.score))) {
    return {
      score: Number(diagnosis.score),
      grade: diagnosis.grade || gradeFromScore(Number(diagnosis.score)),
      source: 'ai'
    };
  }

  return {
    score: fallbackResult.score,
    grade: fallbackResult.grade,
    source: 'heuristic'
  };
}

export function formatAiAuditContent(aiResult, result) {
  const content = aiResult.content;
  const audit = content.audit ?? {};
  const lines = [];
  lines.push('Source2Launch · AI 发布资料检查');
  lines.push('');
  lines.push(`目标    ${result.target}`);
  lines.push(`项目    ${result.project.name}`);
  if (audit.confidence) lines.push(`置信度  ${audit.confidence}`);

  if (Number.isFinite(result.score)) {
    lines.push('本地资料检查  已生成（仅供 CI / 资料完整度参考）');
  }
  if (audit.evidenceGap || audit.heuristicDelta) {
    lines.push('');
    lines.push(`证据缺口  ${audit.evidenceGap || audit.heuristicDelta}`);
  }

  if (audit.summary) {
    lines.push('');
    lines.push('结论');
    lines.push(`  ${audit.summary}`);
  }

  if (audit.visitorExperience) {
    lines.push('');
    lines.push('访客体验（前 10 秒）');
    lines.push(`  ${audit.visitorExperience}`);
  }

  if (Array.isArray(content.dimensions) && content.dimensions.length > 0) {
    lines.push('');
    lines.push('维度评估');
    for (const dimension of content.dimensions) {
      lines.push(`  ${String(dimension.label).padEnd(16)} ${dimension.assessment ?? '需要人工确认'}`);
      if (dimension.fix) lines.push(`         → ${dimension.fix}`);
    }
  }

  if (Array.isArray(content.blockers) && content.blockers.length > 0) {
    lines.push('');
    lines.push('Star 阻碍');
    for (const blocker of content.blockers) {
      lines.push(`  [${blocker.priority ?? 'medium'}] ${blocker.stage ?? ''} · ${blocker.issue}`);
      if (blocker.impact) lines.push(`         影响：${blocker.impact}`);
      lines.push(`         → ${blocker.fix}`);
    }
  }

  if (Array.isArray(content.improvementPlan) && content.improvementPlan.length > 0) {
    lines.push('');
    lines.push('改进计划');
    for (const item of content.improvementPlan) {
      lines.push(`  [${item.priority ?? 'medium'}] ${item.issue}`);
      lines.push(`         → ${item.fix}`);
      if (item.estimatedImpact) lines.push(`         预期：${item.estimatedImpact}`);
    }
  }

  if (content.readmeRewrite?.oneLiner) {
    lines.push('');
    lines.push('建议一句话定位');
    lines.push(`  ${content.readmeRewrite.oneLiner}`);
  }

  lines.push('');
  lines.push(`模型    ${aiResult.model}`);
  if (aiResult.vision) lines.push('视觉    已启用（README 远程截图）');
  lines.push('提示    需要推广文案请运行：source2launch promote . --platform all');

  return lines.join('\n');
}

export function formatAiContent(aiResult, options = {}) {
  const content = aiResult.content;
  const lines = [];
  lines.push(`AI analysis (${aiResult.model})`);

  if (content.analysis) {
    appendAnalysisSection(lines, content.analysis);
  }

  if (content.readmeRewrite) {
    appendReadmeRewrite(lines, content.readmeRewrite);
  }

  const platform = normalizePlatform(options.platform ?? 'all');
  const promotions = content.promotions ?? {};
  if (platform === 'all' || platform === 'xhs') {
    appendXiaohongshu(lines, promotions.xiaohongshu);
  }
  if (platform === 'all' || platform === 'wechat') {
    appendWechatMoments(lines, promotions.wechatMoments);
    appendWechatOfficial(lines, promotions.wechatOfficial);
  }

  return lines.join('\n');
}

function appendAnalysisSection(lines, analysis) {
  if (!analysis) return;
  lines.push('');
  lines.push('Analysis');
  if (analysis.summary) lines.push(`Summary: ${analysis.summary}`);
  if (analysis.positioning) lines.push(`Positioning: ${analysis.positioning}`);

  if (Array.isArray(analysis.targetUsers) && analysis.targetUsers.length > 0) {
    lines.push(`Target users: ${analysis.targetUsers.join(', ')}`);
  }

  if (Array.isArray(analysis.strongestAngles) && analysis.strongestAngles.length > 0) {
    lines.push('');
    lines.push('Strongest angles');
    for (const angle of analysis.strongestAngles) lines.push(`- ${angle}`);
  }

  if (Array.isArray(analysis.improvementPlan) && analysis.improvementPlan.length > 0) {
    lines.push('');
    lines.push('Improvement plan');
    for (const item of analysis.improvementPlan) {
      lines.push(`- [${item.priority ?? 'medium'}] ${item.issue}`);
      lines.push(`  Fix: ${item.fix}`);
      if (item.estimatedImpact) lines.push(`  Impact: ${item.estimatedImpact}`);
    }
  }
}

function appendReadmeRewrite(lines, readmeRewrite) {
  if (!readmeRewrite) return;
  lines.push('');
  lines.push('README rewrite');
  if (readmeRewrite.oneLiner) {
    lines.push('');
    lines.push('One-liner:');
    lines.push(readmeRewrite.oneLiner);
  }
  if (readmeRewrite.firstScreenMarkdown) {
    lines.push('');
    lines.push('First screen:');
    lines.push(readmeRewrite.firstScreenMarkdown);
  }
  if (readmeRewrite.quickstartMarkdown) {
    lines.push('');
    lines.push('Quickstart:');
    lines.push(readmeRewrite.quickstartMarkdown);
  }
}

export function parseJsonContent(content) {
  const trimmed = String(content).trim();
  const withoutFence = trimmed
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim();

  try {
    return JSON.parse(withoutFence);
  } catch {
    const start = withoutFence.indexOf('{');
    const end = withoutFence.lastIndexOf('}');
    if (start >= 0 && end > start) {
      return JSON.parse(withoutFence.slice(start, end + 1));
    }
    throw new Error('AI provider did not return valid JSON');
  }
}

async function callChatCompletions(config, messages, chatOptions = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.timeoutMs);

  try {
    const body = {
      model: config.model,
      messages,
      temperature: config.temperature,
      max_tokens: config.maxTokens,
      stream: config.stream
    };

    if (Array.isArray(chatOptions.tools) && chatOptions.tools.length > 0) {
      body.tools = chatOptions.tools;
      body.tool_choice = chatOptions.toolChoice ?? 'auto';
    } else if ((chatOptions.jsonMode ?? config.jsonMode) && !config.stream) {
      body.response_format = { type: 'json_object' };
    }

    const response = await fetch(`${config.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body),
      signal: controller.signal
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`AI provider request failed (${response.status}): ${text.slice(0, 500)}`);
    }

    if (config.stream) {
      const content = await readStreamedContent(response);
      return {
        choices: [{ message: { content } }]
      };
    }

    const text = await response.text();
    return JSON.parse(text);
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error(`AI provider request timed out after ${config.timeoutMs}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function readStreamedContent(response) {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('Streaming response body is unavailable');
  }

  const decoder = new TextDecoder();
  let buffer = '';
  let content = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) continue;
      const payload = trimmed.slice(5).trim();
      if (!payload || payload === '[DONE]') continue;

      try {
        const chunk = JSON.parse(payload);
        const delta = chunk.choices?.[0]?.delta?.content;
        if (delta) content += delta;
      } catch {
        // Ignore malformed SSE chunks.
      }
    }
  }

  if (!content) {
    throw new Error('AI provider stream returned empty content');
  }

  return content;
}

function isModelScopeBaseUrl(baseUrl) {
  return /modelscope\.cn/i.test(String(baseUrl ?? ''));
}

function resolveVisionEnabled(options = {}, env = process.env) {
  if (options.noVision) return false;
  if (options.vision) return true;
  return (env.SOURCE2LAUNCH_VISION ?? env.STAR_UP_VISION) !== 'false';
}

function appendProductHunt(lines, ph) {
  if (!ph) return;
  lines.push('');
  lines.push('Product Hunt');
  if (ph.tagline) lines.push(`Tagline: ${ph.tagline}`);
  if (ph.firstComment) {
    lines.push('');
    lines.push(ph.firstComment);
  }
}

function appendShowHn(lines, hn) {
  if (!hn) return;
  lines.push('');
  lines.push('Show HN');
  if (hn.title) lines.push(`Title: ${hn.title}`);
  if (hn.body) {
    lines.push('');
    lines.push(hn.body);
  }
}

function appendTwitter(lines, twitter) {
  if (!twitter) return;
  lines.push('');
  lines.push('Twitter / X');
  if (Array.isArray(twitter.posts)) {
    for (const [index, post] of twitter.posts.entries()) {
      lines.push(`${index + 1}/${twitter.posts.length}: ${post}`);
    }
  }
}

function appendReddit(lines, reddit) {
  if (!reddit) return;
  lines.push('');
  lines.push('Reddit / V2EX');
  if (reddit.title) lines.push(`Title: ${reddit.title}`);
  if (reddit.body) {
    lines.push('');
    lines.push(reddit.body);
  }
}

function appendXiaohongshu(lines, xhs) {
  if (!xhs) return;
  lines.push('');
  lines.push('Xiaohongshu');
  if (Array.isArray(xhs.titles) && xhs.titles.length > 0) {
    lines.push('Titles:');
    for (const title of xhs.titles) lines.push(`- ${title}`);
  }
  if (xhs.body) {
    lines.push('');
    lines.push(xhs.body);
  }
  if (Array.isArray(xhs.tags) && xhs.tags.length > 0) {
    lines.push('');
    lines.push(`Tags: ${xhs.tags.join(' ')}`);
  }
  if (Array.isArray(xhs.imageIdeas) && xhs.imageIdeas.length > 0) {
    lines.push('');
    lines.push('Image ideas');
    for (const idea of xhs.imageIdeas) lines.push(`- ${idea}`);
  }
}

function appendWechatMoments(lines, moments) {
  if (!moments?.body) return;
  lines.push('');
  lines.push('WeChat Moments');
  lines.push(moments.body);
}

function appendWechatOfficial(lines, official) {
  if (!official) return;
  lines.push('');
  lines.push('WeChat Official Account');
  if (official.title) lines.push(`Title: ${official.title}`);
  if (official.summary) lines.push(`Summary: ${official.summary}`);
  if (official.body) {
    lines.push('');
    lines.push(official.body);
  }
}

function normalizePlatform(platform) {
  const normalized = String(platform ?? 'all').trim().toLowerCase();
  if (['xhs', 'xiaohongshu', 'red', 'rednote'].includes(normalized)) return 'xhs';
  if (['wechat', 'weixin', 'wx'].includes(normalized)) return 'wechat';
  return 'all';
}

function trimTrailingSlash(value) {
  return String(value).replace(/\/+$/, '');
}

function gradeFromScore(score) {
  if (score >= 85) return 'A';
  if (score >= 70) return 'B';
  if (score >= 55) return 'C';
  if (score >= 40) return 'D';
  return 'F';
}
