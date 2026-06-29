import { promises as fs } from 'node:fs';
import path from 'node:path';

import { formatAiAuditContent, generateAiContent, resolveAiScore } from './ai.js';
import { formatReport } from './report.js';
import { formatLaunchPack, generateLaunchPack } from './launch.js';
import { buildPromoImagePrompt, generateImage, imageGenAvailable, modelscopeImageRequiresReference, resolveImageProvider, resolveModelscopeImageModel } from './modelscope.js';
import {
  formatPromoCopyMarkdown,
  formatPromoEnMarkdown,
  formatPromoUnavailable,
  formatWechatPromoMarkdown,
  formatXhsPromoMarkdown,
  formatZhihuPromoMarkdown
} from './promo.js';
import { resolvePromoBrief } from './promo-brief.js';
import { resolvePromoImageContext } from './promo-shared.js';
import { formatReadmeSuggestions, generateReadmeSuggestions } from './readme.js';
import { buildProjectIntakeWithAi } from './project-brief.js';
import { resolveEffectiveImageModel, sanitizePromoContent } from './promo-sanitize.js';
import { renderTemplate } from './template.js';
import {
  buildCampaign,
  formatContentReview,
  formatProductHuntKit,
  formatShowHnDraft
} from './campaign.js';

const DEFAULT_OUTPUT_DIR = 'launch-assets';

export async function runOptimize(result, options = {}) {
  const cwd = options.cwd || process.cwd();
  const outputDir = path.resolve(cwd, options.outputDir || options.optimizeDir || DEFAULT_OUTPUT_DIR);
  const imagesDir = path.join(outputDir, 'images');

  await fs.mkdir(imagesDir, { recursive: true });
  const launchPack = generateLaunchPack(result);

  const manifest = {
    project: result.project.name,
    outputDir,
    score: result.score,
    grade: result.grade,
    generated: [],
    skipped: [],
    promoSource: 'unavailable',
    images: {},
    mode: resolveOptimizeMode(options)
  };

  if (shouldWriteHeuristicAssets(options)) {
    await writeAsset(outputDir, 'heuristic-audit.md', formatReport(result), manifest);
    await writeAsset(
      outputDir,
      'readme-suggestions.md',
      formatReadmeSuggestions(generateReadmeSuggestions(result)),
      manifest
    );
    await writeAsset(
      outputDir,
      'launch-pack.md',
      formatLaunchPack(launchPack),
      manifest
    );
    await writeAsset(
      outputDir,
      'improvement-report.md',
      await renderTemplate(result, 'report'),
      manifest
    );
  } else {
    manifest.skipped.push('本地资料检查包：已跳过（默认 LLM 模式；需要时用 --with-heuristic）');
  }

  const imageContext = resolvePromoImageContext(result, cwd, options);
  const agentGeneratedImages = {};
  const promoBrief = resolvePromoBrief(options, options.env, cwd);

  let projectIntake = options.projectIntake ?? null;
  if (!projectIntake) {
    try {
      projectIntake = await buildProjectIntakeWithAi(result, {
        ai: options.localOnly !== true,
        cwd,
        pdfPaths: options.pdfPaths,
        docPaths: options.docPaths,
        pdfOcr: options.pdfOcr,
        env: options.env,
        baseUrl: options.baseUrl,
        model: options.model,
        maxTokens: options.maxTokens,
        noVision: options.noVision,
        vision: options.vision,
        stream: options.stream,
        apiKey: pickAiKey(options.env)
      });
      if (projectIntake.aiError) {
        manifest.skipped.push(`大模型阅读：${projectIntake.aiError}（已回退本地摘要）`);
      }
    } catch (error) {
      manifest.skipped.push(`项目理解：${error.message}`);
    }
  }

  if (projectIntake?.summaryMarkdown) {
    await writeAsset(outputDir, 'project-summary.md', projectIntake.summaryMarkdown, manifest);
    manifest.summarySource = projectIntake.summarySource ?? 'local';
    if (projectIntake.aiModel) manifest.summaryModel = projectIntake.aiModel;
    if (projectIntake.errors?.length) {
      for (const item of projectIntake.errors) {
        manifest.skipped.push(`文档解析：${item.path} — ${item.error}`);
      }
    }
  }

  if (promoBrief) {
    await writeAsset(
      outputDir,
      'promo-brief-input.md',
      formatPromoBriefInput(promoBrief),
      manifest
    );
    manifest.promoBrief = true;
  }

  let aiPromoContent = null;
  if (hasAiKey(options.env)) {
    try {
      const audit = await generateAiContent(result, {
        audit: true,
        baseUrl: options.baseUrl,
        env: options.env,
        maxTokens: options.maxTokens,
        model: options.model,
        noVision: options.noVision,
        projectIntake,
        stream: options.stream,
        vision: options.vision,
        apiKey: pickAiKey(options.env)
      });
      await writeAsset(outputDir, 'ai-audit.md', formatAiAuditContent(audit, result), manifest);
      manifest.aiScore = resolveAiScore(audit, result);

      const promo = await generateAiContent(result, {
        promo: true,
        baseUrl: options.baseUrl,
        env: options.env,
        maxTokens: options.maxTokens,
        model: options.model,
        noVision: options.noVision,
        platform: 'all',
        projectIntake,
        promoBrief: options.promoBrief,
        promoBriefFile: options.promoBriefFile,
        appliedSkills: options.appliedSkills,
        audience: options.audience,
        promptNotes: options.promptNotes,
        promptPresets: options.promptPresets,
        reviewFocus: options.reviewFocus,
        skills: options.skills,
        stream: options.stream,
        tone: options.tone,
        vision: options.vision,
        tools: options.agentTools,
        noTools: options.noAgentTools,
        agentContext: {
          result,
          cwd,
          outputDir,
          imagesDir,
          env: options.env,
          imageContext,
          projectIntake,
          pdfPaths: options.pdfPaths,
          docPaths: options.docPaths,
          pdfOcr: options.pdfOcr,
          generatedImages: agentGeneratedImages,
          modelscopeApiKey: pickModelscopeKey(options.env)
        },
        apiKey: pickAiKey(options.env)
      });
      aiPromoContent = sanitizePromoContent(promo.content, result);
      manifest.promoSource = 'ai';
      manifest.promoModel = promo.model;
      manifest.agentTools = Boolean(promo.agentTools);
      manifest.toolCalls = Array.isArray(promo.toolCalls) ? promo.toolCalls.length : 0;
      if (manifest.toolCalls > 0) {
        manifest.toolSummary = summarizeToolCalls(promo.toolCalls);
      }
    } catch (error) {
      manifest.skipped.push(`AI 推广：${error.message}`);
    }
  } else {
    manifest.skipped.push('推广文案：未配置 SOURCE2LAUNCH_API_KEY / SOURCE2LAUNCH_MODELSCOPE_API_KEY（需 AI 生成，不使用模板）');
  }

  for (const [key, relativePath] of Object.entries(agentGeneratedImages)) {
    manifest.images[key] = relativePath;
    if (!manifest.generated.includes(relativePath)) {
      manifest.generated.push(relativePath);
    }
  }
  const hasReference = Boolean(imageContext.imageUrl || imageContext.imageFile);
  const imageProvider = resolveImageProvider(options.env);

  if (imageGenAvailable(options, options.env)) {
    const imageJobs = [
      { name: 'xhs-cover.png', platform: 'xhs', key: 'xhs' },
      { name: 'wechat-cover.png', platform: 'wechat', key: 'wechat' }
    ];

    for (const job of imageJobs) {
      if (manifest.images[job.key]) {
        continue;
      }

      try {
        const imageModel = resolveEffectiveImageModel(options.env, hasReference);
        const prompt = buildPromoImagePrompt(result, {
          platform: job.platform,
          hasReference,
          provider: imageProvider,
          model: imageModel,
          env: options.env
        });
        const imageResult = await generateImage({
          apiKey: pickModelscopeKey(options.env),
          env: options.env,
          imageFile: imageContext.imageFile,
          imageUrl: imageContext.imageUrl,
          model: options.imageModel || imageModel,
          outputPath: path.join(imagesDir, job.name),
          platform: job.platform,
          prompt,
          result
        });
        const relative = normalizeCoverRelativePath(path.relative(outputDir, imageResult.outputPath));
        manifest.generated.push(relative);
        manifest.images[job.key] = relative;
      } catch (error) {
        manifest.skipped.push(`图片 ${job.name}：${error.message}`);
      }
    }

    if (
      imageProvider === 'modelscope'
      && modelscopeImageRequiresReference(resolveModelscopeImageModel(options.env))
      && !hasReference
      && !manifest.images.xhs
      && !manifest.images.wechat
    ) {
      manifest.skipped.push('配图参考：图像编辑模型需要 PNG/JPG 参考图（文生图请设 SOURCE2LAUNCH_IMAGE_MODEL=Qwen/Qwen-Image）');
    }
  } else {
    manifest.skipped.push('推广配图：未配置 SOURCE2LAUNCH_GRADIO_URL 或 SOURCE2LAUNCH_MODELSCOPE_API_KEY');
  }

  const promotions = aiPromoContent?.promotions ?? {};
  const xhsCover = manifest.images.xhs ?? null;
  const wechatCover = manifest.images.wechat ?? null;
  const xhsMarkdown = aiPromoContent
    ? formatXhsPromoMarkdown(result, { ai: promotions.xiaohongshu, coverImage: xhsCover })
    : formatPromoUnavailable(result.project.name, '小红书');
  const wechatMarkdown = aiPromoContent
    ? formatWechatPromoMarkdown(result, { ai: promotions.wechatMoments, coverImage: wechatCover })
    : formatPromoUnavailable(result.project.name, '微信');
  const zhihuMarkdown = aiPromoContent
    ? formatZhihuPromoMarkdown(result, { ai: promotions.zhihu })
    : formatPromoUnavailable(result.project.name, '知乎');
  const englishMarkdown = aiPromoContent
    ? formatPromoEnMarkdown(result, promotions)
    : formatPromoUnavailable(result.project.name, '英文平台');
  const promoCopyMarkdown = aiPromoContent
    ? formatPromoCopyMarkdown(result, aiPromoContent, { coverImage: xhsCover })
    : formatPromoUnavailable(result.project.name, '推广');

  await writeAsset(
    outputDir,
    'promo-xhs.md',
    xhsMarkdown,
    manifest
  );
  await writeAsset(
    outputDir,
    'promo-wechat.md',
    wechatMarkdown,
    manifest
  );
  await writeAsset(
    outputDir,
    'promo-zhihu.md',
    zhihuMarkdown,
    manifest
  );
  await writeAsset(
    outputDir,
    'promo-en.md',
    englishMarkdown,
    manifest
  );
  await writeAsset(
    outputDir,
    'promo-copy.md',
    promoCopyMarkdown,
    manifest
  );
  await writeAsset(outputDir, 'platform/xhs.md', xhsMarkdown, manifest);
  await writeAsset(outputDir, 'platform/wechat.md', wechatMarkdown, manifest);
  await writeAsset(outputDir, 'platform/zhihu.md', zhihuMarkdown, manifest);
  await writeAsset(outputDir, 'platform/show-hn.md', formatShowHnDraft(result, promotions, launchPack), manifest);
  await writeAsset(outputDir, 'platform/producthunt-kit.md', formatProductHuntKit(result, promotions, launchPack), manifest);
  await writeAsset(
    outputDir,
    'content-review.md',
    formatContentReview(result, manifest, { aiPromoContent, launchPack }),
    manifest
  );
  await writeAsset(
    outputDir,
    'campaign.json',
    JSON.stringify(
      buildCampaign(result, manifest, {
        aiPromoContent,
        hasDocContext: Boolean(options.docPaths?.length),
        hasPdfContext: Boolean(options.pdfPaths?.length),
        launchPack,
        projectIntake
      }),
      null,
      2
    ),
    manifest
  );

  await writeAsset(outputDir, 'INDEX.md', formatOptimizeIndex(manifest, result), manifest);
  return manifest;
}

export function formatOptimizeIndex(manifest, result) {
  const lines = [];
  lines.push(`# ${manifest.project} · Launch Assets`);
  lines.push('');
  lines.push('> 由 `source2launch optimize` 自动生成');
  if (manifest.mode === 'llm') {
    lines.push('> 模式：**大模型优先**（本地资料检查包已跳过，需要时加 `--with-heuristic`）');
  }
  lines.push('');
  if (manifest.generated.includes('heuristic-audit.md')) {
    lines.push('资料检查：**已生成本地检查报告**（见 `heuristic-audit.md`）');
  } else {
    lines.push('资料检查：**已跳过本地规则检查**（需要时加 `--with-heuristic`）');
  }
  if (manifest.summarySource === 'ai') {
    lines.push(`项目理解：**大模型生成（${manifest.summaryModel ?? 'model'}）** · 见 \`project-summary.md\``);
  } else if (manifest.generated.includes('project-summary.md')) {
    lines.push('项目理解：**本地证据摘要**（配置 API Key 后由大模型生成）');
  }
  if (manifest.generated.includes('ai-audit.md')) {
    lines.push('AI 资料检查：**已生成**（见 `ai-audit.md`）');
  }
  lines.push(`AI 平台文案：**${manifest.promoSource === 'ai' ? `已生成（${manifest.promoModel ?? 'model'}）` : '未生成（需配置 API Key）'}**`);
  if (manifest.agentTools) {
    lines.push(`Agent 工具：**已启用**（${manifest.toolCalls ?? 0} 次调用）`);
    if (Array.isArray(manifest.toolSummary) && manifest.toolSummary.length > 0) {
      for (const item of manifest.toolSummary) lines.push(`- ${item}`);
    }
  }
  if (manifest.promoBrief) {
    lines.push('创作引导：**已应用**（见 `promo-brief-input.md`）');
  }
  lines.push('');

  if (manifest.images.xhs || manifest.images.wechat) {
    lines.push('## 推广配图预览');
    lines.push('');
    if (manifest.images.xhs) {
      lines.push('### 小红书封面');
      lines.push('');
      lines.push(`![小红书封面](./${manifest.images.xhs})`);
      lines.push('');
    }
    if (manifest.images.wechat) {
      lines.push('### 微信封面');
      lines.push('');
      lines.push(`![微信封面](./${manifest.images.wechat})`);
      lines.push('');
    }
  }

  lines.push('## 文件清单');
  lines.push('');
  for (const file of manifest.generated) {
    lines.push(`- [${file}](./${file})${promoFileNote(file)}`);
  }
  lines.push('');
  lines.push('## 推荐使用顺序');
  lines.push('');
  lines.push('1. 阅读 `project-summary.md`（大模型项目理解，推荐起点）');
  lines.push('2. 阅读 `content-review.md`，确认事实、图片、链接和平台语气');
  lines.push('3. 到 `platform/` 选择要发布的平台草稿');
  lines.push('4. 英文渠道优先看 `platform/show-hn.md` 和 `platform/producthunt-kit.md`');
  lines.push('5. 配图使用 `images/` 中的封面，必要时再用 `--promo-brief` 重新生成');
  lines.push('6. 需要自动化对接时读取 `campaign.json`；需要改 README 时再看 `readme-suggestions.md`');
  lines.push('');
  if (manifest.skipped.length > 0) {
    lines.push('## 跳过项');
    lines.push('');
    for (const item of manifest.skipped) lines.push(`- ${item}`);
    lines.push('');
  }
  lines.push('## 项目信息');
  lines.push('');
  lines.push(`- 项目：${result.project.name}`);
  if (result.project.repositoryUrl) lines.push(`- 仓库：${result.project.repositoryUrl}`);
  if (result.project.installCommand) lines.push(`- 安装：\`${result.project.installCommand}\``);
  lines.push('');
  return lines.join('\n');
}

function resolveOptimizeMode(options = {}) {
  if (options.llmOnly === true) return 'llm';
  if (options.withHeuristic === true) return 'full';
  if (hasAiKey(options.env)) return 'llm';
  return 'full';
}

function shouldWriteHeuristicAssets(options = {}) {
  return resolveOptimizeMode(options) === 'full';
}

function normalizeCoverRelativePath(relativePath) {
  const normalized = String(relativePath ?? '').replace(/\\/g, '/');
  if (!normalized || normalized.startsWith('./')) return normalized;
  return `./${normalized}`;
}

function promoFileNote(file) {
  if (file === 'project-summary.md') return ' — 大模型项目理解（推荐先读）';
  if (file === 'heuristic-audit.md') return ' — 本地资料检查（CI）';
  if (file === 'ai-audit.md') return ' — AI 发布资料检查';
  if (file === 'promo-xhs.md') return ' — 小红书';
  if (file === 'promo-wechat.md') return ' — 微信';
  if (file === 'promo-zhihu.md') return ' — 知乎';
  if (file === 'promo-en.md') return ' — 英文平台';
  if (file === 'promo-copy.md') return ' — 推广索引';
  if (file === 'campaign.json') return ' — 活动状态（机器可读）';
  if (file === 'content-review.md') return ' — 人工审核清单';
  if (file.startsWith('platform/')) return ' — 平台草稿';
  if (file.startsWith('images/')) return ' — 配图';
  return '';
}

function hasAiKey(env = process.env) {
  return Boolean(
    env.SOURCE2LAUNCH_API_KEY
    || env.STAR_UP_API_KEY
    || env.OPENAI_API_KEY
    || env.SOURCE2LAUNCH_MODELSCOPE_API_KEY
    || env.STAR_UP_MODELSCOPE_API_KEY
    || env.MODELSCOPE_API_KEY
  );
}

function hasModelscopeKey(env = process.env) {
  return imageGenAvailable({}, env);
}

function pickAiKey(env = process.env) {
  return env.SOURCE2LAUNCH_API_KEY
    || env.STAR_UP_API_KEY
    || env.OPENAI_API_KEY
    || env.SOURCE2LAUNCH_MODELSCOPE_API_KEY
    || env.STAR_UP_MODELSCOPE_API_KEY
    || env.MODELSCOPE_API_KEY;
}

function pickModelscopeKey(env = process.env) {
  return env.SOURCE2LAUNCH_MODELSCOPE_API_KEY || env.STAR_UP_MODELSCOPE_API_KEY || env.MODELSCOPE_API_KEY;
}

function formatPromoBriefInput(brief) {
  return [
    '# 创作引导输入',
    '',
    '> 由 `--promo-brief` / `SOURCE2LAUNCH_PROMO_BRIEF` 提供，已注入 AI 推广生成',
    '',
    String(brief).trim()
  ].join('\n');
}

function summarizeToolCalls(toolCalls = []) {
  const counts = new Map();
  for (const call of toolCalls) {
    const name = call.name ?? 'unknown';
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts.entries()].map(([name, count]) => `${name} ×${count}`);
}

async function writeAsset(outputDir, filename, content, manifest) {
  const filePath = path.join(outputDir, filename);
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${String(content).trimEnd()}\n`, 'utf8');
  manifest.generated.push(filename);
}
