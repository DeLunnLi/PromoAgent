import { promises as fs } from 'node:fs';
import path from 'node:path';

const DEFAULT_IMAGE_BASE_URL = 'https://api.openai.com/v1';
const DEFAULT_IMAGE_MODEL = 'gpt-image-2';
const DEFAULT_MODELSCOPE_BASE_URL = 'https://api-inference.modelscope.cn';
const DEFAULT_MODELSCOPE_IMAGE_MODEL = 'FireRedTeam/FireRed-Image-Edit-1.1';
const DEFAULT_GRADIO_BASE_URL = 'http://127.0.0.1:7860';

const IMAGE_PROVIDER_PRESETS = {
  custom: {
    label: 'Custom image provider',
    baseUrl: DEFAULT_IMAGE_BASE_URL,
    model: DEFAULT_IMAGE_MODEL,
    apiKeyEnv: ['SOURCE2LAUNCH_IMAGE_API_KEY', 'SOURCE2LAUNCH_API_KEY', 'STAR_UP_IMAGE_API_KEY', 'STAR_UP_API_KEY'],
    baseUrlEnv: ['SOURCE2LAUNCH_IMAGE_BASE_URL', 'SOURCE2LAUNCH_BASE_URL', 'STAR_UP_IMAGE_BASE_URL', 'STAR_UP_BASE_URL'],
    modelEnv: ['SOURCE2LAUNCH_IMAGE_MODEL', 'STAR_UP_IMAGE_MODEL']
  },
  openai: {
    label: 'OpenAI Images API',
    baseUrl: DEFAULT_IMAGE_BASE_URL,
    model: DEFAULT_IMAGE_MODEL,
    apiKeyEnv: ['SOURCE2LAUNCH_IMAGE_API_KEY', 'STAR_UP_IMAGE_API_KEY', 'OPENAI_API_KEY'],
    baseUrlEnv: ['SOURCE2LAUNCH_IMAGE_BASE_URL', 'STAR_UP_IMAGE_BASE_URL', 'OPENAI_BASE_URL'],
    modelEnv: ['SOURCE2LAUNCH_IMAGE_MODEL', 'STAR_UP_IMAGE_MODEL', 'OPENAI_IMAGE_MODEL']
  },
  modelscope: {
    label: 'ModelScope API Inference',
    baseUrl: DEFAULT_MODELSCOPE_BASE_URL,
    model: DEFAULT_MODELSCOPE_IMAGE_MODEL,
    apiKeyEnv: ['MODELSCOPE_API_TOKEN', 'MODELSCOPE_API_KEY', 'SOURCE2LAUNCH_IMAGE_API_KEY', 'STAR_UP_IMAGE_API_KEY'],
    baseUrlEnv: ['MODELSCOPE_BASE_URL', 'MODELSCOPE_API_BASE_URL', 'SOURCE2LAUNCH_IMAGE_BASE_URL', 'STAR_UP_IMAGE_BASE_URL'],
    modelEnv: ['MODELSCOPE_IMAGE_MODEL', 'SOURCE2LAUNCH_IMAGE_MODEL', 'STAR_UP_IMAGE_MODEL'],
    asyncMode: true,
    taskType: 'image_generation'
  },
  gradio: {
    label: 'Local Gradio image app',
    baseUrl: DEFAULT_GRADIO_BASE_URL,
    model: 'gradio-generate-image',
    apiKeyEnv: [],
    baseUrlEnv: ['SOURCE2LAUNCH_GRADIO_BASE_URL', 'STAR_UP_GRADIO_BASE_URL', 'GRADIO_BASE_URL', 'SOURCE2LAUNCH_IMAGE_BASE_URL', 'STAR_UP_IMAGE_BASE_URL'],
    modelEnv: ['SOURCE2LAUNCH_GRADIO_API_NAME', 'STAR_UP_GRADIO_API_NAME', 'SOURCE2LAUNCH_IMAGE_MODEL', 'STAR_UP_IMAGE_MODEL'],
    asyncMode: true
  }
};

export function imageConfig(options = {}, env = process.env, settings = {}) {
  const provider = normalizeImageProvider(options.provider || env.SOURCE2LAUNCH_IMAGE_PROVIDER || env.STAR_UP_IMAGE_PROVIDER || 'openai');
  const preset = IMAGE_PROVIDER_PRESETS[provider] ?? IMAGE_PROVIDER_PRESETS.custom;
  const apiKey = options.apiKey
    || env.SOURCE2LAUNCH_IMAGE_API_KEY
    || env.STAR_UP_IMAGE_API_KEY
    || firstEnv(env, preset.apiKeyEnv)
    || env.OPENAI_API_KEY
    || null;

  if (!apiKey && (settings.requireApiKey ?? false) && preset.apiKeyEnv.length > 0) {
    throw new Error(`Missing image API key for ${preset.label}. Pass --image-api-key or set SOURCE2LAUNCH_IMAGE_API_KEY / STAR_UP_IMAGE_API_KEY / ${preset.apiKeyEnv.join(' / ')}.`);
  }

  return {
    apiKey,
    provider,
    providerLabel: preset.label,
    asyncMode: booleanOption(options.asyncMode ?? env.SOURCE2LAUNCH_IMAGE_ASYNC_MODE ?? env.STAR_UP_IMAGE_ASYNC_MODE ?? preset.asyncMode ?? false),
    baseUrl: trimTrailingSlash(options.baseUrl || env.SOURCE2LAUNCH_IMAGE_BASE_URL || env.STAR_UP_IMAGE_BASE_URL || firstEnv(env, preset.baseUrlEnv) || preset.baseUrl),
    imageUrl: cleanText(options.imageUrl || env.SOURCE2LAUNCH_IMAGE_URL || env.STAR_UP_IMAGE_URL) || null,
    editCustomSize: booleanOption(options.editCustomSize ?? env.SOURCE2LAUNCH_GRADIO_EDIT_CUSTOM_SIZE ?? env.STAR_UP_GRADIO_EDIT_CUSTOM_SIZE ?? false),
    gradioApiName: cleanApiName(options.gradioApiName || env.SOURCE2LAUNCH_GRADIO_API_NAME || env.STAR_UP_GRADIO_API_NAME || 'generate_image'),
    gradioPathPrefix: cleanPathPrefix(options.gradioPathPrefix ?? env.SOURCE2LAUNCH_GRADIO_PATH_PREFIX ?? env.STAR_UP_GRADIO_PATH_PREFIX ?? 'gradio_api'),
    loras: parseLoras(options.loras ?? env.SOURCE2LAUNCH_IMAGE_LORAS ?? env.STAR_UP_IMAGE_LORAS),
    model: options.model || env.SOURCE2LAUNCH_IMAGE_MODEL || env.STAR_UP_IMAGE_MODEL || firstEnv(env, preset.modelEnv) || preset.model,
    outputFormat: normalizeOutputFormat(options.outputFormat || env.SOURCE2LAUNCH_IMAGE_OUTPUT_FORMAT || env.STAR_UP_IMAGE_OUTPUT_FORMAT || 'png'),
    pollIntervalMs: Number(options.pollIntervalMs || env.SOURCE2LAUNCH_IMAGE_POLL_INTERVAL_MS || env.STAR_UP_IMAGE_POLL_INTERVAL_MS || 5000),
    promptExtend: booleanOption(options.promptExtend ?? env.SOURCE2LAUNCH_GRADIO_PROMPT_EXTEND ?? env.STAR_UP_GRADIO_PROMPT_EXTEND ?? true),
    quality: normalizeQuality(options.quality || env.SOURCE2LAUNCH_IMAGE_QUALITY || env.STAR_UP_IMAGE_QUALITY || 'medium'),
    randomizeSeed: booleanOption(options.randomizeSeed ?? env.SOURCE2LAUNCH_GRADIO_RANDOMIZE_SEED ?? env.STAR_UP_GRADIO_RANDOMIZE_SEED ?? true),
    negativePrompt: cleanText(options.negativePrompt ?? env.SOURCE2LAUNCH_GRADIO_NEGATIVE_PROMPT ?? env.STAR_UP_GRADIO_NEGATIVE_PROMPT ?? ' '),
    seed: Number(options.seed ?? env.SOURCE2LAUNCH_GRADIO_SEED ?? env.STAR_UP_GRADIO_SEED ?? 0),
    size: options.size || env.SOURCE2LAUNCH_IMAGE_SIZE || env.STAR_UP_IMAGE_SIZE || null,
    taskTimeoutMs: Number(options.taskTimeoutMs || env.SOURCE2LAUNCH_IMAGE_TASK_TIMEOUT_MS || env.STAR_UP_IMAGE_TASK_TIMEOUT_MS || 180_000),
    taskType: options.taskType || env.SOURCE2LAUNCH_IMAGE_TASK_TYPE || env.STAR_UP_IMAGE_TASK_TYPE || preset.taskType || null
  };
}

export function generateImageAssetPlan(result, options = {}) {
  const channel = normalizeChannel(options.channel || options.platform || 'xhs');
  const project = result.project;
  const audience = cleanText(options.audience) || inferAudience(project);
  const tone = normalizeTone(options.tone);
  const highlights = sourceHighlights(result);
  const installCommand = project.installCommand || 'source2launch promote .';
  const base = {
    audience,
    channel,
    inputType: result.inputType,
    project: project.name,
    repositoryUrl: project.repositoryUrl,
    tone
  };

  const assets = channel === 'wechat-article'
    ? wechatArticleAssets(project, highlights, installCommand, base)
    : channel === 'wechat-moments'
      ? wechatMomentsAssets(project, highlights, installCommand, base)
      : channel === 'zhihu'
        ? zhihuAssets(project, highlights, installCommand, base)
        : xhsAssets(project, highlights, installCommand, base);

  return {
    ...base,
    assets
  };
}

export function generateImageEditAssetPlan(result, options = {}) {
  const project = result.project;
  const audience = cleanText(options.audience) || inferAudience(project);
  const tone = normalizeTone(options.tone);
  const prompt = cleanText(options.prompt) || [
    `Edit the input image into a polished promotion image for ${project.name}.`,
    'Keep the original subject recognizable, improve layout and readability, add a clean developer-tool launch style, and leave space for platform copy.',
    `Audience: ${audience}. Tone: ${tone}.`,
    'Do not add unsupported claims or fake brand logos.'
  ].join(' ');
  const sourceImages = normalizeFileList(options.sourceImages ?? options.imageInput).filter(Boolean);
  const imageUrl = cleanText(options.imageUrl) || null;
  const mask = cleanText(options.mask) || null;

  return {
    audience,
    channel: 'image-edit',
    project: project.name,
    repositoryUrl: project.repositoryUrl,
    tone,
    assets: [
      {
        id: cleanText(options.id) || 'promotion-image-edit',
        channel: 'image-edit',
        operation: 'edit',
        title: 'Promotion image edit',
        purpose: 'Edit an existing image into a promotion-ready asset.',
        size: options.size || '1024x1024',
        quality: normalizeQuality(options.quality || 'medium'),
        prompt,
        textLayers: normalizeFileList(options.textLayers).filter(Boolean),
        sourceHints: [
          imageUrl ? `Input image URL: ${imageUrl}` : null,
          sourceImages.length > 0 ? `Input image files: ${sourceImages.join(', ')}` : null,
          mask ? `Mask file: ${mask}` : null
        ].filter(Boolean),
        ...(imageUrl ? { imageUrl } : {}),
        ...(sourceImages.length > 0 ? { sourceImages } : {}),
        ...(mask ? { mask } : {})
      }
    ]
  };
}

export function formatImageAssetPlan(plan) {
  const lines = [];
  lines.push(`# Image asset plan for ${plan.project}`);
  lines.push('');
  lines.push(`Channel: ${plan.channel}`);
  lines.push(`Audience: ${plan.audience}`);

  for (const asset of plan.assets) {
    lines.push('');
    lines.push(`## ${asset.title}`);
    lines.push('');
    lines.push(`- ID: ${asset.id}`);
    lines.push(`- Size: ${asset.size}`);
    lines.push(`- Operation: ${asset.operation}`);
    lines.push(`- Purpose: ${asset.purpose}`);
    lines.push('');
    lines.push('Prompt:');
    lines.push(asset.prompt);

    const textLayers = asset.textLayers ?? [];
    const sourceHints = asset.sourceHints ?? [];

    if (textLayers.length > 0) {
      lines.push('');
      lines.push('Text layers:');
      for (const layer of textLayers) lines.push(`- ${layer}`);
    }

    if (sourceHints.length > 0) {
      lines.push('');
      lines.push('Source hints:');
      for (const hint of sourceHints) lines.push(`- ${hint}`);
    }
  }

  return lines.join('\n');
}

export function buildImageApiRequests(plan, options = {}, env = process.env) {
  const config = imageConfig(options, env, { requireApiKey: false });
  return {
    provider: config.provider,
    providerLabel: config.providerLabel,
    asyncMode: config.asyncMode,
    baseUrl: config.baseUrl,
    imageUrl: config.imageUrl,
    model: config.model,
    outputFormat: config.outputFormat,
    pollIntervalMs: config.pollIntervalMs,
    quality: config.quality,
    taskTimeoutMs: config.taskTimeoutMs,
    taskType: config.taskType,
    requests: plan.assets.map((asset) => buildImageRequest(asset, config))
  };
}

export function formatImageApiRequests(preview) {
  return JSON.stringify(preview, null, 2);
}

export async function generateImageAsset(asset, options = {}, env = process.env) {
  const config = imageConfig(options, env, { requireApiKey: true });
  const request = buildImageRequest(asset, config);

  if (request.provider === 'modelscope') {
    return postModelScopeImageRequest(request, config);
  }

  if (request.provider === 'gradio') {
    return postGradioImageRequest(request, config);
  }

  if (request.operation === 'edit') {
    return postMultipartImageRequest(request, config);
  }

  return postJsonImageRequest(request, config);
}

export async function generateImageFromPrompt(input = {}, options = {}, env = process.env) {
  const prompt = cleanText(input.prompt);
  if (!prompt) {
    throw new Error('Image generation requires a prompt.');
  }

  return generateImageAsset({
    id: cleanText(input.id) || 'api-image-generation',
    operation: 'generate',
    prompt,
    size: input.size,
    quality: input.quality,
    n: input.n,
    imageUrl: input.imageUrl ?? input.image_url,
    imageBase64: input.imageBase64 ?? input.image_base64
  }, options, env);
}

export async function pollImageTask(taskId, options = {}, env = process.env) {
  const config = imageConfig(options, env, { requireApiKey: true });
  if (config.provider !== 'modelscope') {
    throw new Error(`Task polling is not implemented for image provider: ${config.provider}`);
  }
  return pollModelScopeTask(taskId, config);
}

async function postModelScopeImageRequest(request, config) {
  const response = await fetch(request.endpoint, {
    method: request.method,
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      'Content-Type': 'application/json',
      ...(config.asyncMode ? { 'X-ModelScope-Async-Mode': 'true' } : {})
    },
    body: JSON.stringify(request.body)
  });
  const data = await parseJsonResponse(response);

  if (!config.asyncMode || !data.task_id) {
    return data;
  }

  return pollModelScopeTask(data.task_id, config);
}

async function pollModelScopeTask(taskId, config) {
  const deadline = Date.now() + config.taskTimeoutMs;
  const endpoint = `${config.baseUrl}/v1/tasks/${taskId}`;

  while (Date.now() < deadline) {
    const response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        ...(config.taskType ? { 'X-ModelScope-Task-Type': config.taskType } : {})
      }
    });
    const data = await parseJsonResponse(response);

    if (data.task_status === 'SUCCEED') return data;
    if (data.task_status === 'FAILED') {
      throw new Error(`ModelScope image task failed: ${JSON.stringify(data).slice(0, 500)}`);
    }

    await sleep(config.pollIntervalMs);
  }

  throw new Error(`ModelScope image task timed out after ${config.taskTimeoutMs}ms: ${taskId}`);
}

async function postGradioImageRequest(request, config) {
  let endpoint = request.endpoint;
  let response = await fetch(endpoint, {
    method: request.method,
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request.body)
  });
  if (response.status === 404 && endpoint.includes('/gradio_api/call/')) {
    endpoint = endpoint.replace('/gradio_api/call/', '/call/');
    response = await fetch(endpoint, {
      method: request.method,
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request.body)
    });
  }
  const data = await parseJsonResponse(response);
  if (!data.event_id) return data;
  return pollGradioTask(data.event_id, { ...request, endpoint }, config);
}

async function pollGradioTask(eventId, request, config) {
  const deadline = Date.now() + config.taskTimeoutMs;
  const endpoint = `${request.endpoint}/${eventId}`;

  while (Date.now() < deadline) {
    const response = await fetch(endpoint, { method: 'GET' });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`Gradio image task failed (${response.status}): ${text.slice(0, 500)}`);
    }
    const event = parseGradioEventStream(text);
    if (event.status === 'complete') return event.data;
    if (event.status === 'error') {
      throw new Error(`Gradio image task failed: ${text.slice(0, 500)}`);
    }
    await sleep(config.pollIntervalMs);
  }

  throw new Error(`Gradio image task timed out after ${config.taskTimeoutMs}ms: ${eventId}`);
}

function parseGradioEventStream(text) {
  const lines = String(text ?? '').split('\n');
  let status = 'pending';
  let data = null;
  for (const line of lines) {
    if (line.startsWith('event:')) {
      const eventName = line.slice('event:'.length).trim();
      if (eventName === 'complete') status = 'complete';
      if (eventName === 'error') status = 'error';
    }
    if (line.startsWith('data:')) {
      const raw = line.slice('data:'.length).trim();
      if (!raw || raw === 'null') continue;
      try {
        data = JSON.parse(raw);
      } catch {
        data = raw;
      }
    }
  }
  return { status, data };
}

async function parseJsonResponse(response) {
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Image provider request failed (${response.status}): ${text.slice(0, 500)}`);
  }
  return JSON.parse(text);
}

async function postJsonImageRequest(request, config) {
  const response = await fetch(request.endpoint, {
    method: request.method,
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request.body)
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Image provider request failed (${response.status}): ${text.slice(0, 500)}`);
  }
  return JSON.parse(text);
}

async function postMultipartImageRequest(request, config) {
  const imageFiles = request.files?.image ?? [];
  if (imageFiles.length === 0) {
    throw new Error('Image edit requests require at least one source image.');
  }

  const form = new FormData();
  for (const [key, value] of Object.entries(request.form ?? {})) {
    if (value !== null && value !== undefined) form.append(key, String(value));
  }

  for (const image of imageFiles) {
    const file = await fileRefToBlob(image);
    form.append('image[]', file.blob, file.filename);
  }

  if (request.files.mask) {
    const mask = await fileRefToBlob(request.files.mask);
    form.append('mask', mask.blob, mask.filename);
  }

  const response = await fetch(request.endpoint, {
    method: request.method,
    headers: {
      Authorization: `Bearer ${config.apiKey}`
    },
    body: form
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Image provider request failed (${response.status}): ${text.slice(0, 500)}`);
  }
  return JSON.parse(text);
}

function buildImageRequest(asset, config) {
  const operation = asset.operation || 'generate';
  if (!['generate', 'edit'].includes(operation)) {
    throw new Error(`Unsupported image operation: ${operation}`);
  }
  if (config.provider === 'modelscope') {
    return buildModelScopeImageRequest(asset, config, operation);
  }

  if (config.provider === 'gradio') {
    return buildGradioImageRequest(asset, config, operation);
  }

  const path = operation === 'edit' ? '/images/edits' : '/images/generations';
  const commonBody = {
    model: config.model,
    prompt: asset.prompt,
    size: asset.size || config.size || '1024x1536',
    quality: asset.quality || config.quality,
    output_format: config.outputFormat,
    n: normalizedCount(asset.n || config.n || 1)
  };
  const request = {
    assetId: asset.id,
    operation,
    method: 'POST',
    endpoint: `${config.baseUrl}${path}`
  };

  if (operation === 'edit') {
    return {
      ...request,
      contentType: 'multipart/form-data',
      form: commonBody,
      files: {
        image: normalizeFileList(asset.sourceImages ?? asset.images ?? asset.image),
        mask: asset.mask ?? null
      },
      note: 'Image edits use multipart/form-data with image[] files and an optional mask.'
    };
  }

  return {
    ...request,
    contentType: 'application/json',
    body: commonBody
  };
}

function buildModelScopeImageRequest(asset, config, operation) {
  const imageUrl = cleanText(asset.imageUrl ?? asset.image_url ?? config.imageUrl) || null;
  const imageBase64 = cleanText(asset.imageBase64 ?? asset.image_base64) || null;
  const body = {
    model: config.model,
    prompt: asset.prompt
  };

  if (config.loras) body.loras = config.loras;
  if (imageUrl) body.image_url = imageUrl;
  if (imageBase64) body.image = imageBase64;

  return {
    assetId: asset.id,
    provider: config.provider,
    operation,
    method: 'POST',
    endpoint: `${config.baseUrl}/v1/images/generations`,
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer <redacted>',
      'Content-Type': 'application/json',
      ...(config.asyncMode ? { 'X-ModelScope-Async-Mode': 'true' } : {})
    },
    body,
    poll: config.asyncMode ? {
      method: 'GET',
      endpoint: `${config.baseUrl}/v1/tasks/{task_id}`,
      headers: {
        Authorization: 'Bearer <redacted>',
        ...(config.taskType ? { 'X-ModelScope-Task-Type': config.taskType } : {})
      },
      intervalMs: config.pollIntervalMs,
      timeoutMs: config.taskTimeoutMs,
      successStatus: 'SUCCEED',
      failureStatus: 'FAILED',
      outputField: 'output_images'
    } : null,
    note: imageUrl || imageBase64
      ? 'ModelScope async image request. Poll task_id until task_status is SUCCEED.'
      : 'ModelScope image edit models usually require image_url or base64 image input.'
  };
}

function buildGradioImageRequest(asset, config, operation) {
  const dimensions = sizeToDimensions(config.size || asset.size || '2688x1536');
  const inputImages = normalizeGradioInputImages(asset);
  const data = [
    inputImages,
    asset.prompt,
    config.promptExtend,
    config.editCustomSize,
    Number.isFinite(config.seed) ? config.seed : 0,
    config.randomizeSeed,
    dimensions.height,
    dimensions.width,
    config.negativePrompt || ' '
  ];
  const prefix = config.gradioPathPrefix ? `/${config.gradioPathPrefix}` : '';
  const endpoint = `${config.baseUrl}${prefix}/call/${config.gradioApiName}`;

  return {
    assetId: asset.id,
    provider: config.provider,
    operation,
    method: 'POST',
    endpoint,
    contentType: 'application/json',
    body: { data },
    data,
    gradio: {
      apiName: `/${config.gradioApiName}`,
      output: ['result_image', 'seed', 'queue_status']
    },
    note: 'Gradio named endpoint call. POST returns an event_id; GET endpoint/event_id streams the generated image result.'
  };
}

function zhihuAssets(project, highlights, installCommand, base) {
  return [
    {
      id: 'zhihu-answer-header',
      channel: 'zhihu',
      operation: 'generate',
      title: 'Zhihu answer header',
      purpose: 'Header image for a credible technical answer.',
      size: '1536x864',
      quality: 'medium',
      textLayers: [
        base.inputType === 'paper' ? '这篇论文解决了什么问题' : '这个项目解决了什么问题',
        project.name,
        '结论 / 证据 / 局限'
      ],
      sourceHints: ['Use as the first image in a Zhihu answer. Avoid clickbait and unsupported metrics.'],
      prompt: [
        `Create a landscape header image for a Zhihu technical answer about ${project.name}.`,
        `Source type: ${base.inputType}.`,
        'Visual style: editorial, clean, credible, suitable for a long-form technical explanation.',
        `Highlight the answer structure: conclusion, evidence, limitations, and who should read it.`,
        `Evidence-backed highlights: ${highlights.join('; ') || project.description}.`,
        `Audience: ${base.audience}. Tone: ${base.tone}.`,
        'Leave readable Chinese headline space and avoid marketing-style exaggeration.'
      ].join(' ')
    },
    {
      id: 'zhihu-evidence-card',
      channel: 'zhihu',
      operation: 'generate',
      title: 'Evidence figure card',
      purpose: 'Explain the strongest paper figure, abstract crop, README snippet, or result table.',
      size: '1536x864',
      quality: 'medium',
      textLayers: [
        '证据截图',
        '为什么这个点重要',
        '来源说明'
      ],
      sourceHints: [
        'Pair with an abstract crop, method figure, result table, or README snippet.',
        `Use command only when relevant: ${installCommand}`
      ],
      prompt: [
        `Create a landscape evidence card for ${project.name}.`,
        'The card should have one area for a source screenshot or paper figure and one area for a concise explanation.',
        `Ground the claim in these highlights: ${highlights.join('; ') || project.description}.`,
        'Use a restrained technical style and keep text short enough for mobile reading.'
      ].join(' ')
    },
    {
      id: 'zhihu-limitations-card',
      channel: 'zhihu',
      operation: 'generate',
      title: 'Limitations and reader fit card',
      purpose: 'Make the promotion credible by naming caveats and target readers.',
      size: '1536x864',
      quality: 'medium',
      textLayers: [
        '适合谁读',
        '需要注意什么',
        '下一步怎么用'
      ],
      sourceHints: ['Use after the main claim to reduce overstatement and improve trust.'],
      prompt: [
        `Create a landscape card for a Zhihu answer about ${project.name}.`,
        'Show three sections: who should read it, caveats, and what to try next.',
        `Use source-backed highlights: ${highlights.join('; ') || project.description}.`,
        `If it is a repository, include this command only if useful: ${installCommand}.`,
        'Avoid fake benchmark numbers, awards, logos, or claims not present in the source.'
      ].join(' ')
    }
  ];
}

function xhsAssets(project, highlights, installCommand, base) {
  return [
    {
      id: 'xhs-cover',
      channel: 'xhs',
      operation: 'generate',
      title: 'Xiaohongshu cover',
      purpose: 'First card that explains the source in one glance.',
      size: '1024x1536',
      quality: 'medium',
      textLayers: [
        base.inputType === 'paper' ? '论文速读' : '开源项目速览',
        '适合发推的亮点',
        project.name
      ],
      sourceHints: ['Use project name, source type, and the strongest evidence-backed highlight.'],
      prompt: [
        `Create a vertical Xiaohongshu cover image for ${base.inputType === 'paper' ? 'a research paper' : 'an open source project'} named ${project.name}.`,
        'Style: clean modern developer-tool poster, high contrast, readable Chinese text areas, terminal-inspired visual elements, no logos copied from real brands.',
        `Main message: ${base.inputType === 'paper' ? '论文速读：一个值得发推的研究亮点' : '开源项目速览：一个值得发推的技术亮点'}.`,
        `Audience: ${base.audience}. Tone: ${base.tone}.`,
        `Highlights to visualize: ${highlights.join('; ') || project.description}.`,
        'Leave clear space for the text layers and avoid clutter.'
      ].join(' ')
    },
    {
      id: 'xhs-terminal',
      channel: 'xhs',
      operation: 'generate',
      title: 'Evidence card',
      purpose: 'Show the evidence that grounds the generated tweet.',
      size: '1024x1536',
      quality: 'medium',
      textLayers: [
        installCommand,
        'Source evidence',
        'Tweet angle'
      ],
      sourceHints: ['Use command, README/source excerpt, and tweet angle.'],
      prompt: [
        `Create a vertical social card showing source evidence for ${project.name}.`,
        `If it is a repository, include this command when useful: ${installCommand}.`,
        `Use these evidence-backed highlights: ${highlights.join('; ') || project.description}.`,
        'Use realistic terminal UI, sharp typography, and enough margin for mobile reading.'
      ].join(' ')
    },
    {
      id: 'xhs-before-after',
      channel: 'xhs',
      operation: 'generate',
      title: 'Thread structure card',
      purpose: 'Preview the structure of a social thread.',
      size: '1024x1536',
      quality: 'medium',
      textLayers: [
        '1. 它是什么',
        '2. 为什么有意思',
        '3. 适合谁看'
      ],
      sourceHints: ['Show a tweet/thread outline without unsupported claims.'],
      prompt: [
        `Create a vertical card that previews a three-part tweet thread for ${project.name}.`,
        `The thread should be grounded in these highlights: ${highlights.join('; ') || project.description}.`,
        'Chinese text should be short and legible. Avoid hype and unsupported claims.'
      ].join(' ')
    }
  ];
}

function wechatMomentsAssets(project, highlights, installCommand, base) {
  return [
    {
      id: 'wechat-moments-summary',
      channel: 'wechat-moments',
      operation: 'generate',
      title: 'WeChat Moments summary card',
      purpose: 'Compact share card for friends and developer circles.',
      size: '1024x1024',
      quality: 'medium',
      textLayers: [
        project.name,
        base.inputType === 'paper' ? 'paper brief' : 'project brief',
        installCommand
      ],
      sourceHints: ['Square card, suitable for WeChat Moments.'],
      prompt: [
        `Create a square WeChat Moments image for ${project.name}.`,
        `Message: summarize the most tweetable idea from this ${base.inputType}.`,
        `Show command only if relevant: ${installCommand}`,
        `Highlights: ${highlights.join('; ') || project.description}.`,
        `Audience: ${base.audience}. Keep it understated and credible.`
      ].join(' ')
    },
    {
      id: 'wechat-moments-highlights',
      channel: 'wechat-moments',
      operation: 'generate',
      title: 'Highlights card',
      purpose: 'Show the strongest points without long copy.',
      size: '1024x1024',
      quality: 'medium',
      textLayers: highlights.length > 0 ? highlights : ['核心问题', '方法亮点', '适合读者'],
      sourceHints: ['Use as second image in a WeChat Moments post.'],
      prompt: [
        `Create a square highlight checklist image for ${project.name}.`,
        `Show source-backed highlights: ${highlights.join('; ') || project.description}.`,
        'Use clean checklist layout and developer-friendly typography.'
      ].join(' ')
    }
  ];
}

function wechatArticleAssets(project, highlights, installCommand, base) {
  return [
    {
      id: 'wechat-article-header',
      channel: 'wechat-article',
      operation: 'generate',
      title: 'WeChat article header',
      purpose: 'Header image for a longer official-account article.',
      size: '1536x1024',
      quality: 'medium',
      textLayers: [
        base.inputType === 'paper' ? '这篇论文讲了什么' : '这个开源项目讲了什么',
        project.name
      ],
      sourceHints: ['Use as the first image in a WeChat article.'],
      prompt: [
        `Create a landscape header image for a WeChat official-account article about ${project.name}.`,
        'Theme: technical explanation, source-grounded highlights, and social post preparation.',
        `Audience: ${base.audience}. Tone: ${base.tone}.`,
        'Professional editorial layout, clear Chinese headline area, no unsupported claims.'
      ].join(' ')
    },
    {
      id: 'wechat-article-thread',
      channel: 'wechat-article',
      operation: 'generate',
      title: 'Thread outline image',
      purpose: 'Visual explanation of the tweet/thread outline.',
      size: '1536x1024',
      quality: 'medium',
      textLayers: [
        'Tweet angle',
        'Evidence',
        'Audience'
      ],
      sourceHints: ['Use after the article introduction to explain the source-backed thread.'],
      prompt: [
        `Create a landscape infographic for ${project.name}.`,
        `Show a tweet/thread outline grounded in evidence: ${highlights.join('; ') || project.description}.`,
        `Include command only if useful: ${installCommand}.`,
        'Keep text short and legible.'
      ].join(' ')
    }
  ];
}

function inferAudience(project) {
  const text = `${project.description} ${project.topics.join(' ')}`.toLowerCase();
  if (/paper|arxiv|research|benchmark|dataset|method/.test(text)) {
    return 'researchers, engineers, and technical readers';
  }
  if (/readme|github|repo|open-source|promotion/.test(text)) {
    return 'developers and open source users';
  }
  if (/ai|llm|agent/.test(text)) return 'AI builders and agent developers';
  if (/cli|terminal/.test(text)) return 'developers who use command-line tools';
  return 'technical readers and developers';
}

function sourceHighlights(result) {
  const evidence = result.evidence ?? {};
  const headings = Array.isArray(evidence.headings)
    ? evidence.headings.map((heading) => heading.text).filter(Boolean)
    : [];
  const topics = result.project?.topics ?? [];
  return [
    result.project?.description,
    ...topics.slice(0, 3).map((topic) => `Topic: ${topic}`),
    ...headings.slice(0, 3).map((heading) => `Section: ${heading}`),
    ...(evidence.installCommands?.[0] ? [`Command: ${evidence.installCommands[0]}`] : [])
  ]
    .map((item) => cleanText(item))
    .filter(Boolean)
    .slice(0, 5);
}

function normalizeChannel(value) {
  const normalized = cleanText(value).toLowerCase();
  if (['zhihu', 'zhi-hu'].includes(normalized)) return 'zhihu';
  if (['wechat-moments', 'moments', 'pyq'].includes(normalized)) return 'wechat-moments';
  if (['wechat-article', 'wechat-official', 'official-account', 'mp', 'gzh'].includes(normalized)) return 'wechat-article';
  return 'xhs';
}

function normalizeImageProvider(value) {
  const normalized = cleanText(value).toLowerCase();
  if (normalized === 'openai') return 'openai';
  if (['modelscope', 'model-scope', 'ms'].includes(normalized)) return 'modelscope';
  if (['gradio', 'local-gradio', 'gradio-client'].includes(normalized)) return 'gradio';
  return 'custom';
}

function normalizeTone(value) {
  const normalized = cleanText(value).toLowerCase();
  if (['casual', 'friendly'].includes(normalized)) return 'casual';
  if (['professional', 'formal'].includes(normalized)) return 'professional';
  if (['launch', 'promo'].includes(normalized)) return 'launch';
  return 'balanced';
}

function normalizeOutputFormat(value) {
  const normalized = cleanText(value).toLowerCase();
  if (['jpeg', 'jpg'].includes(normalized)) return 'jpeg';
  if (normalized === 'webp') return 'webp';
  return 'png';
}

function normalizeQuality(value) {
  const normalized = cleanText(value).toLowerCase();
  if (['low', 'medium', 'high', 'auto'].includes(normalized)) return normalized;
  return 'medium';
}

function normalizedCount(value) {
  const count = Number(value);
  if (!Number.isFinite(count) || count < 1) return 1;
  return Math.min(Math.floor(count), 10);
}

function sizeToDimensions(size) {
  const match = String(size ?? '').match(/(\d+)\s*x\s*(\d+)/i);
  if (!match) return { width: 2688, height: 1536 };
  return {
    width: Number(match[1]),
    height: Number(match[2])
  };
}

function normalizeGradioInputImages(asset) {
  const refs = [
    ...normalizeFileList(asset.sourceImages ?? asset.images ?? asset.image),
    asset.imageUrl ?? asset.image_url
  ].filter(Boolean);

  return refs.map((ref) => {
    const text = cleanText(ref);
    const isUrl = /^https?:\/\//i.test(text) || /^data:/i.test(text);
    return {
      image: {
        path: isUrl ? null : text,
        url: isUrl ? text : null,
        size: null,
        orig_name: isUrl ? null : text.split('/').pop(),
        mime_type: null,
        is_stream: false,
        meta: {}
      },
      caption: null
    };
  });
}

function cleanApiName(value) {
  return cleanText(value || 'generate_image').replace(/^\/+/, '');
}

function cleanPathPrefix(value) {
  return cleanText(value).replace(/^\/+|\/+$/g, '');
}

function firstEnv(env, names = []) {
  for (const name of names) {
    const value = env[name];
    if (value) return value;
  }
  return '';
}

function cleanText(value) {
  return String(value ?? '').trim();
}

function trimTrailingSlash(value) {
  return String(value).replace(/\/+$/, '');
}

function booleanOption(value) {
  if (typeof value === 'boolean') return value;
  const normalized = cleanText(value).toLowerCase();
  if (['true', '1', 'yes', 'y', 'on'].includes(normalized)) return true;
  if (['false', '0', 'no', 'n', 'off'].includes(normalized)) return false;
  return Boolean(value);
}

function parseLoras(value) {
  if (value && typeof value === 'object') return value;
  const normalized = cleanText(value);
  if (!normalized) return null;
  if (!normalized.startsWith('{')) return normalized;

  try {
    return JSON.parse(normalized);
  } catch (error) {
    throw new Error(`Invalid image LoRA JSON: ${error.message}`);
  }
}

function normalizeFileList(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

async function fileRefToBlob(fileRef) {
  if (typeof Blob !== 'undefined' && fileRef instanceof Blob) {
    return {
      blob: fileRef,
      filename: fileRef.name || 'image.png'
    };
  }

  if (typeof fileRef === 'string') {
    const data = await fs.readFile(fileRef);
    return {
      blob: new Blob([data], { type: mimeTypeForPath(fileRef) }),
      filename: path.basename(fileRef)
    };
  }

  if (fileRef?.path) {
    const data = await fs.readFile(fileRef.path);
    return {
      blob: new Blob([data], { type: fileRef.type || mimeTypeForPath(fileRef.path) }),
      filename: fileRef.name || path.basename(fileRef.path)
    };
  }

  if (fileRef?.data) {
    const blob = fileRef.data instanceof Blob
      ? fileRef.data
      : new Blob([fileRef.data], { type: fileRef.type || 'application/octet-stream' });
    return {
      blob,
      filename: fileRef.name || 'image.png'
    };
  }

  throw new Error('Unsupported image file reference. Use a file path, Blob, or { path, name, type }.');
}

function mimeTypeForPath(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.jpg' || ext === '.jpeg') return 'image/jpeg';
  if (ext === '.webp') return 'image/webp';
  if (ext === '.gif') return 'image/gif';
  return 'image/png';
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
