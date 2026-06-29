import { generateAiContent, formatAiProjectBriefMarkdown, hasAiKey, pickAiKey } from './ai.js';
import { buildProjectIntake } from './project-summary.js';

export { hasAiKey, pickAiKey };

export async function buildProjectIntakeWithAi(result, options = {}) {
  const intake = await buildProjectIntake(result, options);
  const wantAi = options.ai !== false;
  const canAi = hasAiKey(options.env);

  if (!wantAi || !canAi) {
    return {
      ...intake,
      summarySource: 'local',
      aiBrief: null,
      summaryMarkdown: formatLocalFallbackHeader(intake.summaryMarkdown, { wantAi, canAi })
    };
  }

  try {
    const ai = await generateAiContent(result, {
      brief: true,
      projectIntake: intake,
      baseUrl: options.baseUrl,
      env: options.env,
      model: options.model,
      maxTokens: options.maxTokens,
      noVision: options.noVision,
      vision: options.vision,
      stream: options.stream,
      apiKey: options.apiKey ?? pickAiKey(options.env)
    });

    return {
      ...intake,
      summarySource: 'ai',
      aiBrief: ai.content,
      aiModel: ai.model,
      summaryMarkdown: formatAiProjectBriefMarkdown(ai, result, intake)
    };
  } catch (error) {
    return {
      ...intake,
      summarySource: 'local',
      aiBrief: null,
      aiError: error.message,
      summaryMarkdown: formatLocalFallbackHeader(intake.summaryMarkdown, {
        wantAi: true,
        canAi: true,
        error: error.message
      })
    };
  }
}

function formatLocalFallbackHeader(markdown, meta = {}) {
  const notes = [];
  if (meta.wantAi && !meta.canAi) {
    notes.push('> 未配置 API Key，以下为本地证据摘要。配置 `SOURCE2LAUNCH_MODELSCOPE_API_KEY` 后重新运行，将由大模型阅读并介绍项目。');
  } else if (meta.error) {
    notes.push(`> 大模型阅读失败（${meta.error}），已回退本地证据摘要。`);
  } else if (meta.wantAi === false) {
    notes.push('> 本地证据摘要（`--local` 模式，未调用大模型）。');
  }
  if (notes.length === 0) return markdown;
  return `${notes.join('\n')}\n\n${markdown}`;
}
