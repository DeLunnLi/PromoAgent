import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { buildPromoSystemPrompt, buildPromoUserPrompt, buildEvidenceBrief, PROMO_JSON_SCHEMA } from '../src/promo-prompts.js';

describe('promo prompts', () => {
  it('includes platform-specific writing guides', () => {
    const system = buildPromoSystemPrompt();

    assert.match(system, /小红书/);
    assert.match(system, /Show HN/);
    assert.match(system, /Pipepost/);
    assert.match(system, /禁止编造/);
    assert.match(system, /markdown 字段/);
  });

  it('requests full markdown output in JSON schema', () => {
    assert.match(PROMO_JSON_SCHEMA, /"markdown"/);
    assert.match(PROMO_JSON_SCHEMA, /xiaohongshu/);
    assert.match(PROMO_JSON_SCHEMA, /zhihu/);
    assert.match(PROMO_JSON_SCHEMA, /showHn/);
    assert.match(PROMO_JSON_SCHEMA, /qualityRubric/);
    assert.match(PROMO_JSON_SCHEMA, /fidelity/);
  });

  it('builds evidence brief from repo payload', () => {
    const brief = buildEvidenceBrief({
      project: { name: 'source2launch', installCommand: 'npx source2launch .', repositoryUrl: 'https://github.com/x/y' },
      heuristicScore: { score: 91, grade: 'A' },
      evidence: { launchRisks: ['Missing GIF demo'], readmeOpening: 'AI launch kit generator' },
      topFixes: [{ fix: 'Add terminal GIF' }],
      checks: [{ label: 'Install', score: 12, max: 12, summary: 'Short install command' }]
    });

    assert.match(brief, /npx source2launch \./);
    assert.match(brief, /Missing GIF demo/);
    assert.match(brief, /Add terminal GIF/);
  });

  it('builds user prompt with evidence brief', () => {
    const user = buildPromoUserPrompt({
      project: { name: 'source2launch', installCommand: 'npx source2launch .' },
      evidence: { readmeOpening: 'test' }
    }, { platform: 'xhs' });

    assert.match(user, /source2launch/);
    assert.match(user, /写作时必须引用的真实证据/);
    assert.match(user, /promotionStrategy\.qualityRubric/);
    assert.match(user, /npx source2launch \./);
  });
});
