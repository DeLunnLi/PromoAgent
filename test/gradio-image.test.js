import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  buildGradioPredictPayload,
  gradioImageConfig,
  resolveGradioDimensions
} from '../src/gradio-image.js';
import { imageGenAvailable, resolveImageProvider } from '../src/modelscope.js';

describe('Gradio image generation', () => {
  it('reads Gradio config from environment variables', () => {
    const config = gradioImageConfig({}, {
      SOURCE2LAUNCH_GRADIO_URL: 'http://127.0.0.1:7860',
      SOURCE2LAUNCH_GRADIO_API: 'generate_image',
      SOURCE2LAUNCH_GRADIO_PROMPT_EXTEND: 'true'
    });

    assert.equal(config.provider, 'gradio');
    assert.equal(config.baseUrl, 'http://127.0.0.1:7860');
    assert.equal(config.apiName, 'generate_image');
    assert.equal(config.promptExtend, true);
  });

  it('builds /generate_image payload in API order', () => {
    const config = gradioImageConfig({}, { SOURCE2LAUNCH_GRADIO_URL: 'http://127.0.0.1:7860' });
    const payload = buildGradioPredictPayload('Hello!!', config, { width: 2688, height: 1536 });

    assert.deepEqual(payload, [
      [],
      'Hello!!',
      true,
      false,
      0,
      true,
      1536,
      2688,
      ' '
    ]);
  });

  it('uses square dimensions for WeChat covers', () => {
    const dims = resolveGradioDimensions('wechat', { SOURCE2LAUNCH_GRADIO_WECHAT_SIZE: '1536' });
    assert.equal(dims.width, 1536);
    assert.equal(dims.height, 1536);
  });

  it('prefers Gradio when SOURCE2LAUNCH_GRADIO_URL is set', () => {
    assert.equal(resolveImageProvider({ SOURCE2LAUNCH_GRADIO_URL: 'http://127.0.0.1:7860' }), 'gradio');
    assert.equal(imageGenAvailable({}, { SOURCE2LAUNCH_GRADIO_URL: 'http://127.0.0.1:7860' }), true);
  });
});
