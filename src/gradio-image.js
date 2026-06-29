import { promises as fs } from 'node:fs';
import path from 'node:path';

const DEFAULT_GRADIO_URL = 'http://127.0.0.1:7860';
const DEFAULT_API_NAME = 'generate_image';

export function gradioImageConfig(options = {}, env = process.env) {
  const baseUrl = trimTrailingSlash(
    options.gradioUrl
    || env.SOURCE2LAUNCH_GRADIO_URL
    || env.STAR_UP_GRADIO_URL
    || env.GRADIO_URL
    || DEFAULT_GRADIO_URL
  );
  const apiName = normalizeApiName(
    options.gradioApi
    || env.SOURCE2LAUNCH_GRADIO_API
    || env.STAR_UP_GRADIO_API
    || env.GRADIO_API
    || DEFAULT_API_NAME
  );

  return {
    provider: 'gradio',
    baseUrl,
    apiName,
    promptExtend: parseBoolean(options.promptExtend ?? env.SOURCE2LAUNCH_GRADIO_PROMPT_EXTEND ?? env.STAR_UP_GRADIO_PROMPT_EXTEND, true),
    editCustomSize: parseBoolean(options.editCustomSize ?? env.SOURCE2LAUNCH_GRADIO_EDIT_CUSTOM_SIZE ?? env.STAR_UP_GRADIO_EDIT_CUSTOM_SIZE, false),
    seed: Number(options.seed ?? env.SOURCE2LAUNCH_GRADIO_SEED ?? env.STAR_UP_GRADIO_SEED ?? 0),
    randomizeSeed: parseBoolean(options.randomizeSeed ?? env.SOURCE2LAUNCH_GRADIO_RANDOMIZE_SEED ?? env.STAR_UP_GRADIO_RANDOMIZE_SEED, true),
    negativePrompt: String(options.negativePrompt ?? env.SOURCE2LAUNCH_GRADIO_NEGATIVE_PROMPT ?? env.STAR_UP_GRADIO_NEGATIVE_PROMPT ?? ' '),
    pollIntervalMs: Number(options.pollIntervalMs ?? env.SOURCE2LAUNCH_GRADIO_POLL_MS ?? env.STAR_UP_GRADIO_POLL_MS ?? 2_000),
    timeoutMs: Number(options.timeoutMs ?? env.SOURCE2LAUNCH_GRADIO_TIMEOUT_MS ?? env.STAR_UP_GRADIO_TIMEOUT_MS ?? 600_000)
  };
}

export function resolveGradioDimensions(platform, env = process.env) {
  const normalized = String(platform ?? 'xhs').trim().toLowerCase();
  if (normalized === 'wechat') {
    const size = Number(env.SOURCE2LAUNCH_GRADIO_WECHAT_SIZE || env.STAR_UP_GRADIO_WECHAT_SIZE || 1536);
    return { width: size, height: size };
  }

  const width = Number(env.SOURCE2LAUNCH_GRADIO_WIDTH || env.STAR_UP_GRADIO_WIDTH || 2688);
  const height = Number(env.SOURCE2LAUNCH_GRADIO_HEIGHT || env.STAR_UP_GRADIO_HEIGHT || 1536);
  return { width, height };
}

export function buildGradioPredictPayload(prompt, config, dimensions = {}) {
  const width = Number(dimensions.width ?? 1536);
  const height = Number(dimensions.height ?? 2048);

  return [
    [],
    String(prompt).trim(),
    config.promptExtend,
    config.editCustomSize,
    config.seed,
    config.randomizeSeed,
    height,
    width,
    config.negativePrompt
  ];
}

export async function generateGradioImage(options = {}) {
  const config = gradioImageConfig(options);
  const prompt = String(options.prompt ?? '').trim();
  if (!prompt) {
    throw new Error('Image generation requires a prompt.');
  }

  const dimensions = options.dimensions || resolveGradioDimensions(options.platform, options.env);
  const data = buildGradioPredictPayload(prompt, config, dimensions);
  const eventId = await submitGradioCall(config, data);
  const result = await pollGradioCall(config, eventId);
  const imageRef = result.data?.[0];
  const seed = result.data?.[1];
  const imageUrl = resolveGradioImageUrl(imageRef, config.baseUrl);
  const buffer = await downloadImage(imageUrl);

  const outputPath = path.resolve(options.outputPath || 'promo-image.jpg');
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, buffer);

  return {
    provider: 'gradio',
    taskId: eventId,
    model: config.apiName,
    prompt,
    seed,
    remoteUrl: imageUrl,
    outputPath,
    queueStatus: result.data?.[2] ?? null,
    dimensions
  };
}

async function submitGradioCall(config, data) {
  const response = await fetch(`${config.baseUrl}/call/${config.apiName}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data })
  });

  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Gradio call failed (${response.status}): ${text.slice(0, 500)}`);
  }

  const payload = JSON.parse(text);
  if (!payload.event_id) {
    throw new Error('Gradio did not return event_id');
  }

  return payload.event_id;
}

async function pollGradioCall(config, eventId) {
  const started = Date.now();

  while (Date.now() - started < config.timeoutMs) {
    const response = await fetch(`${config.baseUrl}/call/${config.apiName}/${eventId}`);
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`Gradio poll failed (${response.status}): ${text.slice(0, 500)}`);
    }

    const payload = JSON.parse(text);
    const message = String(payload.msg ?? '');

    if (message === 'process_completed') {
      if (!payload.output?.data?.length) {
        throw new Error('Gradio completed but returned no output data');
      }
      return payload.output;
    }

    if (message === 'process_error') {
      const reason = payload.output?.error || payload.title || 'unknown error';
      throw new Error(`Gradio image generation failed: ${reason}`);
    }

    await sleep(config.pollIntervalMs);
  }

  throw new Error(`Gradio image generation timed out after ${config.timeoutMs}ms`);
}

function resolveGradioImageUrl(resultImage, baseUrl) {
  if (!resultImage) {
    throw new Error('Gradio returned an empty image');
  }

  if (typeof resultImage === 'string') {
    if (/^https?:\/\//i.test(resultImage)) return resultImage;
    if (resultImage.startsWith('/file=')) return `${baseUrl}${resultImage}`;
    if (resultImage.startsWith('file=')) return `${baseUrl}/${resultImage}`;
    return `${baseUrl}/file=${encodeURIComponent(resultImage)}`;
  }

  if (resultImage.url) {
    return String(resultImage.url);
  }

  if (resultImage.path) {
    return `${baseUrl}/file=${encodeURIComponent(resultImage.path)}`;
  }

  throw new Error('Unrecognized Gradio image result format');
}

async function downloadImage(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download generated image (${response.status})`);
  }
  return Buffer.from(await response.arrayBuffer());
}

function normalizeApiName(value) {
  return String(value).trim().replace(/^\/+/, '');
}

function trimTrailingSlash(value) {
  return String(value).trim().replace(/\/+$/, '');
}

function parseBoolean(value, fallback) {
  if (value === undefined || value === null || value === '') return fallback;
  if (typeof value === 'boolean') return value;
  return !['false', '0', 'no', 'off'].includes(String(value).trim().toLowerCase());
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
