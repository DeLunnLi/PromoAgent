import { promises as fs } from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';

import { composeVerticalCoverFromSquare, shouldComposeXhsCover } from './promo-image-compose.js';
import { generateGradioImage, gradioImageConfig } from './gradio-image.js';
import {
  applyPromoTextOverlay,
  buildPromoCoverText,
  shouldApplyPromoTextOverlay
} from './promo-image-overlay.js';
import { resolveEffectiveImageModel } from './promo-sanitize.js';
import {
  buildPromoImageNegativePrompt,
  buildPromoImagePrompt,
  buildPromoImageRequestExtras
} from './promo-image-prompts.js';

export { buildPromoImagePrompt } from './promo-image-prompts.js';
export { buildPromoImageNegativePrompt, resolvePromoImageStyle } from './promo-image-prompts.js';

const DEFAULT_BASE_URL = 'https://api-inference.modelscope.cn/';
const DEFAULT_IMAGE_MODEL = 'Qwen/Qwen-Image';
const DEFAULT_TASK_TYPE = 'image_generation';

export function resolveImageProvider(env = process.env) {
  const explicit = String(env.SOURCE2LAUNCH_IMAGE_PROVIDER ?? env.STAR_UP_IMAGE_PROVIDER ?? '').trim().toLowerCase();
  if (explicit === 'gradio') return 'gradio';
  if (explicit === 'modelscope') return 'modelscope';
  if (env.SOURCE2LAUNCH_GRADIO_URL || env.STAR_UP_GRADIO_URL || env.GRADIO_URL) return 'gradio';
  if (env.SOURCE2LAUNCH_MODELSCOPE_API_KEY || env.STAR_UP_MODELSCOPE_API_KEY || env.MODELSCOPE_API_KEY) return 'modelscope';
  return 'modelscope';
}

export function resolveModelscopeImageModel(options = {}, env = process.env) {
  return options.model || env.SOURCE2LAUNCH_IMAGE_MODEL || env.STAR_UP_IMAGE_MODEL || env.MODELSCOPE_IMAGE_MODEL || DEFAULT_IMAGE_MODEL;
}

export function modelscopeImageRequiresReference(modelId) {
  const model = String(modelId ?? DEFAULT_IMAGE_MODEL).toLowerCase();
  return /(?:^|\/)fire(?:red)?|image-edit|image_edit|-edit-/i.test(model);
}

export function isQwenImageModel(modelId) {
  const model = String(modelId ?? '').toLowerCase();
  return /qwen\/qwen-image/i.test(model) || /^qwen-image$/i.test(model);
}

export function resolveModelscopeImageDimensions(platform, env = process.env) {
  const normalized = normalizeImagePlatform(platform);
  const sizeString = String(env.SOURCE2LAUNCH_IMAGE_SIZE ?? env.STAR_UP_IMAGE_SIZE ?? '').trim();

  if (sizeString && /^\d+x\d+$/i.test(sizeString)) {
    const [width, height] = sizeString.toLowerCase().split('x').map(Number);
    return { width, height };
  }

  if (normalized === 'wechat') {
    const size = Number(env.SOURCE2LAUNCH_IMAGE_WECHAT_SIZE || env.STAR_UP_IMAGE_WECHAT_SIZE || env.SOURCE2LAUNCH_MODELSCOPE_WECHAT_SIZE || env.STAR_UP_MODELSCOPE_WECHAT_SIZE || 1024);
    return { width: size, height: size };
  }

  return {
    width: Number(env.SOURCE2LAUNCH_IMAGE_WIDTH || env.STAR_UP_IMAGE_WIDTH || 1104),
    height: Number(env.SOURCE2LAUNCH_IMAGE_HEIGHT || env.STAR_UP_IMAGE_HEIGHT || 1472)
  };
}

export function imageGenAvailable(options = {}, env = process.env) {
  if (resolveImageProvider(env) === 'gradio') {
    try {
      gradioImageConfig(options, env);
      return true;
    } catch {
      return false;
    }
  }

  try {
    modelscopeConfig(options, env);
    return Boolean(
      options.apiKey
      || env.SOURCE2LAUNCH_MODELSCOPE_API_KEY
      || env.STAR_UP_MODELSCOPE_API_KEY
      || env.MODELSCOPE_API_KEY
    );
  } catch {
    return false;
  }
}

export function modelscopeConfig(options = {}, env = process.env) {
  const apiKey = options.apiKey
    || env.SOURCE2LAUNCH_MODELSCOPE_API_KEY
    || env.STAR_UP_MODELSCOPE_API_KEY
    || env.MODELSCOPE_API_KEY;

  if (!apiKey) {
    throw new Error('Missing ModelScope API key. Set SOURCE2LAUNCH_MODELSCOPE_API_KEY or MODELSCOPE_API_KEY.');
  }

  return {
    provider: 'modelscope',
    apiKey,
    baseUrl: normalizeBaseUrl(options.baseUrl || env.SOURCE2LAUNCH_MODELSCOPE_BASE_URL || env.STAR_UP_MODELSCOPE_BASE_URL || env.MODELSCOPE_BASE_URL || DEFAULT_BASE_URL),
    model: resolveModelscopeImageModel(options, env),
    pollIntervalMs: Number(options.pollIntervalMs || env.SOURCE2LAUNCH_IMAGE_POLL_MS || env.STAR_UP_IMAGE_POLL_MS || 5_000),
    timeoutMs: Number(options.timeoutMs || env.SOURCE2LAUNCH_IMAGE_TIMEOUT_MS || env.STAR_UP_IMAGE_TIMEOUT_MS || 300_000),
    taskType: options.taskType || env.SOURCE2LAUNCH_IMAGE_TASK_TYPE || env.STAR_UP_IMAGE_TASK_TYPE || DEFAULT_TASK_TYPE
  };
}

export async function generateImage(options = {}) {
  const env = options.env || process.env;
  const provider = options.provider || resolveImageProvider(env);

  if (provider === 'gradio') {
    return generateGradioImage({
      ...options,
      env,
      platform: options.platform
    });
  }

  return generateModelscopeImage(options);
}

async function generateModelscopeImage(options = {}) {
  const prompt = String(options.prompt ?? '').trim();
  if (!prompt) {
    throw new Error('Image generation requires a prompt. Use --image-prompt or run without it to auto-build from repo data.');
  }

  const imageUrl = options.imageUrl ? String(options.imageUrl).trim() : '';
  const imageBase64 = options.imageBase64 ? String(options.imageBase64).trim() : '';
  const hasReference = Boolean(imageUrl || imageBase64 || options.imageFile);
  const model = options.model || resolveEffectiveImageModel(options.env, hasReference);
  const config = modelscopeConfig({ ...options, model });
  const requiresReference = modelscopeImageRequiresReference(config.model);

  const payload = {
    model: config.model,
    prompt,
    ...buildPromoImageRequestExtras({ model: config.model }, options.env)
  };

  if (imageUrl) {
    payload.image_url = imageUrl;
  } else if (imageBase64) {
    payload.image = imageBase64;
  } else if (options.imageFile) {
    payload.image = await readImageAsBase64(options.imageFile);
  } else if (requiresReference) {
    throw new Error(
      `Model ${config.model} requires a reference image. Provide --image-url/--image-file, or set SOURCE2LAUNCH_IMAGE_MODEL=Qwen/Qwen-Image for text-to-image.`
    );
  }

  if (!requiresReference || hasReference) {
    const composeXhs = shouldComposeXhsCover(options.platform, options.env);
    const requestPlatform = composeXhs ? 'wechat' : options.platform;
    const dimensions = resolveModelscopeImageDimensions(requestPlatform, options.env);
    payload.width = dimensions.width;
    payload.height = dimensions.height;
  }

  const taskId = await submitImageTask(config, payload);
  const task = await pollImageTask(config, taskId);
  const imageRemoteUrl = task.outputImages[0];
  const buffer = await downloadImage(imageRemoteUrl);
  const ext = detectImageExtension(buffer);
  const composeXhs = shouldComposeXhsCover(options.platform, options.env);
  let finalBuffer = buffer;

  if (composeXhs) {
    const target = resolveModelscopeImageDimensions('xhs', options.env);
    finalBuffer = await composeVerticalCoverFromSquare(buffer, target);
  }

  let textOverlay = null;
  if (options.result && shouldApplyPromoTextOverlay(options.env)) {
    const sizeMeta = await sharp(finalBuffer).metadata();
    textOverlay = buildPromoCoverText(options.result, {
      env: options.env,
      platform: options.platform
    });
    finalBuffer = await applyPromoTextOverlay(finalBuffer, {
      width: sizeMeta.width,
      height: sizeMeta.height,
      platform: options.platform,
      text: textOverlay
    });
  }

  let outputPath = path.resolve(options.outputPath || 'promo-image.jpg');
  if (ext === '.png' && /\.jpe?g$/i.test(outputPath)) {
    outputPath = outputPath.replace(/\.jpe?g$/i, '.png');
  } else if (ext === '.jpg' && /\.png$/i.test(outputPath)) {
    outputPath = outputPath.replace(/\.png$/i, '.jpg');
  }

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, finalBuffer);

  return {
    provider: 'modelscope',
    taskId,
    model: config.model,
    prompt,
    negativePrompt: payload.negative_prompt ?? null,
    remoteUrl: imageRemoteUrl,
    outputPath,
    taskStatus: task.taskStatus,
    composed: composeXhs,
    textOverlay,
    dimensions: composeXhs
      ? resolveModelscopeImageDimensions('xhs', options.env)
      : (payload.width && payload.height
        ? { width: payload.width, height: payload.height }
        : null)
  };
}

async function submitImageTask(config, payload) {
  const response = await fetch(`${config.baseUrl}v1/images/generations`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      'Content-Type': 'application/json',
      'X-ModelScope-Async-Mode': 'true'
    },
    body: JSON.stringify(payload)
  });

  const text = await response.text();
  if (!response.ok) {
    throw new Error(`ModelScope image request failed (${response.status}): ${text.slice(0, 500)}`);
  }

  const data = JSON.parse(text);
  if (!data.task_id) {
    throw new Error('ModelScope did not return task_id');
  }

  return data.task_id;
}

async function pollImageTask(config, taskId) {
  const started = Date.now();

  while (Date.now() - started < config.timeoutMs) {
    const response = await fetch(`${config.baseUrl}v1/tasks/${taskId}`, {
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json',
        'X-ModelScope-Task-Type': config.taskType
      }
    });

    const text = await response.text();
    if (!response.ok) {
      throw new Error(`ModelScope task poll failed (${response.status}): ${text.slice(0, 500)}`);
    }

    const data = JSON.parse(text);
    const status = String(data.task_status ?? '').toUpperCase();

    if (status === 'SUCCEED') {
      const outputImages = data.output_images;
      if (!Array.isArray(outputImages) || outputImages.length === 0) {
        throw new Error('ModelScope task succeeded but returned no output_images');
      }
      return {
        taskStatus: status,
        outputImages
      };
    }

    if (status === 'FAILED') {
      const reason = data.error_message || data.message || 'unknown error';
      throw new Error(`ModelScope image generation failed: ${reason}`);
    }

    await sleep(config.pollIntervalMs);
  }

  throw new Error(`ModelScope image generation timed out after ${config.timeoutMs}ms`);
}

async function downloadImage(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download generated image (${response.status})`);
  }
  return Buffer.from(await response.arrayBuffer());
}

async function readImageAsBase64(filePath) {
  const absolute = path.resolve(filePath);
  const buffer = await fs.readFile(absolute);
  const ext = path.extname(absolute).toLowerCase();
  const mime = ext === '.png' ? 'image/png'
    : ext === '.webp' ? 'image/webp'
      : ext === '.gif' ? 'image/gif'
        : 'image/jpeg';
  return `data:${mime};base64,${buffer.toString('base64')}`;
}

function normalizeBaseUrl(value) {
  const trimmed = String(value).trim();
  return trimmed.endsWith('/') ? trimmed : `${trimmed}/`;
}

function normalizeImagePlatform(platform) {
  const normalized = String(platform ?? 'xhs').trim().toLowerCase();
  if (['wechat', 'weixin', 'wx'].includes(normalized)) return 'wechat';
  return 'xhs';
}

function detectImageExtension(buffer) {
  if (buffer.length >= 8 && buffer[0] === 0x89 && buffer[1] === 0x50) return '.png';
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) return '.jpg';
  if (buffer.length >= 12 && buffer.toString('ascii', 0, 4) === 'RIFF' && buffer.toString('ascii', 8, 12) === 'WEBP') {
    return '.webp';
  }
  return '.jpg';
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
