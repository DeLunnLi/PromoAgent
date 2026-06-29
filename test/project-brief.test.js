import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { buildAiMessages, formatAiProjectBriefMarkdown } from '../src/ai.js';

const mockResult = {
  target: '.',
  project: {
    name: 'demo',
    description: 'Demo CLI',
    installCommand: 'npx github:DeLunnLi/demo .',
    repositoryUrl: 'https://github.com/acme/demo'
  },
  score: 80,
  grade: 'B',
  evidence: { readmeOpening: 'Hello', readmeFirstScreen: '# Demo' },
  checks: [],
  topFixes: [],
  repository: { stars: 1, topics: ['cli'] }
};

describe('project brief (AI)', () => {
  it('builds brief-mode AI messages', () => {
    const messages = buildAiMessages(mockResult, { brief: true });
    assert.equal(messages.length, 2);
    assert.match(messages[0].content, /读懂仓库并向访客介绍项目/);
    assert.match(messages[1].content, /projectBrief/);
    assert.match(messages[1].content, /heuristicScore 与 checks 仅作辅助/);
  });

  it('formats AI project brief markdown', () => {
    const md = formatAiProjectBriefMarkdown({
      model: 'Qwen/Test',
      content: {
        projectBrief: {
          oneLiner: '一行命令读懂开源仓库',
          overview: 'Source2Launch 用大模型阅读 README 并介绍项目。',
          targetUsers: ['独立开发者'],
          problem: 'README 写不清',
          solution: 'AI 阅读并总结',
          howItWorks: '收集 evidence → 大模型理解 → 输出摘要',
          differentiators: ['LLM 优先'],
          tryItNow: '先跑 read-project',
          starBlockers: [{ priority: 'high', stage: 'first-impression', issue: '首屏不清', fix: '改 one-liner' }],
          promoHooks: [{ platform: 'xhs', angle: '踩坑', hook: 'README 首屏写错了一行' }],
          honestLimits: ['不保证涨 star'],
          confidence: 'high'
        },
        readmeSuggestions: { oneLiner: '更短的一句话' }
      }
    }, mockResult);

    assert.match(md, /# 项目理解（AI）/);
    assert.match(md, /一行命令读懂开源仓库/);
    assert.match(md, /npx github:DeLunnLi\/demo \./);
    assert.match(md, /不保证涨 star/);
    assert.match(md, /更短的一句话/);
  });
});
