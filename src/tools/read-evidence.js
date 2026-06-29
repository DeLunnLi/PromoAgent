import { buildEvidenceBrief } from '../promo-prompts.js';

const ALLOWED_SECTIONS = new Set([
  'summary',
  'launchRisks',
  'topFixes',
  'readmeOpening',
  'readmeFirstScreen',
  'checks',
  'installCommand',
  'headings',
  'visuals',
  'repository'
]);

export function readRepoEvidence(result, sections = []) {
  const requested = normalizeSections(sections);
  const payload = {};

  if (requested.has('summary')) {
    payload.summary = {
      project: result.project?.name,
      description: result.project?.description,
      score: result.score,
      grade: result.grade,
      repositoryUrl: result.project?.repositoryUrl
    };
  }

  if (requested.has('installCommand')) {
    payload.installCommand = result.project?.installCommand ?? null;
  }

  if (requested.has('launchRisks')) {
    payload.launchRisks = result.evidence?.launchRisks ?? [];
  }

  if (requested.has('topFixes')) {
    payload.topFixes = (result.topFixes ?? []).slice(0, 6);
  }

  if (requested.has('readmeOpening')) {
    payload.readmeOpening = result.evidence?.readmeOpening ?? '';
  }

  if (requested.has('readmeFirstScreen')) {
    payload.readmeFirstScreen = result.evidence?.readmeFirstScreen ?? '';
  }

  if (requested.has('headings')) {
    payload.headings = result.evidence?.headings ?? [];
  }

  if (requested.has('visuals')) {
    payload.visuals = result.evidence?.visuals ?? [];
    payload.visualUrls = result.evidence?.visualUrls ?? [];
  }

  if (requested.has('checks')) {
    payload.checks = (result.checks ?? []).map((check) => ({
      id: check.id,
      label: check.label,
      score: check.score,
      max: check.max,
      summary: check.summary
    }));
  }

  if (requested.has('repository')) {
    payload.repository = {
      stars: result.repository?.stars,
      topics: result.repository?.topics,
      latestRelease: result.repository?.latestRelease,
      readme: result.repository?.readme
    };
  }

  payload.evidenceBrief = buildEvidenceBrief({
    project: result.project,
    heuristicScore: { score: result.score, grade: result.grade },
    evidence: result.evidence,
    topFixes: result.topFixes,
    checks: result.checks
  });

  return payload;
}

function normalizeSections(sections) {
  const list = Array.isArray(sections) ? sections : [sections];
  const normalized = list
    .map((section) => String(section ?? '').trim())
    .filter(Boolean);

  if (normalized.length === 0) {
    return new Set(['summary', 'launchRisks', 'topFixes', 'installCommand', 'readmeOpening']);
  }

  for (const section of normalized) {
    if (!ALLOWED_SECTIONS.has(section)) {
      throw new Error(`Unknown evidence section: ${section}`);
    }
  }

  return new Set(normalized);
}

export { ALLOWED_SECTIONS };
