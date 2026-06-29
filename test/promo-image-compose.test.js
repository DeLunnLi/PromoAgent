import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import sharp from 'sharp';

import { composeVerticalCoverFromSquare, shouldComposeXhsCover } from '../src/promo-image-compose.js';

describe('promo image compose', () => {
  it('enables xhs compose by default', () => {
    assert.equal(shouldComposeXhsCover('xhs', {}), true);
    assert.equal(shouldComposeXhsCover('xhs', { SOURCE2LAUNCH_IMAGE_XHS_COMPOSE: 'false' }), false);
    assert.equal(shouldComposeXhsCover('wechat', {}), false);
  });

  it('extends a square image into a vertical cover', async () => {
    const square = await sharp({
      create: {
        width: 64,
        height: 64,
        channels: 3,
        background: { r: 120, g: 180, b: 240 }
      }
    })
      .png()
      .toBuffer();

    const composed = await composeVerticalCoverFromSquare(square, { width: 64, height: 96 });
    const meta = await sharp(composed).metadata();

    assert.equal(meta.width, 64);
    assert.equal(meta.height, 96);
  });
});
