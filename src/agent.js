import { filterToolDefinitions } from './tools/definitions.js';
import { executeAgentTool } from './tools/executor.js';

const DEFAULT_MAX_STEPS = 8;

export function agentConfig(options = {}, env = process.env) {
  return {
    enabled: resolveAgentToolsEnabled(options, env),
    maxSteps: Number(options.agentMaxSteps ?? env.SOURCE2LAUNCH_AGENT_MAX_STEPS ?? env.STAR_UP_AGENT_MAX_STEPS ?? DEFAULT_MAX_STEPS),
    enabledTools: parseToolList(options.agentTools ?? env.SOURCE2LAUNCH_AGENT_TOOL_LIST ?? env.STAR_UP_AGENT_TOOL_LIST)
  };
}

export function resolveAgentToolsEnabled(options = {}, env = process.env) {
  if (options.tools === true || options.agentTools === true) return true;
  if (options.tools === false || options.noTools || options.agentTools === false) return false;
  return String(env.SOURCE2LAUNCH_AGENT_TOOLS ?? env.STAR_UP_AGENT_TOOLS ?? 'true').trim().toLowerCase() !== 'false';
}

export async function runToolAgent({
  callChat,
  messages,
  executeTool,
  tools,
  maxSteps = DEFAULT_MAX_STEPS,
  finalInstruction = 'Now output the final result as strict JSON only. No Markdown code fence, no commentary.'
}) {
  const toolDefinitions = filterToolDefinitions(tools);
  const transcript = [];
  let steps = 0;
  let workingMessages = [...messages];

  while (steps < maxSteps) {
    const response = await callChat(workingMessages, {
      tools: toolDefinitions,
      jsonMode: false
    });
    const message = response.choices?.[0]?.message;
    if (!message) {
      throw new Error('AI provider returned an empty agent message');
    }

    if (!Array.isArray(message.tool_calls) || message.tool_calls.length === 0) {
      if (message.content?.trim()) {
        return {
          content: message.content,
          toolCalls: transcript,
          steps
        };
      }

      workingMessages = [
        ...workingMessages,
        message,
        {
          role: 'user',
          content: finalInstruction
        }
      ];
      steps += 1;
      continue;
    }

    workingMessages.push(message);

    for (const toolCall of message.tool_calls) {
      const toolName = toolCall.function?.name;
      let args = {};
      try {
        args = JSON.parse(toolCall.function?.arguments || '{}');
      } catch {
        args = {};
      }

      let result;
      try {
        result = await executeTool(toolName, args);
      } catch (error) {
        result = { ok: false, error: error.message };
      }

      transcript.push({
        id: toolCall.id,
        name: toolName,
        args,
        result
      });

      workingMessages.push({
        role: 'tool',
        tool_call_id: toolCall.id,
        content: JSON.stringify(result)
      });
    }

    steps += 1;
  }

  const response = await callChat(
    [
      ...workingMessages,
      { role: 'user', content: finalInstruction }
    ],
    { jsonMode: true }
  );
  const content = response.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error('Agent exceeded max tool steps without producing JSON');
  }

  return {
    content,
    toolCalls: transcript,
    steps: maxSteps,
    forcedFinal: true
  };
}

export function buildAgentToolSystemAddendum() {
  return [
    '## 可用工具',
    '你可以调用工具辅助写作，但最终必须输出严格 JSON。',
    '- `web_search`：搜索各平台真实写法、Show HN 案例、竞品定位（先搜再写）',
    '- `fetch_page_text`：读取搜索结果中的公开网页摘要',
    '- `read_project_summary`：阅读并总结仓库 + 附加 PDF/文档（写文案前先理解项目）',
    '- `read_pdf_document`：解析本地 PDF 为结构化 Markdown（pdftotext → 内置解析 → OCR）',
    '- `read_repo_evidence`：读取仓库审计证据（引用 installCommand / launchRisks 前必调）',
    '- `generate_promo_image`：生成小红书/微信封面（若已配置 Gradio 或 ModelScope）',
    '',
    '工具使用原则：',
    '1. 写文案前先 `read_project_summary` 或 `read_repo_evidence`，有 PDF 时用 `read_pdf_document`',
    '2. 禁止编造 web_search 未证实、evidence 未出现的 star 增长/用户数',
    '3. 需要配图时调用 `generate_promo_image`，并在 markdown 的发布提示里引用生成路径',
    '4. 工具调用完成后，一次性输出完整 JSON（含所有平台 markdown 字段）'
  ].join('\n');
}

export function createDefaultToolExecutor(context = {}) {
  return (name, args) => executeAgentTool(name, args, context);
}

function parseToolList(value) {
  if (!value) return null;
  return String(value)
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}
