import path from 'node:path';

import { buildProjectIntake, buildProjectSummary, formatProjectSummaryMarkdown } from '../project-summary.js';
import { parsePdfDocument, detectPdfCapabilities } from '../pdf.js';

export async function readProjectSummary(context = {}, args = {}) {
  const result = context.result;
  if (!result) {
    return { ok: false, error: 'No repository scan result in agent context.' };
  }

  const includeDocuments = args.include_documents !== false;
  const intake = context.projectIntake
    ?? (includeDocuments && (context.pdfPaths?.length || context.docPaths?.length)
      ? await buildProjectIntake(result, {
        cwd: context.cwd,
        pdfPaths: context.pdfPaths,
        docPaths: context.docPaths,
        pdfOcr: context.pdfOcr,
        env: context.env
      })
      : null);

  const summary = intake?.summary ?? buildProjectSummary(result, intake?.documents ?? []);
  const sections = args.sections ?? ['overview', 'readme', 'risks', 'fixes', 'documents', 'hints'];
  const selected = pickSummarySections(summary, sections, intake?.documents ?? []);

  return {
    ok: true,
    project: summary.project,
    sections: selected,
    markdown: intake?.summaryMarkdown ?? formatProjectSummaryMarkdown(summary, intake?.documents ?? []),
    documentCount: intake?.documents?.length ?? 0,
    errors: intake?.errors ?? []
  };
}

export async function readPdfDocument(context = {}, args = {}) {
  const filePath = String(args.path ?? args.file_path ?? '').trim();
  if (!filePath) {
    return { ok: false, error: 'read_pdf_document requires path.' };
  }

  try {
    const parsed = await parsePdfDocument(filePath, {
      cwd: context.cwd,
      ocr: args.use_ocr ?? context.pdfOcr,
      env: context.env,
      maxChars: args.max_chars
    });

    return {
      ok: true,
      fileName: parsed.fileName,
      method: parsed.method,
      pageCount: parsed.pageCount,
      truncated: parsed.truncated,
      sections: parsed.sections,
      markdown: parsed.markdown,
      excerpt: parsed.excerpt
    };
  } catch (error) {
    const capabilities = await detectPdfCapabilities();
    return {
      ok: false,
      error: error.message,
      capabilities
    };
  }
}

function pickSummarySections(summary, sections, documents) {
  const wanted = new Set(Array.isArray(sections) ? sections : [sections]);
  const out = {};

  if (wanted.has('overview') || wanted.size === 0) {
    out.overview = {
      name: summary.project.name,
      description: summary.project.description,
      installCommand: summary.project.installCommand,
      score: summary.project.score,
      grade: summary.project.grade
    };
  }
  if (wanted.has('readme')) {
    out.readme = summary.readme;
  }
  if (wanted.has('risks')) {
    out.launchRisks = summary.launchRisks;
  }
  if (wanted.has('fixes')) {
    out.topFixes = summary.topFixes;
  }
  if (wanted.has('documents')) {
    out.documents = documents.map((doc) => ({
      fileName: doc.fileName ?? path.basename(doc.path ?? ''),
      method: doc.method,
      excerpt: doc.excerpt
    }));
  }
  if (wanted.has('hints')) {
    out.synthesisHints = summary.synthesisHints;
  }
  if (wanted.has('evidence')) {
    out.evidenceBrief = summary.evidenceBrief;
  }

  return out;
}
