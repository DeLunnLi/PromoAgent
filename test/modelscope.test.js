import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { analyzeTarget } from '../src/index.js';
import { buildPromoImagePrompt, modelscopeConfig, modelscopeImageRequiresReference, isQwenImageModel, resolveModelscopeImageDimensions, resolveModelscopeImageModel } from '../src/modelscope.js';
import { parseArgs } from '../src/cli.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtureRoot = path.join(__dirname, 'fixtures');

describe('ModelScope image generation', () => {
  it('reads ModelScope config from environment variables', () => {
    const config = modelscopeConfig({}, {
      SOURCE2LAUNCH_MODELSCOPE_API_KEY: 'ms-test-key',
      SOURCE2LAUNCH_MODELSCOPE_BASE_URL: 'https://api-inference.modelscope.cn',
      SOURCE2LAUNCH_IMAGE_MODEL: 'Qwen/Qwen-Image'
    });

    assert.equal(config.apiKey, 'ms-test-key');
    assert.equal(config.baseUrl, 'https://api-inference.modelscope.cn/');
    assert.equal(config.model, 'Qwen/Qwen-Image');
  });

  it('detects edit vs text-to-image models', () => {
    assert.equal(modelscopeImageRequiresReference('FireRedTeam/FireRed-Image-Edit-1.1'), true);
    assert.equal(modelscopeImageRequiresReference('Qwen/Qwen-Image-Edit-2511'), true);
    assert.equal(modelscopeImageRequiresReference('Qwen/Qwen-Image'), false);
    assert.equal(isQwenImageModel('Qwen/Qwen-Image'), true);
  });

  it('resolves platform dimensions for Qwen-Image', () => {
    const xhs = resolveModelscopeImageDimensions('xhs', { SOURCE2LAUNCH_IMAGE_WIDTH: '1104', SOURCE2LAUNCH_IMAGE_HEIGHT: '1472' });
    assert.deepEqual(xhs, { width: 1104, height: 1472 });

    const wechat = resolveModelscopeImageDimensions('wechat', { SOURCE2LAUNCH_IMAGE_WECHAT_SIZE: '1024' });
    assert.deepEqual(wechat, { width: 1024, height: 1024 });

    assert.equal(resolveModelscopeImageModel({}, { SOURCE2LAUNCH_IMAGE_MODEL: 'Qwen/Qwen-Image' }), 'Qwen/Qwen-Image');
  });

  it('builds a Xiaohongshu promo image prompt from repo data', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const prompt = buildPromoImagePrompt(result, { platform: 'xhs' });

    assert.match(prompt, /开源|Theme \(do not render as text\)/i);
    assert.match(prompt, /Square 1:1 premium tech|Vertical 3:4 premium tech/i);
    assert.match(prompt, /NOT smartphone mockup/i);
  });

  it('builds edit prompt when reference image is available', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const prompt = buildPromoImagePrompt(result, {
      platform: 'xhs',
      hasReference: true,
      provider: 'modelscope',
      model: 'FireRedTeam/FireRed-Image-Edit-1.1'
    });

    assert.match(prompt, /Enhance this screenshot/i);
    assert.match(prompt, /Do not add any new text/i);
  });

  it('uses custom image prompt when provided', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const prompt = buildPromoImagePrompt(result, { prompt: 'custom cover art' });

    assert.equal(prompt, 'custom cover art');
  });

  it('parses image generation CLI options', () => {
    const parsed = parseArgs([
      '.',
      '--gen-image',
      '--image-prompt',
      'terminal screenshot style',
      '--image-url',
      'https://example.com/base.png',
      '--image-model',
      'FireRedTeam/FireRed-Image-Edit-1.1',
      '--image-output',
      'cover.jpg'
    ]);

    assert.equal(parsed.options.genImage, true);
    assert.equal(parsed.options.imagePrompt, 'terminal screenshot style');
    assert.equal(parsed.options.imageUrl, 'https://example.com/base.png');
    assert.equal(parsed.options.imageModel, 'FireRedTeam/FireRed-Image-Edit-1.1');
    assert.equal(parsed.options.imageOutput, 'cover.jpg');
  });
});
