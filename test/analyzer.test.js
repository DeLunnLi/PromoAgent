import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';

import { aiConfig, buildAiMessages, buildUserMessageContent, parseJsonContent, resolveAiScore } from '../src/ai.js';
import { analyzeTarget } from '../src/index.js';
import { normalizePrimaryInput, parseArgs } from '../src/cli.js';
import { generateLaunchPack } from '../src/launch.js';
import { generateReadmeSuggestions } from '../src/readme.js';
import { renderTemplate } from '../src/template.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtureRoot = path.join(__dirname, 'fixtures');

describe('analyzeTarget', () => {
  it('scores a weak repo low and returns launch fixes', async () => {
    const result = await analyzeTarget('weak-repo', { cwd: fixtureRoot });

    assert.equal(result.source, 'local');
    assert.ok(result.score < 45, `expected weak score, got ${result.score}`);
    assert.ok(result.topFixes.length > 0);
    assert.ok(result.topFixes.some((fix) => /install|usage|visual|topic|package/i.test(fix.message)));
  });

  it('scores a launch-ready repo high', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });

    assert.ok(result.score >= 80, `expected strong score, got ${result.score}`);
    assert.equal(result.repository.manifest, 'package.json');
    assert.equal(result.project.name, 'repo-pulse');
    assert.ok(result.project.installCommand.includes('npx repo-pulse'));
    assert.ok(result.evidence.readmeOpening.includes('Repo Pulse'));
    assert.ok(result.evidence.installCommands.includes('npx repo-pulse .'));
    assert.ok(result.evidence.headings.some((heading) => heading.text === 'Quickstart'));
    assert.ok(Array.isArray(result.evidence.launchRisks));
    assert.ok(result.checks.every((check) => check.score >= 0 && check.score <= check.max));
  });

  it('generates share-ready promotion copy via AI prompt mode', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const messages = buildAiMessages(result, { promo: true, platform: 'all' });

    assert.equal(messages.length, 2);
    assert.match(messages[0].content, /小红书/);
    assert.match(messages[0].content, /Show HN/);
    assert.match(messages[0].content, /反 AI 味/);
    assert.match(messages[1].content, /"markdown"/);
    assert.match(messages[1].content, /repo-pulse/);
  });

  it('injects planning prompt presets and custom notes into promo prompts', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const messages = buildAiMessages(result, {
      promo: true,
      platform: 'zhihu',
      promptPresets: ['paper'],
      promptNotes: ['用研究者读论文的口吻'],
      audience: 'researchers',
      tone: 'credible reading note',
      appliedSkills: [{ name: 'paper', label: 'Paper promotion', description: 'Paper-first promotion.' }],
      reviewFocus: ['Paper claim fidelity']
    });

    assert.match(messages[0].content, /Source2Launch 任务控制层/);
    assert.match(messages[0].content, /Academic promotion planning/);
    assert.match(messages[0].content, /用研究者读论文的口吻/);
    assert.match(messages[0].content, /Paper claim fidelity/);
    assert.match(messages[1].content, /promotionStrategy/);
  });

  it('renders templates with repository data', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const rendered = await renderTemplate(result, 'xhs');

    assert.match(rendered, /repo-pulse/);
    assert.doesNotMatch(rendered, /{{project_name}}/);
    assert.match(rendered, /npx repo-pulse/);
  });

  it('reads ModelScope chat config from shared token', () => {
    const config = aiConfig({}, {
      SOURCE2LAUNCH_MODELSCOPE_API_KEY: 'ms-test-key',
      SOURCE2LAUNCH_BASE_URL: 'https://api-inference.modelscope.cn/v1',
      SOURCE2LAUNCH_MODEL: 'Qwen/Qwen3.5-397B-A17B'
    });

    assert.equal(config.apiKey, 'ms-test-key');
    assert.equal(config.provider, 'modelscope');
    assert.equal(config.model, 'Qwen/Qwen3.5-397B-A17B');
    assert.equal(config.vision, true);
  });

  it('builds multimodal audit messages when README has remote images', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    result.evidence.visualUrls = ['https://example.com/demo.png'];
    const messages = buildAiMessages(result, { audit: true, vision: true });

    assert.equal(messages.length, 2);
    assert.ok(Array.isArray(messages[1].content));
    assert.equal(messages[1].content[0].type, 'text');
    assert.equal(messages[1].content[1].type, 'image_url');
    assert.equal(messages[1].content[1].image_url.url, 'https://example.com/demo.png');
  });

  it('builds AI audit prompts that prioritize README evidence without score display', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const messages = buildAiMessages(result, { audit: true });

    assert.equal(messages.length, 2);
    assert.match(messages[0].content, /不要展示分数或等级/);
    assert.match(messages[1].content, /"audit"/);
    assert.match(messages[1].content, /readmeFirstScreen/);
    assert.match(messages[1].content, /heuristicScore/);
  });

  it('prefers AI audit score when resolving fail-under thresholds', () => {
    const resolved = resolveAiScore({
      content: {
        audit: {
          score: 92,
          grade: 'A'
        }
      }
    }, { score: 55, grade: 'C' });

    assert.equal(resolved.score, 92);
    assert.equal(resolved.source, 'ai');
  });

  it('builds AI prompts from repository data without calling the network', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const messages = buildAiMessages(result, { platform: 'xhs' });

    assert.equal(messages.length, 2);
    assert.match(messages[1].content, /repo-pulse/);
    assert.match(messages[1].content, /readmeRewrite/);
    assert.match(messages[1].content, /readmeFirstScreen/);
    assert.match(messages[1].content, /xiaohongshu|xhs/i);
  });

  it('generates README first-screen suggestions', async () => {
    const result = await analyzeTarget('weak-repo', { cwd: fixtureRoot });
    const suggestions = generateReadmeSuggestions(result);

    assert.match(suggestions.suggestedFirstScreen, /^# thing/m);
    assert.match(suggestions.suggestedFirstScreen, /Quickstart/);
    assert.ok(suggestions.priorityFixes.length > 0);
  });

  it('generates a multi-channel launch pack', async () => {
    const result = await analyzeTarget('healthy-repo', { cwd: fixtureRoot });
    const launchPack = generateLaunchPack(result);

    assert.match(launchPack.showHn.title, /Show HN/);
    assert.match(launchPack.redditV2ex.body, /仓库/);
    assert.ok(launchPack.xThread.posts.length >= 3);
    assert.ok(launchPack.checklist.length >= 5);
  });
});

describe('parseArgs', () => {
  it('parses json and fail-under options', () => {
    const parsed = parseArgs(['.', '--json', '--fail-under', '70']);

    assert.equal(parsed.target, '.');
    assert.equal(parsed.options.json, true);
    assert.equal(parsed.options.failUnder, 70);
  });

  it('parses promotion options', () => {
    const parsed = parseArgs(['.', '--promo', 'wechat', '--promo-only']);

    assert.equal(parsed.target, '.');
    assert.equal(parsed.options.promo, 'wechat');
    assert.equal(parsed.options.promoOnly, true);
  });

  it('parses promote subcommand for platform-specific copy', () => {
    const parsed = parseArgs(['promote', '.', '--platform', 'xhs']);

    assert.equal(parsed.target, '.');
    assert.equal(parsed.options.mode, 'promote');
    assert.equal(parsed.options.ai, true);
    assert.equal(parsed.options.promoOnly, true);
    assert.equal(parsed.options.promo, 'xhs');
  });

  it('parses promote subcommand for paper inputs', () => {
    const parsed = parseArgs(['promote', 'paper.pdf', '--platform', 'zhihu']);

    assert.equal(parsed.target, 'paper.pdf');
    assert.equal(parsed.options.mode, 'promote');
    assert.equal(parsed.options.promo, 'zhihu');
  });

  it('parses optimize subcommand with output directory alias', () => {
    const parsed = parseArgs(['optimize', '.', '--output', 'launch-assets/']);

    assert.equal(parsed.target, '.');
    assert.equal(parsed.options.mode, 'optimize');
    assert.equal(parsed.options.optimize, true);
    assert.equal(parsed.options.optimizeDir, 'launch-assets/');
    assert.equal(parsed.options.output, null);
  });

  it('parses task skills and prompt controls', () => {
    const parsed = parseArgs([
      'promote',
      'paper.pdf',
      '--skill',
      'paper',
      '--prompt-preset',
      'visual,zhihu',
      '--prompt-note',
      '用研究者读论文的口吻',
      '--audience',
      'researchers',
      '--tone',
      'credible reading note'
    ]);

    assert.equal(parsed.target, 'paper.pdf');
    assert.deepEqual(parsed.options.skills, ['paper']);
    assert.deepEqual(parsed.options.promptPresets, ['visual,zhihu']);
    assert.deepEqual(parsed.options.promptNotes, ['用研究者读论文的口吻']);
    assert.equal(parsed.options.audience, 'researchers');
    assert.equal(parsed.options.tone, 'credible reading note');
  });

  it('parses markdown subcommand', () => {
    const parsed = parseArgs(['markdown', '.', '--markdown-type', 'launch', '--output', 'LAUNCH.md']);

    assert.equal(parsed.target, '.');
    assert.equal(parsed.options.mode, 'markdown');
    assert.equal(parsed.options.markdown, true);
    assert.equal(parsed.options.markdownType, 'launch');
    assert.equal(parsed.options.output, 'LAUNCH.md');
  });

  it('parses publish subcommand with raw platform names', () => {
    const parsed = parseArgs(['publish', 'promotion.json', '--platform', 'producthunt', '--publish-mode', 'review', '--media', 'cover.png', '--yes']);

    assert.equal(parsed.target, 'promotion.json');
    assert.equal(parsed.options.mode, 'publish');
    assert.equal(parsed.options.publish, true);
    assert.equal(parsed.options.promo, 'producthunt');
    assert.equal(parsed.options.publishMode, 'review');
    assert.deepEqual(parsed.options.media, ['cover.png']);
    assert.equal(parsed.options.yes, true);
  });

  it('parses template and output options', () => {
    const parsed = parseArgs(['.', '--template', 'report', '--output', 'report.md']);

    assert.equal(parsed.target, '.');
    assert.equal(parsed.options.template, 'report');
    assert.equal(parsed.options.output, 'report.md');
  });

  it('parses AI options', () => {
    const parsed = parseArgs(['.', '--ai-only', '--promo', 'xhs', '--model', 'test-model', '--base-url', 'https://example.com/v1', '--max-tokens', '2048']);

    assert.equal(parsed.options.ai, true);
    assert.equal(parsed.options.aiOnly, true);
    assert.equal(parsed.options.promo, 'xhs');
    assert.equal(parsed.options.model, 'test-model');
    assert.equal(parsed.options.baseUrl, 'https://example.com/v1');
    assert.equal(parsed.options.maxTokens, 2048);
  });

  it('parses README suggestion option', () => {
    const parsed = parseArgs(['.', '--readme-suggestions']);

    assert.equal(parsed.options.readmeSuggestions, true);
  });

  it('parses launch pack option', () => {
    const parsed = parseArgs(['.', '--launch-pack']);

    assert.equal(parsed.options.launchPack, true);
  });
});

describe('normalizePrimaryInput', () => {
  it('treats a PDF target as source evidence for promote', async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'source2launch-pdf-target-'));
    try {
      await writeFile(path.join(tempRoot, 'paper.pdf'), '%PDF-1.4\n', 'utf8');
      const parsed = parseArgs(['promote', 'paper.pdf', '--platform', 'zhihu']);
      const normalized = await normalizePrimaryInput(parsed.target, parsed.options, tempRoot);

      assert.equal(normalized.target, tempRoot);
      assert.deepEqual(normalized.options.pdfPaths, ['paper.pdf']);
      assert.equal(normalized.options.mode, 'promote');
      assert.equal(normalized.options.promo, 'zhihu');
    } finally {
      await rm(tempRoot, { force: true, recursive: true });
    }
  });

  it('treats a Markdown target as project document evidence', async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'source2launch-md-target-'));
    try {
      await writeFile(path.join(tempRoot, 'notes.md'), '# Notes\n', 'utf8');
      const parsed = parseArgs(['optimize', 'notes.md', '--output', 'launch-assets/']);
      const normalized = await normalizePrimaryInput(parsed.target, parsed.options, tempRoot);

      assert.equal(normalized.target, tempRoot);
      assert.deepEqual(normalized.options.docPaths, ['notes.md']);
      assert.equal(normalized.options.optimizeDir, 'launch-assets/');
    } finally {
      await rm(tempRoot, { force: true, recursive: true });
    }
  });
});

describe('AI helpers', () => {
  it('parses fenced JSON model output', () => {
    const parsed = parseJsonContent('```json\n{"ok":true}\n```');

    assert.equal(parsed.ok, true);
  });

  it('builds multimodal user content arrays', () => {
    const content = buildUserMessageContent('describe this repo', {
      vision: true,
      imageUrls: ['https://example.com/readme.png']
    });

    assert.ok(Array.isArray(content));
    assert.equal(content.length, 2);
    assert.equal(content[1].image_url.url, 'https://example.com/readme.png');
  });

  it('reads API config from explicit env', () => {
    const config = aiConfig({}, {
      SOURCE2LAUNCH_API_KEY: 'test-key',
      SOURCE2LAUNCH_BASE_URL: 'https://example.com/v1/',
      SOURCE2LAUNCH_MODEL: 'test-model'
    });

    assert.equal(config.apiKey, 'test-key');
    assert.equal(config.baseUrl, 'https://example.com/v1');
    assert.equal(config.model, 'test-model');
  });
});
