import { existsSync, readFileSync } from 'node:fs';
import { promises as fs } from 'node:fs';
import path from 'node:path';

import { formatAiContent, generateAiContent, resolveAiScore } from './ai.js';
import { analyzeTarget } from './index.js';
import { formatLaunchPack, generateLaunchPack } from './launch.js';
import { generateMarkdownDocument, markdownTypeNames } from './markdown.js';
import { buildPromoImagePrompt, generateImage, imageGenAvailable, resolveImageProvider } from './modelscope.js';
import { runOptimize } from './optimize.js';
import { buildProjectIntakeWithAi } from './project-brief.js';
import { formatIntroCliOutput } from './project-intro.js';
import {
  formatPromoCopyMarkdown,
  formatPromoEnMarkdown,
  formatPromoUnavailable,
  formatWechatPromoMarkdown,
  formatXhsPromoMarkdown,
  formatZhihuPromoMarkdown
} from './promo.js';
import { resolvePromoImageContext } from './promo-shared.js';
import { formatReadmeSuggestions, generateReadmeSuggestions } from './readme.js';
import { formatReport } from './report.js';
import { renderTemplate, templateChoices } from './template.js';
import { buildPublishPlan, formatPublishPlan } from './publish.js';
import { buildPromotionSkillPlan, applyPromotionSkills, promotionSkillNames } from './skills.js';
import { promptPresetNames } from './prompts.js';

const VERSION = '0.2.0';

export async function runCli(argv = process.argv) {
  loadEnvFromFile(process.cwd());
  let { target, options } = parseArgs(argv.slice(2));

  if (options.help) {
    console.log(helpText());
    return;
  }

  if (options.version) {
    console.log(VERSION);
    return;
  }

  options = await hydratePromptFiles(options, process.cwd());
  options = applyCliPromotionSkills(options);

  if (options.publish) {
    await runPublishCli(target, options);
    return;
  }

  ({ target, options } = await normalizePrimaryInput(target ?? '.', options, process.cwd()));
  options = await hydrateContextSources(options, process.cwd());

  const result = await analyzeTarget(target ?? '.', { cwd: process.cwd() });
  const renderedTemplate = options.template ? await renderTemplate(result, options.template) : null;
  const readmeSuggestions = options.readmeSuggestions ? generateReadmeSuggestions(result) : null;
  const launchPack = options.launchPack ? generateLaunchPack(result) : null;

  if (options.markdown) {
    const output = generateMarkdownDocument(result, { markdownType: options.markdownType });
    if (options.output) {
      const outputPath = path.resolve(process.cwd(), options.output);
      await fs.mkdir(path.dirname(outputPath), { recursive: true });
      await fs.writeFile(outputPath, `${output.trimEnd()}\n`, 'utf8');
      console.log(`已写入 ${outputPath}`);
    } else {
      console.log(output);
    }
    return;
  }

  if (options.intro || options.docs) {
    const intake = await buildProjectIntakeWithAi(result, {
      ai: !options.localOnly,
      cwd: process.cwd(),
      pdfPaths: options.pdfPaths,
      docPaths: options.docPaths,
      pdfOcr: resolvePdfOcr(options),
      env: process.env,
      baseUrl: options.baseUrl,
      model: options.model,
      maxTokens: options.maxTokens,
      noVision: options.noVision,
      vision: options.vision,
      stream: options.stream
    });

    if (options.docs) {
      console.log('Source2Launch · 项目文档包生成中…');
      console.log('');
      console.log('项目    ' + result.project.name);
      console.log('状态    ' + (intake.summarySource === 'ai' ? `大模型生成（${intake.aiModel ?? 'model'}）` : '本地证据'));
      console.log('');
      console.log('推荐入口：source2launch markdown . --markdown-type all --output project-pack.md');
      console.log('完整资料包：source2launch optimize . --output launch-assets/');
      console.log('');
      return;
    }

    // --intro 生成项目介绍文档
    const output = formatIntroCliOutput(intake, result);

    if (options.output) {
      const outputPath = path.resolve(process.cwd(), options.output);
      await fs.mkdir(path.dirname(outputPath), { recursive: true });
      await fs.writeFile(outputPath, `${output.trimEnd()}\n`, 'utf8');
      console.log(`已写入 ${outputPath}`);
    } else {
      console.log(output);
    }

    if (intake.summarySource === 'ai') {
      console.error('');
      console.error(`（大模型阅读 · ${intake.aiModel ?? 'model'}）`);
    } else if (intake.aiError) {
      console.error('');
      console.error(`（AI 失败，已回退本地摘要：${intake.aiError}）`);
    }

    if (intake.errors?.length > 0) {
      console.error('');
      console.error('文档解析警告');
      for (const item of intake.errors) {
        console.error(`  ${item.path}: ${item.error}`);
      }
    }
    return;
  }

  if (options.readProject) {
    const intake = await buildProjectIntakeWithAi(result, {
      ai: !options.localOnly,
      cwd: process.cwd(),
      pdfPaths: options.pdfPaths,
      docPaths: options.docPaths,
      pdfOcr: resolvePdfOcr(options),
      env: process.env,
      baseUrl: options.baseUrl,
      model: options.model,
      maxTokens: options.maxTokens,
      noVision: options.noVision,
      vision: options.vision,
      stream: options.stream
    });
    const output = intake.summaryMarkdown;

    if (options.output) {
      const outputPath = path.resolve(process.cwd(), options.output);
      await fs.mkdir(path.dirname(outputPath), { recursive: true });
      await fs.writeFile(outputPath, `${output.trimEnd()}\n`, 'utf8');
      console.log(`已写入 ${outputPath}`);
    } else {
      console.log(output);
    }

    if (intake.summarySource === 'ai') {
      console.error('');
      console.error(`（大模型阅读 · ${intake.aiModel ?? 'model'}）`);
    } else if (intake.aiError) {
      console.error('');
      console.error(`（AI 失败，已回退本地摘要：${intake.aiError}）`);
    }

    if (intake.errors?.length > 0) {
      console.error('');
      console.error('文档解析警告');
      for (const item of intake.errors) {
        console.error(`  ${item.path}: ${item.error}`);
      }
    }
    return;
  }

  const projectIntake = await resolveCliProjectIntake(result, options);

  if (options.optimize) {
    const manifest = await runOptimize(result, {
      agentTools: options.agentTools,
      baseUrl: options.baseUrl,
      cwd: process.cwd(),
      docPaths: options.docPaths,
      env: process.env,
      imageFile: options.imageFile,
      imageModel: options.imageModel,
      imageUrl: options.imageUrl,
      maxTokens: options.maxTokens,
      model: options.model,
      noAgentTools: options.noAgentTools,
      noVision: options.noVision,
      optimizeDir: options.optimizeDir,
      pdfOcr: resolvePdfOcr(options),
      pdfPaths: options.pdfPaths,
      llmOnly: options.llmOnly,
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
      withHeuristic: options.withHeuristic
    });

    console.log('Source2Launch · 项目优化包已生成');
    console.log('');
    console.log(`目录    ${manifest.outputDir}`);
    console.log(`文件    ${manifest.generated.length} 个`);
    for (const file of manifest.generated) {
      console.log(`        ${file}`);
    }
    if (manifest.skipped.length > 0) {
      console.log('');
      console.log('跳过项');
      for (const item of manifest.skipped) console.log(`        ${item}`);
    }
    console.log('');
    if (manifest.images.xhs || manifest.images.wechat) {
      console.log('配图');
      if (manifest.images.xhs) {
        console.log(`        ${manifest.images.xhs}`);
        console.log(`        打开    ${path.join(manifest.outputDir, manifest.images.xhs.replace(/^\.\//, ''))}`);
      }
      if (manifest.images.wechat) {
        console.log(`        ${manifest.images.wechat}`);
        console.log(`        打开    ${path.join(manifest.outputDir, manifest.images.wechat.replace(/^\.\//, ''))}`);
      }
    } else {
      console.log('配图    未生成（见下方跳过项）');
    }
    if (manifest.summarySource === 'ai') {
      console.log(`理解    大模型 project-summary.md（${manifest.summaryModel ?? 'model'}）`);
    }
    console.log(`模式    ${manifest.mode === 'llm' ? '大模型优先（本地资料检查包已跳过）' : '完整包（含本地资料检查）'}`);
    console.log(`文案    ${manifest.promoSource === 'ai' ? `AI 生成（${manifest.promoModel ?? 'model'}）` : 'AI 未生成（需 API Key）'}`);
    if (manifest.agentTools) {
      console.log(`工具    Agent 已启用（${manifest.toolCalls ?? 0} 次调用）`);
    }
    console.log('');
    console.log(`请从 ${path.join(manifest.outputDir, 'INDEX.md')} 开始查看`);
    return;
  }

  if (options.genImage) {
    const prompt = options.imagePrompt || buildPromoImagePrompt(result, {
      platform: options.promo || 'xhs',
      prompt: options.imagePrompt
    });
    const outputPath = path.resolve(
      process.cwd(),
      options.imageOutput || options.output || 'promo-image.jpg'
    );

    console.log('推广配图生成中…');
    const provider = resolveImageProvider(process.env);
    console.log(`后端    ${provider === 'gradio' ? 'Gradio /generate_image' : 'ModelScope'}`);
    console.log(`模型    ${options.imageModel || (provider === 'gradio' ? '(Gradio API)' : '(env SOURCE2LAUNCH_IMAGE_MODEL)')}`);
    console.log(`Prompt  ${prompt}`);

    const imageResult = await generateImage({
      env: process.env,
      imageFile: options.imageFile,
      imageUrl: options.imageUrl,
      model: options.imageModel,
      outputPath,
      platform: options.promo || 'xhs',
      prompt,
      result
    });

    console.log(`已保存  ${imageResult.outputPath}`);
    console.log(`任务 ID ${imageResult.taskId}`);
    return;
  }

  const ai = options.ai ? await generateAiContent(result, {
    baseUrl: options.baseUrl,
    maxTokens: options.maxTokens,
    model: options.model,
    noVision: options.noVision,
    platform: options.promo ?? options.template ?? 'all',
    projectIntake,
    promo: Boolean(options.promo || options.promoOnly),
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
    agentContext: buildCliAgentContext(result, options, projectIntake)
  }) : null;
  let output = '';

  if (options.json) {
    const jsonResult = {
      ...result,
      ...(renderedTemplate ? { renderedTemplate: { name: options.template, content: renderedTemplate } } : {}),
      ...(readmeSuggestions ? { readmeSuggestions } : {}),
      ...(launchPack ? { launchPack } : {}),
      ...(ai ? { ai } : {})
    };
    output = JSON.stringify(jsonResult, null, 2);
  } else if (options.aiOnly && ai) {
    output = formatPromoCliOutput(result, ai.content, options.promo ?? 'all');
  } else if (options.aiOnly) {
    output = formatPromoCliOutput(result, (await generateAiContent(result, {
      baseUrl: options.baseUrl,
      maxTokens: options.maxTokens,
      model: options.model,
      promo: true,
      platform: options.promo ?? 'all',
      projectIntake,
      promoBrief: options.promoBrief,
      promoBriefFile: options.promoBriefFile,
      appliedSkills: options.appliedSkills,
      audience: options.audience,
      promptNotes: options.promptNotes,
      promptPresets: options.promptPresets,
      reviewFocus: options.reviewFocus,
      skills: options.skills,
      tone: options.tone,
      tools: options.agentTools,
      noTools: options.noAgentTools,
      agentContext: buildCliAgentContext(result, options, projectIntake)
    })).content, options.promo ?? 'all');
  } else if (renderedTemplate) {
    output = ai ? `${renderedTemplate.trimEnd()}\n\n${formatAiContent(ai, { platform: options.promo ?? options.template ?? 'all' })}` : renderedTemplate;
  } else if (readmeSuggestions) {
    output = ai
      ? `${formatReadmeSuggestions(readmeSuggestions)}\n\n${formatAiContent(ai, { platform: options.promo ?? 'all' })}`
      : formatReadmeSuggestions(readmeSuggestions);
  } else if (launchPack) {
    output = ai
      ? `${formatLaunchPack(launchPack)}\n\n${formatAiContent(ai, { platform: options.promo ?? 'all' })}`
      : formatLaunchPack(launchPack);
  } else if (options.promoOnly) {
    if (ai?.content?.promotions) {
      output = formatPromoCliOutput(result, ai.content, options.promo ?? 'all');
    } else if (ai) {
      output = formatAiContent(ai, { platform: options.promo ?? 'all' });
    } else {
      output = formatPromoUnavailable(result.project.name, '推广');
    }
  } else {
    const parts = [formatReport(result)];
    if (ai?.content?.promotions) parts.push(formatPromoCliOutput(result, ai.content, options.promo ?? 'all'));
    else if (ai) parts.push(formatAiContent(ai, { platform: options.promo ?? 'all' }));
    output = parts.join('\n\n');
  }

  if (options.output) {
    const outputPath = path.resolve(process.cwd(), options.output);
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, `${output.trimEnd()}\n`, 'utf8');
    console.log(`Wrote ${outputPath}`);
  } else {
    console.log(output);
  }

  if (options.failUnder !== null) {
    applyFailUnder(options.failUnder, result.score);
  }
}

function applyFailUnder(threshold, score) {
  if (threshold !== null && score < threshold) {
    process.exitCode = 1;
  }
}

function loadEnvFromFile(cwd) {
  const envPath = path.join(cwd, '.env');
  if (!existsSync(envPath)) return;

  for (const line of readFileSync(envPath, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const index = trimmed.indexOf('=');
    if (index <= 0) continue;
    const key = trimmed.slice(0, index).trim();
    const value = trimmed.slice(index + 1).trim();
    if (key && process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

export function parseArgs(args) {
  const options = {
    ai: false,
    aiOnly: false,
    agentTools: false,
    audience: null,
    baseUrl: null,
    context: [],
    docs: false,
    executePublish: false,
    failUnder: null,
    genImage: false,
    help: false,
    imageFile: null,
    imageModel: null,
    imageOutput: null,
    imagePrompt: null,
    imageUrl: null,
    intro: false,
    json: false,
    launchPack: false,
    localOnly: false,
    markdown: false,
    markdownType: 'project',
    maxTokens: null,
    media: [],
    mode: null,
    model: null,
    noVision: false,
    noAgentTools: false,
    optimize: false,
    optimizeDir: null,
    llmOnly: false,
    withHeuristic: false,
    output: null,
    pdfOcr: false,
    pdfPaths: [],
    platformExplicit: false,
    docPaths: [],
    readProject: false,
    promo: null,
    promoBrief: null,
    promoBriefFile: null,
    promoOnly: false,
    promptFiles: [],
    promptNotes: [],
    promptPresets: [],
    publish: false,
    publishMode: 'review',
    readmeSuggestions: false,
    reviewFocus: [],
    skills: [],
    stream: false,
    template: null,
    tone: null,
    version: false,
    vision: false,
    yes: false
  };
  let target = null;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];

    if (target === null && options.mode === null && !arg.startsWith('-')) {
      if (arg === 'promote') {
        options.mode = 'promote';
        options.ai = true;
        options.promo = 'all';
        options.promoOnly = true;
        continue;
      }
      if (arg === 'optimize') {
        options.mode = 'optimize';
        options.optimize = true;
        continue;
      }
      if (arg === 'markdown') {
        options.mode = 'markdown';
        options.markdown = true;
        continue;
      }
      if (arg === 'publish') {
        options.mode = 'publish';
        options.publish = true;
        continue;
      }
    }

    if (arg === '--help' || arg === '-h') {
      options.help = true;
    } else if (arg === '--version' || arg === '-v') {
      options.version = true;
    } else if (arg === '--ai') {
      options.ai = true;
    } else if (arg === '--ai-only') {
      options.ai = true;
      options.aiOnly = true;
    } else if (arg === '--model') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--model expects a model name');
      }
      options.model = value;
      index += 1;
    } else if (arg === '--base-url') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--base-url expects an API base URL');
      }
      options.baseUrl = value;
      index += 1;
    } else if (arg === '--max-tokens') {
      const value = Number(args[index + 1]);
      if (!Number.isFinite(value) || value < 256) {
        throw new Error('--max-tokens expects a number >= 256');
      }
      options.maxTokens = value;
      index += 1;
    } else if (arg === '--skill') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`--skill expects one of: ${promotionSkillNames().join(', ')}`);
      }
      options.skills.push(value);
      index += 1;
    } else if (arg === '--prompt-preset') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`--prompt-preset expects one of: ${promptPresetNames().join(', ')}`);
      }
      options.promptPresets.push(value);
      index += 1;
    } else if (arg === '--prompt-note') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--prompt-note expects instruction text');
      }
      options.promptNotes.push(value);
      index += 1;
    } else if (arg === '--prompt-file') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--prompt-file expects a file path');
      }
      options.promptFiles.push(value);
      index += 1;
    } else if (arg === '--context') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--context expects a related source path or URL');
      }
      options.context.push(value);
      index += 1;
    } else if (arg === '--audience') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--audience expects audience text');
      }
      options.audience = value;
      index += 1;
    } else if (arg === '--tone') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--tone expects tone text');
      }
      options.tone = value;
      index += 1;
    } else if (arg === '--optimize' || arg === '--auto') {
      options.optimize = true;
    } else if (arg === '--intro') {
      options.intro = true;
    } else if (arg === '--docs') {
      options.docs = true;
    } else if (arg === '--optimize-dir') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--optimize-dir expects a directory path');
      }
      options.optimizeDir = value;
      index += 1;
    } else if (arg === '--with-heuristic') {
      options.withHeuristic = true;
    } else if (arg === '--llm-only') {
      options.llmOnly = true;
    } else if (arg === '--pdf') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--pdf expects a PDF file path');
      }
      options.pdfPaths.push(value);
      index += 1;
    } else if (arg === '--project-doc') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--project-doc expects a text/markdown file path');
      }
      options.docPaths.push(value);
      index += 1;
    } else if (arg === '--pdf-ocr') {
      options.pdfOcr = true;
    } else if (arg === '--markdown-type') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`--markdown-type expects one of: ${markdownTypeNames().join(', ')}`);
      }
      options.markdownType = value;
      index += 1;
    } else if (arg === '--read-project' || arg === '--brief') {
      options.readProject = true;
    } else if (arg === '--local' || arg === '--no-ai') {
      options.localOnly = true;
    } else if (arg === '--vision') {
      options.vision = true;
    } else if (arg === '--no-vision') {
      options.noVision = true;
    } else if (arg === '--agent-tools') {
      options.agentTools = true;
    } else if (arg === '--no-agent-tools') {
      options.noAgentTools = true;
    } else if (arg === '--stream') {
      options.stream = true;
    } else if (arg === '--gen-image' || arg === '--image') {
      options.genImage = true;
    } else if (arg === '--image-prompt') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--image-prompt expects a prompt string');
      }
      options.imagePrompt = value;
      index += 1;
    } else if (arg === '--image-url') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--image-url expects an image URL');
      }
      options.imageUrl = value;
      index += 1;
    } else if (arg === '--image-file') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--image-file expects a local image path');
      }
      options.imageFile = value;
      index += 1;
    } else if (arg === '--image-model') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--image-model expects a ModelScope model id');
      }
      options.imageModel = value;
      index += 1;
    } else if (arg === '--image-output') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--image-output expects a file path');
      }
      options.imageOutput = value;
      index += 1;
    } else if (arg === '--json') {
      options.json = true;
    } else if (arg === '--promo' || arg === '--platform') {
      const rawValue = args[index + 1];
      if (!rawValue || rawValue.startsWith('--')) {
        throw new Error(`${arg} expects a platform`);
      }
      if (options.mode === 'publish') {
        options.promo = rawValue;
      } else {
        const value = normalizePromo(rawValue);
        if (!value) {
          throw new Error(`${arg} expects xhs, zhihu, wechat, launch, or all`);
        }
        options.promo = value;
      }
      options.platformExplicit = true;
      index += 1;
    } else if (arg === '--xiaohongshu' || arg === '--xhs') {
      options.promo = 'xhs';
      options.platformExplicit = true;
    } else if (arg === '--wechat' || arg === '--weixin') {
      options.promo = 'wechat';
      options.platformExplicit = true;
    } else if (arg === '--promo-brief' || arg === '--brief') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--promo-brief expects guidance text');
      }
      options.promoBrief = value;
      index += 1;
    } else if (arg === '--promo-brief-file' || arg === '-B') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--promo-brief-file expects a file path');
      }
      options.promoBriefFile = value;
      index += 1;
    } else if (arg === '--promo-only') {
      options.promoOnly = true;
    } else if (arg === '--readme-suggestions' || arg === '--readme') {
      options.readmeSuggestions = true;
    } else if (arg === '--launch-pack' || arg === '--launch') {
      options.launchPack = true;
    } else if (arg === '--template') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`--template expects one of: ${templateChoices().join(', ')}`);
      }
      options.template = value;
      index += 1;
    } else if (arg === '--output' || arg === '-o') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--output expects a file path');
      }
      options.output = value;
      index += 1;
    } else if (arg === '--fail-under') {
      const value = Number(args[index + 1]);
      if (!Number.isFinite(value) || value < 0 || value > 100) {
        throw new Error('--fail-under expects a number from 0 to 100');
      }
      options.failUnder = value;
      index += 1;
    } else if (arg === '--publish-mode') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--publish-mode expects review, dry-run, api, or assist');
      }
      options.publishMode = value;
      index += 1;
    } else if (arg === '--yes' || arg === '-y') {
      options.yes = true;
    } else if (arg === '--media') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--media expects a media path or URL');
      }
      options.media.push(value);
      index += 1;
    } else if (arg.startsWith('--')) {
      throw new Error(`Unknown option: ${arg}`);
    } else if (target === null) {
      target = arg;
    } else {
      throw new Error(`Unexpected argument: ${arg}`);
    }
  }

  if (options.mode === 'optimize' && options.output && !options.optimizeDir) {
    options.optimizeDir = options.output;
    options.output = null;
  }

  return { target, options };
}

async function runPublishCli(target, options = {}) {
  if (!target) throw new Error('publish expects a JSON file produced by promote/optimize');
  const inputPath = path.resolve(process.cwd(), target);
  const raw = await fs.readFile(inputPath, 'utf8');
  const input = JSON.parse(raw);
  const plan = buildPublishPlan(input, {
    media: options.media,
    platform: options.promo ?? 'all',
    publishMode: options.publishMode,
    yes: options.yes
  });
  const output = options.json ? JSON.stringify(plan, null, 2) : formatPublishPlan(plan);
  if (options.output) {
    const outputPath = path.resolve(process.cwd(), options.output);
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, `${output.trimEnd()}\n`, 'utf8');
    console.log(`已写入 ${outputPath}`);
  } else {
    console.log(output);
  }
}

async function hydratePromptFiles(options = {}, cwd = process.cwd()) {
  if (!options.promptFiles?.length) return options;
  const promptNotes = [...(options.promptNotes ?? [])];
  for (const file of options.promptFiles) {
    const filePath = path.resolve(cwd, file);
    const content = await fs.readFile(filePath, 'utf8');
    promptNotes.push(`来自 ${file} 的自定义提示词：\n${content.trim()}`);
  }
  return { ...options, promptNotes };
}

async function hydrateContextSources(options = {}, cwd = process.cwd()) {
  if (!options.context?.length) return options;
  const next = {
    ...options,
    docPaths: [...(options.docPaths ?? [])],
    pdfPaths: [...(options.pdfPaths ?? [])],
    promptNotes: [...(options.promptNotes ?? [])]
  };

  for (const item of options.context) {
    if (/^https?:\/\//i.test(item)) {
      next.promptNotes.push(`Related source URL supplied by user: ${item}. Do not claim facts from it unless its content is present in provided evidence.`);
      continue;
    }

    const resolved = path.resolve(cwd, item);
    const stat = await fs.stat(resolved).catch(() => null);
    if (!stat?.isFile()) {
      next.promptNotes.push(`Related source path supplied but not readable: ${item}. Mention as missing evidence if relevant.`);
      continue;
    }

    const ext = path.extname(resolved).toLowerCase();
    if (ext === '.pdf') addUniquePath(next.pdfPaths, item);
    else if (['.md', '.markdown', '.txt', '.rst', '.tex', '.html'].includes(ext)) addUniquePath(next.docPaths, item);
    else next.promptNotes.push(`Related source path supplied: ${item}. It is not a supported text/PDF evidence file.`);
  }

  return next;
}

function applyCliPromotionSkills(options = {}) {
  if (!options.skills?.length) return options;
  const skillPlan = buildPromotionSkillPlan(options.skills);
  const applied = applyPromotionSkills({ ...options, skill: options.skills });
  const next = {
    ...applied,
    skillPlan,
    skills: options.skills
  };
  if (!options.platformExplicit && skillPlan.defaultPlatform) {
    next.promo = skillPlan.defaultPlatform;
    next.platform = skillPlan.defaultPlatform;
  }
  return next;
}

export async function normalizePrimaryInput(target = '.', options = {}, cwd = process.cwd()) {
  const rawTarget = String(target || '.').trim();
  if (!rawTarget || /^https?:\/\//i.test(rawTarget)) {
    return { target: rawTarget || '.', options };
  }

  const resolved = path.resolve(cwd, rawTarget);
  const stat = await fs.stat(resolved).catch(() => null);
  if (!stat?.isFile()) {
    return { target: rawTarget, options };
  }

  const ext = path.extname(resolved).toLowerCase();
  const nextOptions = {
    ...options,
    pdfPaths: [...(options.pdfPaths ?? [])],
    docPaths: [...(options.docPaths ?? [])]
  };

  if (ext === '.pdf') {
    addUniquePath(nextOptions.pdfPaths, rawTarget);
    return { target: path.dirname(resolved), options: nextOptions };
  }

  if (['.md', '.markdown', '.txt', '.rst', '.tex', '.html'].includes(ext)) {
    addUniquePath(nextOptions.docPaths, rawTarget);
    return { target: path.dirname(resolved), options: nextOptions };
  }

  return { target: rawTarget, options };
}

function addUniquePath(list, value) {
  if (!list.includes(value)) list.unshift(value);
}

function helpText() {
  return [
    'Source2Launch · 从开源项目或论文生成可审核的发布推广内容',
    '',
    '用法:',
    '  source2launch promote <路径|GitHub URL|PDF|文本> [选项]',
    '  source2launch optimize <路径|GitHub URL|PDF|文本> [选项]',
    '  source2launch markdown <路径|GitHub URL|PDF|文本> [选项]',
    '  source2launch publish <promotion.json> [选项]',
    '  source2launch <路径或 GitHub URL> [legacy 选项]',
    '',
    '主路径:',
    '  source2launch promote . --platform xhs',
    '  source2launch promote paper.pdf --platform zhihu',
    '  source2launch promote https://github.com/user/repo --platform launch',
    '  source2launch optimize . --output launch-assets/',
    '  source2launch markdown . --markdown-type launch --output LAUNCH.md',
    '  source2launch publish promotion.json --platform xhs --publish-mode review',
    '',
    'Promote 选项:',
    '  --platform <target>    输出平台：xhs | zhihu | wechat | launch | all',
    '  --promo <target>       --platform 的兼容别名',
    '  --skill <name>         任务技能：paper | code | paper-code | social | visual | markdown',
    '  --prompt-preset <name>  提示词预设（可重复或逗号分隔）',
    '  --prompt-note <text>   追加临时写作要求',
    '  --prompt-file <path>   从文件读取追加提示词',
    '  --audience <text>      指定目标读者',
    '  --tone <text>          指定写作语气',
    '  --promo-brief <text>   创作引导：风格/思路/受众',
    '  --promo-brief-file <path>  从文件读取创作引导',
    '  --agent-tools          推广文案启用 Agent 工具（搜索/读证据/生图）',
    '  --no-agent-tools       禁用 Agent 工具，单次 JSON 生成',
    '',
    'Optimize 选项:',
    '  --output <dir>         输出发布资料目录（默认 launch-assets）',
    '  --optimize-dir <dir>   --output 的兼容别名',
    '  --llm-only             仅生成大模型产物',
    '  --with-heuristic       额外生成本地资料检查材料',
    '  --pdf <path>           附加 PDF 文档（可重复）',
    '  --project-doc <path>   附加 Markdown/文本文档（可重复）',
    '  --pdf-ocr              扫描版 PDF 启用 OCR（需 pdftoppm + tesseract）',
    '',
    'Markdown / Publish:',
    '  --markdown-type <type> project | readme | launch | promo | all',
    '  --publish-mode <mode>  review | dry-run | api | assist',
    '  --media <path|url>     给发布计划附加媒体（可重复）',
    '  --yes, -y              标记人工已审核；仍不会自动点击发布',
    '',
    'AI 与图片:',
    '  --model <name>         覆盖 SOURCE2LAUNCH_MODEL',
    '  --base-url <url>       覆盖 SOURCE2LAUNCH_BASE_URL',
    '  --vision               附带 README 远程截图做多模态分析',
    '  --no-vision            禁用多模态视觉分析',
    '  --stream               启用流式输出（ModelScope/OpenAI 兼容）',
    '  --max-tokens <number>  覆盖 SOURCE2LAUNCH_MAX_TOKENS',
    '  --gen-image, --image   生成推广配图（默认 Gradio /generate_image 文生图）',
    '  --image-prompt <text>  自定义图片 prompt（默认按仓库自动生成）',
    '  --image-url <url>      参考图 URL（图像编辑模型）',
    '  --image-file <path>    本地参考图（自动 base64 上传）',
    '  --image-model <id>     ModelScope 模型 ID',
    '  --image-output <file>  图片输出路径（也可用 -o）',
    '',
    '兼容 / 本地检查:',
    '  --ai                   AI 增强入口（建议改用 promote）',
    '  --ai-only              仅输出 AI 内容',
    '  --intro                生成项目介绍文档',
    '  --docs                 显示文档包推荐入口',
    '  --read-project         大模型阅读并介绍项目',
    '  --readme-suggestions   README 首屏改写建议',
    '  --launch-pack          多渠道发布包模板',
    '  --template <name>      渲染本地模板',
    '  --fail-under <score>   本地资料检查分低于阈值时 exit 1',
    '  -o, --output <file>    写入文件',
    '  --json                 JSON 输出',
    '  --local, --no-ai         项目理解/optimize 时使用本地证据，不调用大模型',
    '  -h, --help             显示帮助',
    '  -v, --version          显示版本'
  ].join('\n');
}

function buildCliAgentContext(result, options = {}, projectIntake = null) {
  const outputDir = path.resolve(process.cwd(), options.optimizeDir || 'launch-assets');
  const imagesDir = path.join(outputDir, 'images');
  return {
    result,
    cwd: process.cwd(),
    outputDir,
    imagesDir,
    env: process.env,
    imageContext: resolvePromoImageContext(result, process.cwd(), options),
    projectIntake,
    pdfPaths: options.pdfPaths,
    docPaths: options.docPaths,
    pdfOcr: resolvePdfOcr(options),
    generatedImages: {}
  };
}

function resolvePdfOcr(options = {}) {
  return Boolean(options.pdfOcr || process.env.SOURCE2LAUNCH_PDF_OCR === 'true' || process.env.STAR_UP_PDF_OCR === 'true');
}

async function resolveCliProjectIntake(result, options) {
  const needsIntake = Boolean(
    options.optimize
    || options.ai
    || options.pdfPaths?.length
    || options.docPaths?.length
  );
  if (!needsIntake) return null;

  return buildProjectIntakeWithAi(result, {
    ai: !options.localOnly,
    cwd: process.cwd(),
    pdfPaths: options.pdfPaths,
    docPaths: options.docPaths,
    pdfOcr: resolvePdfOcr(options),
    env: process.env,
    baseUrl: options.baseUrl,
    model: options.model,
    maxTokens: options.maxTokens,
    noVision: options.noVision,
    vision: options.vision,
    stream: options.stream
  });
}

function normalizePromo(value) {
  const normalized = String(value ?? '').trim().toLowerCase();
  if (['all', 'both'].includes(normalized)) return 'all';
  if (['xhs', 'xiaohongshu', 'red', 'rednote'].includes(normalized)) return 'xhs';
  if (['wechat', 'weixin', 'wx'].includes(normalized)) return 'wechat';
  if (['zhihu', 'zh'].includes(normalized)) return 'zhihu';
  if (['en', 'english', 'launch', 'twitter', 'x', 'hn', 'showhn', 'show-hn', 'producthunt', 'product-hunt', 'ph', 'linkedin'].includes(normalized)) return 'en';
  return null;
}

function formatPromoCliOutput(result, aiContent, platform = 'all') {
  const promotions = aiContent?.promotions ?? {};
  const normalized = normalizePromo(platform) ?? 'all';
  const parts = [];

  if (normalized === 'all' || normalized === 'xhs') {
    parts.push(formatXhsPromoMarkdown(result, { ai: promotions.xiaohongshu }));
  }
  if (normalized === 'all' || normalized === 'wechat') {
    parts.push(formatWechatPromoMarkdown(result, { ai: promotions.wechatMoments }));
  }
  if (normalized === 'all' || normalized === 'zhihu') {
    parts.push(formatZhihuPromoMarkdown(result, { ai: promotions.zhihu }));
  }
  if (normalized === 'all' || normalized === 'en') {
    parts.push(formatPromoEnMarkdown(result, promotions));
  }
  if (normalized === 'all') {
    parts.push(formatPromoCopyMarkdown(result, aiContent));
  }

  return parts.filter(Boolean).join('\n\n');
}
