import { execFile as execFileCallback } from 'node:child_process';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';

const execFile = promisify(execFileCallback);

const DEFAULT_MAX_CHARS = 24_000;
const DEFAULT_MAX_PAGES_OCR = 12;

export async function parsePdfDocument(inputPath, options = {}) {
  const filePath = path.resolve(options.cwd ?? process.cwd(), String(inputPath).trim());
  const stat = await fs.stat(filePath).catch(() => null);
  if (!stat?.isFile()) {
    throw new Error(`PDF not found: ${inputPath}`);
  }
  if (!filePath.toLowerCase().endsWith('.pdf')) {
    throw new Error(`Not a PDF file: ${inputPath}`);
  }

  const maxChars = Number(options.maxChars ?? DEFAULT_MAX_CHARS);
  const preferOcr = Boolean(options.ocr ?? (options.env?.SOURCE2LAUNCH_PDF_OCR ?? options.env?.STAR_UP_PDF_OCR) === 'true');
  const buffer = await fs.readFile(filePath);
  const errors = [];

  if (!preferOcr) {
    const pdftotext = await tryPdftotext(filePath, maxChars).catch((error) => {
      errors.push(`pdftotext: ${error.message}`);
      return null;
    });
    if (pdftotext?.text?.trim()) {
      return finalizePdfResult(filePath, pdftotext.text, {
        method: 'pdftotext',
        pageCount: pdftotext.pageCount,
        maxChars
      });
    }

    const streamText = extractPdfTextFromStreams(buffer);
    if (streamText.trim()) {
      return finalizePdfResult(filePath, streamText, {
        method: 'stream-parse',
        pageCount: estimatePageCount(buffer),
        maxChars
      });
    }
    errors.push('stream-parse: no extractable text');
  }

  const ocr = await tryOcrPdf(filePath, {
    maxChars,
    maxPages: Number(options.maxPages ?? options.env?.SOURCE2LAUNCH_PDF_OCR_MAX_PAGES ?? options.env?.STAR_UP_PDF_OCR_MAX_PAGES ?? DEFAULT_MAX_PAGES_OCR),
    lang: options.ocrLang ?? options.env?.SOURCE2LAUNCH_PDF_OCR_LANG ?? options.env?.STAR_UP_PDF_OCR_LANG ?? 'chi_sim+eng'
  }).catch((error) => {
    errors.push(`ocr: ${error.message}`);
    return null;
  });

  if (ocr?.text?.trim()) {
    return finalizePdfResult(filePath, ocr.text, {
      method: 'ocr',
      pageCount: ocr.pageCount,
      maxChars,
      ocrLang: ocr.lang
    });
  }

  throw new Error(
    `Failed to extract PDF text from ${path.basename(filePath)}. ${errors.join(' | ')}. `
    + 'Install poppler (`pdftotext`) or enable OCR with --pdf-ocr / SOURCE2LAUNCH_PDF_OCR=true (requires pdftoppm + tesseract).'
  );
}

export function structurePdfText(rawText, options = {}) {
  const maxSectionChars = Number(options.maxSectionChars ?? 2_000);
  const lines = String(rawText ?? '')
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line.trimEnd());

  const sections = [];
  let current = { heading: '正文', lines: [] };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (current.lines.length > 0) current.lines.push('');
      continue;
    }

    if (isHeadingLine(trimmed)) {
      if (current.lines.some((item) => item.trim())) sections.push(current);
      current = { heading: normalizeHeading(trimmed), lines: [] };
      continue;
    }

    current.lines.push(trimmed);
  }

  if (current.lines.some((item) => item.trim())) sections.push(current);

  if (sections.length === 0) {
    sections.push({ heading: '正文', lines: lines.filter(Boolean) });
  }

  const normalized = sections.map((section) => {
    const content = section.lines.join('\n').trim();
    return {
      heading: section.heading,
      content: content.length > maxSectionChars
        ? `${content.slice(0, maxSectionChars - 3).trim()}...`
        : content
    };
  });

  const markdown = normalized.map((section) => {
    const level = section.heading === '正文' ? '##' : '##';
    return `${level} ${section.heading}\n\n${section.content}`;
  }).join('\n\n');

  return {
    sections: normalized,
    markdown,
    excerpt: normalized.map((section) => section.content).join('\n\n').slice(0, 1_200)
  };
}

export function extractPdfTextFromStreams(buffer) {
  const raw = buffer.toString('latin1');
  const chunks = [];

  const literalPattern = /\((?:\\.|[^\\()])*\)\s*Tj/g;
  for (const match of raw.matchAll(literalPattern)) {
    const decoded = decodePdfLiteral(match[0].replace(/\s*Tj$/, '').slice(1, -1));
    if (decoded.trim()) chunks.push(decoded.trim());
  }

  const arrayPattern = /\[(.*?)\]\s*TJ/gms;
  for (const match of raw.matchAll(arrayPattern)) {
    const inner = match[1];
    for (const part of inner.matchAll(/\((?:\\.|[^\\()])*\)/g)) {
      const decoded = decodePdfLiteral(part[0].slice(1, -1));
      if (decoded.trim()) chunks.push(decoded.trim());
    }
  }

  return dedupeLines(chunks.join('\n'));
}

export async function detectPdfCapabilities() {
  const caps = {
    pdftotext: await commandExists('pdftotext'),
    pdftoppm: await commandExists('pdftoppm'),
    tesseract: await commandExists('tesseract'),
    streamParse: true
  };
  caps.ocr = caps.pdftoppm && caps.tesseract;
  return caps;
}

function finalizePdfResult(filePath, text, meta = {}) {
  const cleaned = dedupeLines(String(text ?? '').replace(/\r\n/g, '\n').trim());
  const clipped = cleaned.slice(0, meta.maxChars ?? DEFAULT_MAX_CHARS);
  const structured = structurePdfText(clipped);

  return {
    ok: true,
    path: filePath,
    fileName: path.basename(filePath),
    method: meta.method ?? 'unknown',
    pageCount: meta.pageCount ?? null,
    ocrLang: meta.ocrLang ?? null,
    charCount: clipped.length,
    truncated: cleaned.length > clipped.length,
    sections: structured.sections,
    markdown: structured.markdown,
    excerpt: structured.excerpt,
    text: clipped
  };
}

async function tryPdftotext(filePath, maxChars) {
  if (!(await commandExists('pdftotext'))) {
    throw new Error('pdftotext not installed');
  }

  const { stdout } = await execFile('pdftotext', ['-layout', filePath, '-'], {
    maxBuffer: Math.max(maxChars * 4, 1024 * 1024),
    timeout: 60_000
  });

  let pageCount = null;
  if (await commandExists('pdfinfo')) {
    try {
      const info = await execFile('pdfinfo', [filePath], { timeout: 10_000 });
      const match = String(info.stdout).match(/^Pages:\s+(\d+)/m);
      if (match) pageCount = Number(match[1]);
    } catch {
      // Optional metadata.
    }
  }

  return { text: stdout, pageCount };
}

async function tryOcrPdf(filePath, options = {}) {
  if (!(await commandExists('pdftoppm')) || !(await commandExists('tesseract'))) {
    throw new Error('pdftoppm and tesseract are required for OCR');
  }

  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'star-up-pdf-ocr-'));
  const prefix = path.join(tmpDir, 'page');
  const maxPages = Math.max(1, Number(options.maxPages ?? DEFAULT_MAX_PAGES_OCR));
  const lang = String(options.lang ?? 'chi_sim+eng');

  try {
    await execFile('pdftoppm', ['-png', '-f', '1', '-l', String(maxPages), filePath, prefix], {
      timeout: 120_000
    });

    const files = (await fs.readdir(tmpDir))
      .filter((name) => name.startsWith('page-') && name.endsWith('.png'))
      .sort();

    const pageTexts = [];
    for (const file of files) {
      const imagePath = path.join(tmpDir, file);
      const { stdout } = await execFile('tesseract', [imagePath, 'stdout', '-l', lang], {
        maxBuffer: 1024 * 1024,
        timeout: 120_000
      });
      if (stdout.trim()) pageTexts.push(stdout.trim());
    }

    return {
      text: pageTexts.join('\n\n'),
      pageCount: files.length,
      lang
    };
  } finally {
    await fs.rm(tmpDir, { recursive: true, force: true }).catch(() => {});
  }
}

function isHeadingLine(line) {
  if (/^#{1,4}\s/.test(line)) return true;
  if (/^第[0-9一二三四五六七八九十百千]+[章节部分篇]\s*.+/.test(line)) return true;
  if (/^\d+(?:\.\d+)*[、.)]\s+\S/.test(line)) return true;
  if (line.length <= 40 && /[:：]$/.test(line)) return true;
  if (line.length <= 32 && /^[A-Z0-9\s\-—:：]{4,}$/.test(line)) return true;
  return false;
}

function normalizeHeading(line) {
  return line
    .replace(/^#{1,4}\s*/, '')
    .replace(/[:：]\s*$/, '')
    .trim();
}

function decodePdfLiteral(value) {
  return value
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\r')
    .replace(/\\t/g, '\t')
    .replace(/\\\(/g, '(')
    .replace(/\\\)/g, ')')
    .replace(/\\\\/g, '\\');
}

function dedupeLines(text) {
  const lines = String(text).split('\n').map((line) => line.trimEnd());
  const out = [];
  let blank = false;
  for (const line of lines) {
    if (!line.trim()) {
      if (!blank && out.length > 0) out.push('');
      blank = true;
      continue;
    }
    out.push(line);
    blank = false;
  }
  return out.join('\n').trim();
}

function estimatePageCount(buffer) {
  const matches = buffer.toString('latin1').match(/\/Type\s*\/Page\b/g);
  return matches?.length ?? null;
}

async function commandExists(command) {
  try {
    await execFile('which', [command], { timeout: 3_000 });
    return true;
  } catch {
    return false;
  }
}
