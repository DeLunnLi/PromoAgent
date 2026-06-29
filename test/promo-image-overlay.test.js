import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import sharp from 'sharp';

import {
  applyPromoTextOverlay,
  buildPromoCoverText,
  shouldApplyPromoTextOverlay
} from '../src/promo-image-overlay.js';

describe('promo image overlay', () => {
  it('builds default cover text from repo metadata', () => {
    const text = buildPromoCoverText({
      project: {
        name: 'source2launch',
        topics: ['ai', 'cli', 'github'],
        description: 'AI reads repos'
      }
    }, { platform: 'xhs' });

    assert.equal(text.title, 'source2launch');
    assert.match(text.subtitle, /AI|读懂/);
    assert.ok(text.badges.length >= 2);
  });

  it('respects overlay env toggle', () => {
    assert.equal(shouldApplyPromoTextOverlay({}), true);
    assert.equal(shouldApplyPromoTextOverlay({ SOURCE2LAUNCH_IMAGE_TEXT_OVERLAY: 'false' }), false);
  });

  it('composites readable overlay onto an image buffer', async () => {
    const base = await sharp({
      create: {
        width: 320,
        height: 420,
        channels: 3,
        background: { r: 180, g: 210, b: 245 }
      }
    })
      .png()
      .toBuffer();

    const overlaid = await applyPromoTextOverlay(base, {
      width: 320,
      height: 420,
      platform: 'xhs',
      text: {
        title: 'source2launch',
        subtitle: 'README 没人看？先让 AI 读懂你的项目',
        badges: ['AI 项目理解', '多平台文案']
      }
    });

    const meta = await sharp(overlaid).metadata();
    assert.equal(meta.width, 320);
    assert.equal(meta.height, 420);
    assert.ok(overlaid.length > base.length);
  });
});
