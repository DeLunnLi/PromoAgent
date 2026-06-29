import { promises as fs } from 'node:fs';
import path from 'node:path';

import { parsePdfDocument } from './pdf.js';
import { buildEvidenceBrief } from './promo-prompts.js';

const TEXT_EXTENSIONS = new Set(['.md', '.markdown', '.txt', '.rst']);

export async function buildProjectIntake(result, options = {}) {
  const cwd = options.cwd ?? process.cwd();
  const pdfPaths = normalizePaths(options.pdfPaths ?? options.pdfs ?? [], cwd);
  const docPaths = normalizePaths(options.docPaths ?? options.projectDocs ?? [], cwd);
  const allPaths = [...pdfPaths, ...docPaths];

  const documents = [];
  const errors = [];

  for (const filePath of allPaths) {
    try {
      if (filePath.toLowerCase().endsWith('.pdf')) {
        documents.push(await parsePdfDocument(filePath, {
          cwd,
          ocr: options.pdfOcr,
          env: options.env,
          maxChars: options.maxChars
        }));
      } else {
        documents.push(await readTextDocument(filePath, options));
      }
    } catch (error) {
      errors.push({ path: filePath, error: error.message });
    }
  }

  const summary = buildProjectSummary(result, documents);
  return {
    summary,
    summaryMarkdown: formatProjectSummaryMarkdown(summary, documents),
    documents,
    errors,
    capabilities: summary.capabilities
  };
}

export function buildProjectSummary(result, documents = []) {
  const project = result?.project ?? {};
  return {
    project: {
      name: project.name,
      description: project.description,
      installCommand: project.installCommand,
      repositoryUrl: project.repositoryUrl,
      score: result?.score,
      grade: result?.grade
    },
    readme: {
      opening: result?.evidence?.readmeOpening ?? '',
      firstScreen: result?.evidence?.readmeFirstScreen ?? '',
      headings: (result?.evidence?.headings ?? []).slice(0, 8)
    },
    launchRisks: result?.evidence?.launchRisks ?? [],
    topFixes: (result?.topFixes ?? []).slice(0, 5),
    evidenceBrief: buildEvidenceBrief({
      project,
      heuristicScore: { score: result?.score, grade: result?.grade },
      evidence: result?.evidence,
      topFixes: result?.topFixes,
      checks: result?.checks
    }),
    documents: documents.map((doc) => ({
      fileName: doc.fileName ?? path.basename(doc.path ?? ''),
      method: doc.method ?? 'text',
      pageCount: doc.pageCount ?? null,
      sectionCount: doc.sections?.length ?? 0,
      excerpt: doc.excerpt ?? doc.text?.slice(0, 600) ?? ''
    })),
    synthesisHints: buildSynthesisHints(result, documents)
  };
}

export function formatProjectSummaryMarkdown(summary, documents = []) {
  const lines = [];
  lines.push('# 项目阅读摘要');
  lines.push('');
  lines.push(`> 项目：${summary.project.name ?? 'unknown'} · 本地证据摘要`);
  lines.push('');
  lines.push('## 一句话');
  lines.push(summary.project.description || '（无描述）');
  lines.push('');
  if (summary.project.installCommand) {
    lines.push('## 安装命令');
    lines.push('```sh');
    lines.push(summary.project.installCommand);
    lines.push('```');
    lines.push('');
  }
  lines.push('## README 首屏片段');
  lines.push(summary.readme.opening || '（无）');
  lines.push('');
  if (summary.launchRisks.length > 0) {
    lines.push('## 发布风险');
    for (const risk of summary.launchRisks.slice(0, 4)) {
      lines.push(`- ${risk.message ?? risk}`);
    }
    lines.push('');
  }
  if (summary.topFixes.length > 0) {
    lines.push('## 优先改进');
    for (const fix of summary.topFixes) {
      lines.push(`- ${fix.fix ?? fix.message ?? fix}`);
    }
    lines.push('');
  }
  if (documents.length > 0) {
    lines.push('## 附加文档');
    for (const doc of documents) {
      lines.push(`### ${doc.fileName ?? path.basename(doc.path ?? 'document')}`);
      lines.push(`- 解析方式：${doc.method ?? 'text'}${doc.pageCount ? ` · ${doc.pageCount} 页` : ''}`);
      if (doc.excerpt) {
        lines.push('');
        lines.push(doc.excerpt);
      }
      lines.push('');
    }
  }
  if (summary.synthesisHints.length > 0) {
    lines.push('## 写作提示');
    for (const hint of summary.synthesisHints) lines.push(`- ${hint}`);
    lines.push('');
  }
  return lines.join('\n').trim();
}

function buildSynthesisHints(result, documents) {
  const hints = [];
  if (result?.project?.installCommand) {
    hints.push(`推广文案必须原样使用安装命令：${result.project.installCommand}`);
  }
  if ((result?.evidence?.launchRisks ?? []).length > 0) {
    hints.push('附加文档与 README 冲突时，以仓库扫描 evidence 为准');
  }
  for (const doc of documents) {
    if (doc.method === 'ocr') hints.push(`${doc.fileName} 来自 OCR，引用时需标注可能有个别错字`);
    if ((doc.sections?.length ?? 0) > 0) {
      hints.push(`可将 ${doc.fileName} 的章节结构借鉴到知乎/长文，但不要照搬未核实数据`);
    }
  }
  return hints;
}

async function readTextDocument(filePath, options = {}) {
  const maxChars = Number(options.maxChars ?? 24_000);
  const ext = path.extname(filePath).toLowerCase();
  if (!TEXT_EXTENSIONS.has(ext)) {
    throw new Error(`Unsupported document type: ${ext || '(none)'}`);
  }
  const text = (await fs.readFile(filePath, 'utf8')).slice(0, maxChars);
  const structured = structurePlainText(text);
  return {
    ok: true,
    path: filePath,
    fileName: path.basename(filePath),
    method: 'text',
    pageCount: null,
    charCount: text.length,
    truncated: false,
    sections: structured.sections,
    markdown: structured.markdown,
    excerpt: structured.excerpt,
    text
  };
}

function structurePlainText(text) {
  const lines = String(text).split('\n');
  const sections = [];
  let current = { heading: '正文', lines: [] };

  for (const line of lines) {
    const trimmed = line.trim();
    const headingMatch = trimmed.match(/^#{1,4}\s+(.+)/);
    if (headingMatch) {
      if (current.lines.length > 0) sections.push(current);
      current = { heading: headingMatch[1].trim(), lines: [] };
      continue;
    }
    current.lines.push(line);
  }
  if (current.lines.length > 0) sections.push(current);

  const normalized = sections.map((section) => ({
    heading: section.heading,
    content: section.lines.join('\n').trim()
  }));

  return {
    sections: normalized,
    markdown: normalized.map((section) => `## ${section.heading}\n\n${section.content}`).join('\n\n'),
    excerpt: normalized.map((section) => section.content).join('\n\n').slice(0, 1_200)
  };
}

function normalizePaths(values, cwd) {
  const list = Array.isArray(values) ? values : [values];
  return list
    .map((value) => String(value ?? '').trim())
    .filter(Boolean)
    .map((value) => path.resolve(cwd, value));
}
