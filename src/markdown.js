const MARKDOWN_TYPES = new Set(['project', 'readme', 'launch', 'promo', 'all']);

export function markdownTypeNames() {
  return [...MARKDOWN_TYPES];
}

export function generateMarkdownDocument(source, options = {}) {
  const type = normalizeMarkdownType(options.markdownType ?? options.type ?? 'project');
  if (type === 'all') {
    return [
      projectBriefMarkdown(source),
      readmeDraftMarkdown(source),
      launchMarkdown(source),
      promoMarkdown(source)
    ].join('\n\n---\n\n');
  }
  if (type === 'readme') return readmeDraftMarkdown(source);
  if (type === 'launch') return launchMarkdown(source);
  if (type === 'promo') return promoMarkdown(source);
  return projectBriefMarkdown(source);
}

export function normalizeMarkdownType(value) {
  const normalized = String(value ?? 'project').trim().toLowerCase();
  if (['doc', 'docs', 'brief', 'project-brief'].includes(normalized)) return 'project';
  if (['readme-draft', 'readme-md'].includes(normalized)) return 'readme';
  if (['launch-kit', 'release'].includes(normalized)) return 'launch';
  if (['promotion', 'social'].includes(normalized)) return 'promo';
  if (MARKDOWN_TYPES.has(normalized)) return normalized;
  throw new Error(`Unknown markdown type: ${value}. Available types: ${markdownTypeNames().join(', ')}`);
}

function projectBriefMarkdown(source) {
  const project = source.project ?? {};
  const lines = [];
  lines.push(`# ${project.name || 'Project'} Brief`);
  lines.push('');
  if (project.description) lines.push(`> ${project.description}`);
  lines.push('');
  lines.push('## Source Snapshot');
  appendFact(lines, 'Target', source.target);
  appendFact(lines, 'Input type', source.inputType);
  appendFact(lines, 'Repository', project.repositoryUrl);
  appendFact(lines, 'Homepage', project.homepage);
  appendFact(lines, 'Topics', Array.isArray(project.topics) && project.topics.length > 0 ? project.topics.join(', ') : null);
  appendFact(lines, 'Install command', project.installCommand);
  if (source.repository) {
    appendFact(lines, 'README', source.repository.readme);
    appendFact(lines, 'Manifest', source.repository.manifest);
    appendFact(lines, 'Files scanned', source.repository.filesScanned);
  }
  appendRelatedSources(lines, source.relatedSources);
  lines.push('');
  lines.push('## What It Does');
  lines.push('');
  lines.push(source.evidence?.readmeOpening || project.description || 'TODO: summarize the project from source evidence.');
  lines.push('');
  lines.push('## Source Evidence');
  appendList(lines, 'Install commands', source.evidence?.installCommands);
  appendList(lines, 'Visual references', source.evidence?.visuals);
  appendClipList(lines, source.evidence?.documentClips);
  appendList(lines, 'Example paths', source.evidence?.examplePaths);
  appendList(lines, 'File highlights', source.evidence?.fileHighlights?.slice?.(0, 16));
  appendHeadings(lines, source.evidence?.headings);
  lines.push('');
  lines.push('## Suggested Positioning');
  lines.push('');
  lines.push(`- One-liner: ${project.description || source.evidence?.readmeOpening || 'TODO: write one sentence.'}`);
  lines.push(`- Best first proof: ${bestProof(source)}`);
  lines.push(`- Reader fit: developers, maintainers, researchers, or technical readers who need this workflow.`);
  lines.push('');
  lines.push('## Markdown Assets To Create Next');
  lines.push('');
  lines.push('- README opening rewrite');
  lines.push('- Quickstart section');
  lines.push('- Demo or screenshot caption');
  lines.push('- Product Hunt / Show HN launch note');
  lines.push('- Xiaohongshu or WeChat visual outline');
  lines.push('');
  lines.push('## Review Checklist');
  lines.push('');
  lines.push('- [ ] Claims are grounded in README, docs, paper, demo, or code evidence.');
  lines.push('- [ ] Install command or try path works.');
  lines.push('- [ ] Screenshots or figures are real source evidence.');
  lines.push('- [ ] No fake metrics, stars, users, rankings, or testimonials.');
  lines.push('- [ ] Caveats are clear where source evidence is incomplete.');
  return trimLines(lines);
}

function readmeDraftMarkdown(source) {
  const project = source.project ?? {};
  const lines = [];
  lines.push(`# ${project.name || 'Project'}`);
  lines.push('');
  lines.push(project.description || source.evidence?.readmeOpening || 'TODO: one-sentence project description.');
  lines.push('');
  lines.push('## Why This Exists');
  lines.push('');
  lines.push('TODO: explain the problem this project solves and who it is for.');
  lines.push('');
  lines.push('## Quickstart');
  lines.push('');
  if (project.installCommand) {
    lines.push('```sh');
    lines.push(project.installCommand);
    lines.push('```');
  } else if (Array.isArray(source.evidence?.installCommands) && source.evidence.installCommands.length > 0) {
    lines.push('```sh');
    lines.push(source.evidence.installCommands[0]);
    lines.push('```');
  } else {
    lines.push('```sh');
    lines.push('# TODO: add install or run command');
    lines.push('```');
  }
  lines.push('');
  lines.push('## What It Does');
  lines.push('');
  appendBullets(lines, [
    source.evidence?.readmeOpening || project.description,
    firstValue(source.evidence?.examplePaths) ? `Includes examples such as ${firstValue(source.evidence.examplePaths)}.` : null,
    firstValue(source.evidence?.visuals) ? `Has visual proof in ${firstValue(source.evidence.visuals)}.` : null
  ]);
  lines.push('');
  lines.push('## Example');
  lines.push('');
  lines.push('```sh');
  lines.push(firstValue(source.evidence?.installCommands) || project.installCommand || '# TODO: add usage example');
  lines.push('```');
  lines.push('');
  lines.push('## Evidence From The Repository');
  appendClipList(lines, source.evidence?.documentClips);
  appendList(lines, 'Examples', source.evidence?.examplePaths);
  appendList(lines, 'Relevant files', source.evidence?.fileHighlights?.slice?.(0, 12));
  lines.push('');
  lines.push('## Limitations');
  lines.push('');
  lines.push('- TODO: name incomplete features, missing examples, benchmark limits, or setup assumptions.');
  lines.push('');
  lines.push('## License');
  lines.push('');
  lines.push('TODO: add license details.');
  return trimLines(lines);
}

function launchMarkdown(source) {
  const project = source.project ?? {};
  const firstClip = Array.isArray(source.evidence?.documentClips) ? source.evidence.documentClips[0] : null;
  const lines = [];
  lines.push(`# Launch Kit: ${project.name || 'Project'}`);
  lines.push('');
  lines.push('## Tagline');
  lines.push('');
  lines.push(project.description || source.evidence?.readmeOpening || 'TODO: short tagline.');
  lines.push('');
  lines.push('## Proof To Show First');
  lines.push('');
  appendBullets(lines, [
    project.installCommand ? `Quickstart command: \`${project.installCommand}\`` : null,
    firstValue(source.evidence?.visuals) ? `Visual: ${firstValue(source.evidence.visuals)}` : null,
    firstClip?.text ? `Source clip: ${firstClip.text}` : null
  ]);
  lines.push('');
  lines.push('## X / Twitter Draft');
  lines.push('');
  lines.push(`${project.description || project.name || 'This project'}\n\nTry path: ${project.installCommand || 'TODO: add command or link'}`);
  lines.push('');
  lines.push('## Product Hunt Draft');
  lines.push('');
  lines.push(`**Tagline:** ${project.description || 'TODO: tagline'}`);
  lines.push('');
  lines.push('**Description:**');
  lines.push('');
  lines.push(`${project.name || 'This project'} helps technical users inspect the source, understand the workflow, and try it from repository evidence.`);
  lines.push('');
  lines.push('**Maker comment:**');
  lines.push('');
  lines.push(`Built around source-grounded evidence. The first thing to try is \`${project.installCommand || 'TODO: command'}\`.`);
  lines.push('');
  lines.push('## Show HN Draft');
  lines.push('');
  lines.push(`Show HN: ${project.name || 'Project'} - ${project.description || 'source-grounded technical workflow'}`);
  lines.push('');
  lines.push(`${project.name || 'This project'}: ${ensureSentence(project.description || 'TODO: describe what it does')}\n\nTry it with:\n\n\`\`\`sh\n${project.installCommand || '# TODO: command'}\n\`\`\`\n\nKnown limitation: TODO.`);
  lines.push('');
  lines.push('## Launch Checklist');
  lines.push('');
  lines.push('- [ ] README first screen explains what it does.');
  lines.push('- [ ] Install or demo command works.');
  lines.push('- [ ] Screenshot/GIF shows the real project.');
  lines.push('- [ ] Limitations are stated plainly.');
  lines.push('- [ ] Links point to repo, docs, demo, paper, or release notes.');
  return trimLines(lines);
}

function promoMarkdown(source) {
  const project = source.project ?? {};
  const lines = [];
  lines.push(`# Promotion Markdown: ${project.name || 'Project'}`);
  lines.push('');
  lines.push('## Core Angle');
  lines.push('');
  lines.push(project.description || source.evidence?.readmeOpening || 'TODO: core angle.');
  lines.push('');
  lines.push('## Channel Notes');
  lines.push('');
  lines.push('### Zhihu');
  lines.push('');
  lines.push('- Conclusion first.');
  lines.push('- Explain background, workflow, evidence, limitation, and who should read it.');
  lines.push('');
  lines.push('### Xiaohongshu');
  lines.push('');
  lines.push('- Cover: TODO: short cover text.');
  lines.push('- Card 1: problem.');
  lines.push('- Card 2: workflow or method.');
  lines.push('- Card 3: source proof.');
  lines.push('- Card 4: how to try it.');
  lines.push('- Card 5: caveat.');
  lines.push('');
  lines.push('### WeChat Official Account');
  lines.push('');
  lines.push('- Title: TODO.');
  lines.push('- Summary: TODO.');
  lines.push('- Sections: introduction, problem, workflow, evidence, limitations, reader fit.');
  lines.push('');
  lines.push('## Visual Assets');
  appendClipList(lines, source.evidence?.documentClips);
  appendList(lines, 'Visual references', source.evidence?.visuals);
  lines.push('');
  lines.push('## Source Links');
  appendBullets(lines, [
    project.repositoryUrl,
    project.homepage,
    source.target
  ]);
  return trimLines(lines);
}

function appendFact(lines, label, value) {
  if (value === undefined || value === null || value === '') return;
  lines.push(`- ${label}: ${value}`);
}

function appendList(lines, title, values) {
  const cleanValues = valuesList(values);
  if (cleanValues.length === 0) return;
  lines.push('');
  lines.push(`### ${title}`);
  lines.push('');
  appendBullets(lines, cleanValues);
}

function appendBullets(lines, values) {
  for (const value of valuesList(values)) lines.push(`- ${value}`);
}

function appendClipList(lines, clips) {
  if (!Array.isArray(clips) || clips.length === 0) return;
  lines.push('');
  lines.push('### Source Clips');
  lines.push('');
  for (const clip of clips.slice(0, 8)) {
    lines.push(`- ${clip.title || clip.kind || clip.id}: ${clip.text || clip.visualUse || ''}`);
  }
}

function appendHeadings(lines, headings) {
  if (!Array.isArray(headings) || headings.length === 0) return;
  lines.push('');
  lines.push('### Existing Headings');
  lines.push('');
  for (const heading of headings.slice(0, 12)) {
    lines.push(`- ${'#'.repeat(Math.max(1, Number(heading.level) || 1))} ${heading.text}`);
  }
}

function appendRelatedSources(lines, relatedSources) {
  if (!Array.isArray(relatedSources) || relatedSources.length === 0) return;
  lines.push('');
  lines.push('### Related Sources');
  lines.push('');
  for (const related of relatedSources) {
    const name = related.project?.name || related.paper?.title || related.target;
    lines.push(`- ${name}: ${related.inputType} (${related.target})`);
  }
}

function valuesList(values) {
  const list = Array.isArray(values) ? values : [values];
  return list
    .filter((value) => value !== undefined && value !== null && value !== '')
    .map((value) => typeof value === 'string' ? value : JSON.stringify(value));
}

function firstValue(values) {
  return valuesList(values)[0] ?? null;
}

function bestProof(source) {
  const command = firstValue(source.evidence?.installCommands) || source.project?.installCommand;
  if (command) return `the quickstart command \`${command}\``;
  const visual = firstValue(source.evidence?.visuals);
  if (visual) return `the visual reference ${visual}`;
  const clip = firstValue(source.evidence?.documentClips);
  if (clip) return clip;
  return 'TODO: choose README opening, demo screenshot, paper figure, or command evidence.';
}

function ensureSentence(value) {
  const text = String(value ?? '').trim();
  if (!text) return '';
  return /[.!?]$/.test(text) ? text : `${text}.`;
}

function trimLines(lines) {
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}
