import path from 'node:path';

import { buildPromoImagePrompt, generateImage, imageGenAvailable } from '../modelscope.js';
import { readProjectSummary, readPdfDocument } from './read-project.js';
import { readRepoEvidence } from './read-evidence.js';
import { fetchPageText, webSearch } from './web-search.js';

export async function executeAgentTool(name, args, context = {}) {
  switch (name) {
    case 'web_search':
      return webSearch(args.query, { maxResults: args.max_results });
    case 'fetch_page_text':
      return fetchPageText(args.url, { maxChars: args.max_chars });
    case 'read_project_summary':
      return readProjectSummary(context, args);
    case 'read_pdf_document':
      return readPdfDocument(context, args);
    case 'read_repo_evidence':
      return readRepoEvidence(context.result, args.sections);
    case 'generate_promo_image':
      return executeGeneratePromoImage(args, context);
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

async function executeGeneratePromoImage(args, context) {
  const env = context.env ?? process.env;
  if (!imageGenAvailable(context.imageOptions ?? {}, env)) {
    return {
      ok: false,
      error: 'Image generation unavailable. Set SOURCE2LAUNCH_GRADIO_URL or SOURCE2LAUNCH_MODELSCOPE_API_KEY with SOURCE2LAUNCH_IMAGE_MODEL=Qwen/Qwen-Image.'
    };
  }

  const platform = normalizePlatform(args.platform);
  const imagesDir = context.imagesDir || context.outputDir;
  if (!imagesDir) {
    return { ok: false, error: 'No output directory configured for image generation.' };
  }

  const filename = sanitizeFilename(args.filename || defaultImageName(platform));
  const outputPath = path.join(imagesDir, filename);
  const imageContext = context.imageContext ?? {};

  try {
    const result = await generateImage({
      env,
      platform,
      prompt: args.prompt || buildPromoImagePrompt(context.result, {
        platform,
        hasReference: Boolean(imageContext.imageUrl || imageContext.imageFile),
        provider: undefined,
        env
      }),
      outputPath,
      imageFile: imageContext.imageFile,
      imageUrl: imageContext.imageUrl,
      apiKey: context.modelscopeApiKey,
      result: context.result
    });

    const relative = context.outputDir
      ? path.relative(context.outputDir, result.outputPath)
      : result.outputPath;

    if (context.generatedImages) {
      context.generatedImages[platform === 'wechat' ? 'wechat' : 'xhs'] = relative;
    }

    return {
      ok: true,
      platform,
      provider: result.provider,
      outputPath: result.outputPath,
      relativePath: relative,
      prompt: result.prompt
    };
  } catch (error) {
    return {
      ok: false,
      error: error.message
    };
  }
}

function normalizePlatform(platform) {
  const value = String(platform ?? 'xhs').trim().toLowerCase();
  return value === 'wechat' ? 'wechat' : 'xhs';
}

function defaultImageName(platform) {
  return platform === 'wechat' ? 'wechat-cover.png' : 'xhs-cover.png';
}

function sanitizeFilename(value) {
  const name = path.basename(String(value ?? '').trim());
  if (!name || name.includes('..')) {
    throw new Error('Invalid image filename.');
  }
  return name.replace(/[^\w.-]+/g, '-');
}
