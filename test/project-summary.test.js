import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import {
  buildProjectIntake,
  buildProjectSummary,
  formatProjectSummaryMarkdown
} from '../src/project-summary.js';

const mockResult = {
  project: {
    name: 'demo-cli',
    description: 'A tiny CLI for testing',
    installCommand: 'npx demo-cli .',
    repositoryUrl: 'https://github.com/acme/demo-cli'
  },
  score: 72,
  grade: 'C',
  evidence: {
    readmeOpening: 'Demo CLI helps you audit repos quickly.',
    readmeFirstScreen: '# Demo CLI\n\nAudit in one command.',
    launchRisks: [{ message: 'Missing GIF demo' }],
    headings: ['Install', 'Usage']
  },
  topFixes: [{ fix: 'Add a GIF to README' }],
  checks: [{ id: 'install-command', label: 'Install', score: 10, max: 12, summary: 'ok' }]
};

describe('project summary', () => {
  it('builds a structured summary from audit result', () => {
    const summary = buildProjectSummary(mockResult);
    assert.equal(summary.project.name, 'demo-cli');
    assert.match(summary.evidenceBrief, /npx demo-cli \./);
    assert.equal(summary.synthesisHints.length > 0, true);
  });

  it('formats markdown with documents and hints', () => {
    const markdown = formatProjectSummaryMarkdown(buildProjectSummary(mockResult), [{
      fileName: 'notes.md',
      method: 'text',
      excerpt: 'Extra positioning notes from a PDF export.'
    }]);

    assert.match(markdown, /# 项目阅读摘要/);
    assert.match(markdown, /npx demo-cli \./);
    assert.match(markdown, /notes\.md/);
    assert.match(markdown, /Extra positioning notes/);
  });

  it('merges text documents in project intake', async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'star-up-intake-'));
    const docPath = path.join(tempRoot, 'brief.md');

    try {
      await writeFile(docPath, '# Brief\n\nThis tool focuses on launch readiness.');
      const intake = await buildProjectIntake(mockResult, {
        cwd: tempRoot,
        docPaths: [docPath]
      });

      assert.equal(intake.documents.length, 1);
      assert.match(intake.summaryMarkdown, /launch readiness/);
      assert.equal(intake.summary.documents[0].fileName, 'brief.md');
    } finally {
      await rm(tempRoot, { force: true, recursive: true });
    }
  });
});
