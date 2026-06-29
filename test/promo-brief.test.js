import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import { buildPromoBriefSection, resolvePromoBrief } from '../src/promo-brief.js';
import { buildPromoUserPrompt } from '../src/promo-prompts.js';

describe('promo brief', () => {
  it('merges inline text and file content', () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'star-up-brief-'));
    const filePath = path.join(dir, 'brief.md');
    writeFileSync(filePath, '知乎偏方法论，少提产品名');

    const brief = resolvePromoBrief(
      { promoBrief: '小红书像踩坑日记', promoBriefFile: filePath },
      {},
      dir
    );

    assert.match(brief, /踩坑日记/);
    assert.match(brief, /知乎偏方法论/);
  });

  it('injects brief section into promo user prompt', () => {
    const user = buildPromoUserPrompt({
      project: { name: 'demo', installCommand: 'npx demo .' },
      evidence: {}
    }, {
      platform: 'all',
      briefSection: buildPromoBriefSection('语气偏口语，不要营销腔')
    });

    assert.match(user, /用户创作引导/);
    assert.match(user, /语气偏口语/);
    assert.match(user, /不可违背/);
  });
});
