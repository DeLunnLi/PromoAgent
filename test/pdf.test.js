import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import {
  detectPdfCapabilities,
  extractPdfTextFromStreams,
  parsePdfDocument,
  structurePdfText
} from '../src/pdf.js';

const MINIMAL_PDF = Buffer.from(
  `%PDF-1.4
1 0 obj<<>>endobj
2 0 obj<</Length 52>>stream
BT /F1 12 Tf 100 700 Td (Hello Source2Launch PDF) Tj ET
endstream
endobj
3 0 obj<</Pages 4 0 R /Type/Catalog>>endobj
4 0 obj<</Kids[5 0 R]/Count 1/Type/Pages>>endobj
5 0 obj<</Parent 4 0 R/MediaBox[0 0 612 792]/Contents 2 0 R/Type/Page>>endobj
xref
0 6
0000000000 65535 f 
trailer<</Size 6/Root 3 0 R>>
startxref
0
%%EOF`,
  'latin1'
);

describe('pdf', () => {
  it('extracts text from PDF content streams', () => {
    const text = extractPdfTextFromStreams(MINIMAL_PDF);
    assert.match(text, /Hello Source2Launch PDF/);
  });

  it('structures raw text into sections and markdown', () => {
    const structured = structurePdfText('# Intro\n\nHello world\n\n## Details\n\nMore text');
    assert.equal(structured.sections.length >= 2, true);
    assert.match(structured.markdown, /## Intro/);
    assert.match(structured.excerpt, /Hello world/);
  });

  it('parses a minimal PDF via stream fallback', async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'star-up-pdf-'));
    const pdfPath = path.join(tempRoot, 'sample.pdf');

    try {
      await writeFile(pdfPath, MINIMAL_PDF);
      const parsed = await parsePdfDocument(pdfPath, { cwd: tempRoot, maxChars: 5000 });
      assert.equal(parsed.ok, true);
      assert.match(parsed.excerpt, /Hello Source2Launch PDF/);
      assert.equal(['pdftotext', 'stream-parse', 'ocr'].includes(parsed.method), true);
    } finally {
      await rm(tempRoot, { force: true, recursive: true });
    }
  });

  it('reports local PDF tooling capabilities', async () => {
    const caps = await detectPdfCapabilities();
    assert.equal(caps.streamParse, true);
    assert.equal(typeof caps.pdftotext, 'boolean');
    assert.equal(typeof caps.ocr, 'boolean');
  });
});
