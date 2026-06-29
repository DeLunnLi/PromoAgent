import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { analyzeTarget } from '../src/index.js';
import {
  buildPromoImageNegativePrompt,
  buildPromoImagePrompt,
  buildPromoImageRequestExtras,
  resolvePromoImageStyle
} from '../src/promo-image-prompts.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtureRoot = path.join(__dirname, 'fixtures');

describe('promo image prompts', () => {
  it('uses square compose prompt for xhs poster by default', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const prompt = buildPromoImagePrompt(result, { platform: 'xhs' });

    assert.match(prompt, /Square 1:1 premium tech/i);
    assert.match(prompt, /typography overlay/i);
    assert.match(prompt, /NOT smartphone mockup/i);
  });

  it('supports terminal style preset', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const prompt = buildPromoImagePrompt(result, {
      platform: 'xhs',
      env: { SOURCE2LAUNCH_IMAGE_STYLE: 'terminal' }
    });

    assert.equal(resolvePromoImageStyle({ SOURCE2LAUNCH_IMAGE_STYLE: 'terminal' }), 'terminal');
    assert.match(prompt, /终端窗口/);
  });

  it('builds optional qwen extras when enabled', () => {
    const negative = buildPromoImageNegativePrompt();
    assert.match(negative, /watermark/);

    assert.deepEqual(
      buildPromoImageRequestExtras({ model: 'Qwen/Qwen-Image' }, {}),
      {}
    );
    assert.equal(
      buildPromoImageRequestExtras({ model: 'Qwen/Qwen-Image' }, { SOURCE2LAUNCH_IMAGE_PROMPT_EXTEND: 'true' }).prompt_extend,
      true
    );
  });

  it('builds edit enhance prompt when reference model is used', async () => {
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
});
