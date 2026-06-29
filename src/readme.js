export function generateReadmeSuggestions(result) {
  const project = result.project;
  const evidence = result.evidence ?? {};
  const missingVisual = !Array.isArray(evidence.visuals) || evidence.visuals.length === 0;
  const installCommand = project.installCommand || 'REPLACE_WITH_INSTALL_COMMAND';
  const demoLine = missingVisual
    ? '<!-- Add a GIF or screenshot here: ![Demo](docs/demo.gif) -->'
    : evidence.visuals[0];
  const topFixes = result.topFixes.slice(0, 5).map((fix) => ({
    severity: fix.severity,
    message: fix.message,
    fix: fix.fix
  }));

  return {
    project: project.name,
    score: result.score,
    grade: result.grade,
    currentOpening: evidence.readmeOpening || '',
    suggestedOneLiner: oneLiner(project),
    suggestedFirstScreen: [
      `# ${project.name}`,
      '',
      oneLiner(project),
      '',
      demoLine,
      '',
      '## Quickstart',
      '',
      '```sh',
      installCommand,
      '```',
      '',
      '## Why it matters',
      '',
      ...whyItMatters(project).map((item) => `- ${item}`),
      '',
      project.repositoryUrl ? `[GitHub](${project.repositoryUrl})` : '<!-- Add GitHub repository URL here -->'
    ].join('\n'),
    priorityFixes: topFixes,
    checklist: [
      'Keep the first sentence under 35 words.',
      'Put a GIF, screenshot, or terminal output before deep documentation.',
      'Show one copy-paste install command in the first screen.',
      'Include one working usage example immediately after install.',
      'Add 3-5 precise topics or package keywords.'
    ]
  };
}

export function formatReadmeSuggestions(suggestions) {
  const lines = [];
  lines.push(`# ${suggestions.project} · README 改写建议`);
  lines.push('');
  lines.push('> 由 Source2Launch 生成 · 开源项目发布资料参考');
  lines.push('');
  lines.push('资料检查：根据 README、安装命令、示例和元数据生成；不代表项目质量评分。');

  if (suggestions.currentOpening) {
    lines.push('');
    lines.push('## 当前首段');
    lines.push('');
    lines.push(suggestions.currentOpening);
  }

  lines.push('');
  lines.push('## 建议一句话定位');
  lines.push('');
  lines.push(suggestions.suggestedOneLiner);

  lines.push('');
  lines.push('## 建议首屏 Markdown');
  lines.push('');
  lines.push('```md');
  lines.push(suggestions.suggestedFirstScreen);
  lines.push('```');

  lines.push('');
  lines.push('## 优先修复');
  if (suggestions.priorityFixes.length === 0) {
    lines.push('');
    lines.push('未发现紧急 README 问题。');
  } else {
    lines.push('');
    for (const fix of suggestions.priorityFixes) {
      lines.push(`- **[${fix.severity}]** ${fix.message}`);
      lines.push(`  - 建议：${fix.fix}`);
    }
  }

  lines.push('');
  lines.push('## 发布检查清单');
  lines.push('');
  for (const item of suggestions.checklist) {
    lines.push(`- [ ] ${item}`);
  }

  return lines.join('\n');
}

function oneLiner(project) {
  const description = stripEnding(project.description || '');
  if (!description) {
    return `${project.name} helps [target users] [achieve a concrete outcome] without [specific pain].`;
  }
  if (wordCount(description) < 6 || /\b(simple|tiny|awesome|tool)\b/i.test(description)) {
    return `${project.name} helps [target users] [achieve a concrete outcome] without [specific pain].`;
  }
  if (description.length <= 150) return description;
  return `${description.slice(0, 147).trim()}...`;
}

function whyItMatters(project) {
  const topics = project.topics.slice(0, 3);
  const items = [
    'It makes the project value clear before visitors scroll.',
    'It gives users a short path from discovery to first successful run.'
  ];

  if (topics.length > 0) {
    items.push(`It is positioned around ${topics.join(', ')} so the right users can find it.`);
  }

  return items;
}

function stripEnding(value) {
  return String(value).trim().replace(/[。.]$/, '');
}

function wordCount(value) {
  return String(value).split(/\s+/).filter(Boolean).length;
}
