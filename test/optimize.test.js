import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { analyzeTarget } from '../src/index.js';
import { runOptimize } from '../src/optimize.js';
import { parseArgs } from '../src/cli.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtureRoot = path.join(__dirname, 'fixtures');

describe('optimize', () => {
  it('generates local markdown assets without API keys', async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'star-up-opt-'));
    const outputDir = path.join(tempRoot, 'launch-assets');

    try {
      const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
      const manifest = await runOptimize(result, {
        cwd: fixtureRoot,
        env: {},
        outputDir
      });

      assert.ok(manifest.generated.includes('INDEX.md'));
      assert.ok(manifest.generated.includes('project-summary.md'));
      assert.ok(manifest.generated.includes('heuristic-audit.md'));
      assert.ok(manifest.generated.includes('readme-suggestions.md'));
      assert.ok(manifest.generated.includes('promo-xhs.md'));
      assert.ok(manifest.generated.includes('promo-wechat.md'));
      assert.ok(manifest.generated.includes('promo-zhihu.md'));
      assert.ok(manifest.skipped.some((item) => item.includes('推广配图') || item.includes('Gradio')));
      assert.ok(manifest.generated.includes('promo-en.md'));
      assert.ok(manifest.generated.includes('content-review.md'));
      assert.ok(manifest.generated.includes('campaign.json'));
      assert.ok(manifest.generated.includes('platform/xhs.md'));
      assert.ok(manifest.generated.includes('platform/show-hn.md'));
      assert.ok(manifest.generated.includes('platform/producthunt-kit.md'));

      const index = await readFile(path.join(outputDir, 'INDEX.md'), 'utf8');
      assert.match(index, /repo-pulse/);
      assert.match(index, /content-review\.md/);

      const review = await readFile(path.join(outputDir, 'content-review.md'), 'utf8');
      assert.match(review, /内容审核清单/);
      assert.match(review, /不得编造/);
      assert.match(review, /三轴审核/);
      assert.match(review, /Fidelity/);
      assert.match(review, /Engagement/);
      assert.match(review, /Alignment/);

      const campaign = JSON.parse(await readFile(path.join(outputDir, 'campaign.json'), 'utf8'));
      assert.equal(campaign.status, 'needs_model_config');
      assert.equal(campaign.files.platforms.showHn, 'platform/show-hn.md');
      assert.ok(Array.isArray(campaign.reviewGate.qualityRubric.fidelity.checks));
      assert.ok(Array.isArray(campaign.reviewGate.qualityRubric.engagement.checks));
      assert.ok(Array.isArray(campaign.reviewGate.qualityRubric.alignment.checks));
    } finally {
      await rm(tempRoot, { force: true, recursive: true });
    }
  });

  it('skips heuristic bundle when llm-only mode is requested', async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'star-up-opt-llm-'));
    const outputDir = path.join(tempRoot, 'launch-assets');

    try {
      const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
      const manifest = await runOptimize(result, {
        cwd: fixtureRoot,
        env: { SOURCE2LAUNCH_MODELSCOPE_API_KEY: 'test-key' },
        llmOnly: true,
        outputDir
      });

      assert.equal(manifest.mode, 'llm');
      assert.equal(manifest.generated.includes('heuristic-audit.md'), false);
      assert.equal(manifest.generated.includes('project-summary.md'), true);
      assert.ok(manifest.skipped.some((item) => item.includes('本地资料检查包')));
    } finally {
      await rm(tempRoot, { force: true, recursive: true });
    }
  });

  it('parses optimize options', () => {
    const parsed = parseArgs(['.', '--optimize', '--optimize-dir', 'out', '--pdf', 'docs/a.pdf', '--pdf-ocr']);

    assert.equal(parsed.options.optimize, true);
    assert.equal(parsed.options.optimizeDir, 'out');
    assert.deepEqual(parsed.options.pdfPaths, ['docs/a.pdf']);
    assert.equal(parsed.options.pdfOcr, true);
  });

  it('parses read-project options', () => {
    const parsed = parseArgs(['.', '--read-project', '--project-doc', 'notes.md']);
    assert.equal(parsed.options.readProject, true);
    assert.deepEqual(parsed.options.docPaths, ['notes.md']);
  });
});
