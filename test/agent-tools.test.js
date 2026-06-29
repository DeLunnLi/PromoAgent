import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { buildAgentToolSystemAddendum, resolveAgentToolsEnabled } from '../src/agent.js';
import { readProjectSummary } from '../src/tools/read-project.js';
import { readRepoEvidence } from '../src/tools/read-evidence.js';
import { AGENT_TOOL_DEFINITIONS, filterToolDefinitions } from '../src/tools/definitions.js';

describe('agent tools', () => {
  it('enables agent tools by default for promo unless disabled', () => {
    assert.equal(resolveAgentToolsEnabled({ promo: true }, {}), true);
    assert.equal(resolveAgentToolsEnabled({ promo: true, noTools: true }, {}), false);
    assert.equal(resolveAgentToolsEnabled({ promo: true }, { SOURCE2LAUNCH_AGENT_TOOLS: 'false' }), false);
  });

  it('includes tool usage guidance in system addendum', () => {
    const addendum = buildAgentToolSystemAddendum();
    assert.match(addendum, /web_search/);
    assert.match(addendum, /generate_promo_image/);
    assert.match(addendum, /read_repo_evidence/);
    assert.match(addendum, /read_project_summary/);
    assert.match(addendum, /read_pdf_document/);
  });

  it('reads selected evidence sections', () => {
    const payload = readRepoEvidence({
      project: { name: 'demo', installCommand: 'npx demo .' },
      score: 80,
      grade: 'B',
      evidence: { launchRisks: ['Missing GIF demo'], readmeOpening: 'Hello world' },
      topFixes: [{ fix: 'Add GIF' }],
      checks: [{ id: 'install-command', label: 'Install', score: 10, max: 12, summary: 'ok' }],
      repository: { stars: 12, topics: ['cli'] }
    }, ['installCommand', 'launchRisks']);

    assert.equal(payload.installCommand, 'npx demo .');
    assert.deepEqual(payload.launchRisks, ['Missing GIF demo']);
    assert.match(payload.evidenceBrief, /npx demo \./);
  });

  it('reads project summary from agent context', async () => {
    const payload = await readProjectSummary({
      result: {
        project: { name: 'demo', description: 'Demo tool', installCommand: 'npx demo .' },
        score: 80,
        grade: 'B',
        evidence: { launchRisks: ['Missing GIF demo'], readmeOpening: 'Hello world' },
        topFixes: [{ fix: 'Add GIF' }],
        checks: [{ id: 'install-command', label: 'Install', score: 10, max: 12, summary: 'ok' }]
      }
    }, { sections: ['overview', 'risks'] });

    assert.equal(payload.ok, true);
    assert.equal(payload.sections.overview.name, 'demo');
    assert.deepEqual(payload.sections.launchRisks, ['Missing GIF demo']);
    assert.match(payload.markdown, /Demo tool/);
  });

  it('filters tool definitions by allowlist', () => {
    const filtered = filterToolDefinitions(['web_search', 'read_repo_evidence']);
    assert.equal(filtered.length, 2);
    assert.equal(filtered[0].function.name, 'web_search');
    assert.equal(AGENT_TOOL_DEFINITIONS.length >= 6, true);
  });
});
