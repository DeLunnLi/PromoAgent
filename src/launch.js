export function generateLaunchPack(result) {
  const project = result.project;
  const angles = strongestAngles(result);
  const repoUrl = project.repositoryUrl || 'REPLACE_WITH_REPO_URL';
  const install = project.installCommand || 'REPLACE_WITH_INSTALL_COMMAND';
  const description = stripEnding(project.description || `${project.name} is an open source project.`);
  const chineseDescription = projectDescriptionForChinese(project);
  const risks = result.evidence?.launchRisks ?? [];

  return {
    project: project.name,
    score: result.score,
    grade: result.grade,
    blockers: risks,
    githubAbout: {
      description: shortText(description, 155),
      topics: suggestedTopics(project)
    },
    showHn: {
      title: `Show HN: ${project.name} - ${shortText(description, 70)}`,
      body: [
        `I built ${project.name}, an open source project for ${targetUsers(project)}.`,
        '',
        description,
        '',
        'What it does:',
        ...angles.map((angle) => `- ${angle}`),
        '',
        `Try it: ${install}`,
        `Repo: ${repoUrl}`,
        '',
        'I would appreciate feedback on whether the README makes the value clear in the first 10 seconds.'
      ].join('\n')
    },
    redditV2ex: {
      title: `做了一个开源项目：${project.name}，想请大家看看 README 是否说清楚了`,
      body: [
        `我最近在做 ${project.name}。`,
        '',
        chineseDescription,
        '',
        '现在主要想验证两件事：',
        '- 打开 GitHub 的前 10 秒，大家是否能看懂它解决什么问题',
        '- Quickstart 和 examples 是否足够让人愿意试一下',
        '',
        `一行体验：${install}`,
        `仓库：${repoUrl}`,
        '',
        '欢迎直接提 README、Demo、安装路径上的建议。'
      ].join('\n')
    },
    xThread: {
      posts: [
        `I built ${project.name}: ${shortText(description, 170)}`,
        `The problem: many open source repos lose visitors before they understand the value. ${project.name} focuses on making the first 10 seconds clearer.`,
        `Quickstart: ${install}`,
        `Repo: ${repoUrl}`
      ]
    },
    productHunt: {
      tagline: shortText(description, 60),
      firstComment: [
        `Hi Product Hunt - I built ${project.name}.`,
        '',
        description,
        '',
        `The project is open source: ${repoUrl}`,
        `You can try it with: ${install}`,
        '',
        'I would love feedback on the positioning and README clarity.'
      ].join('\n')
    },
    badges: badgeSuggestions(project),
    checklist: launchChecklist(result)
  };
}

export function formatLaunchPack(pack) {
  const lines = [];
  lines.push(`# ${pack.project} · 多渠道发布包`);
  lines.push('');
  lines.push('> 由 Source2Launch 生成 · 开源项目发布资料参考');
  lines.push('');
  lines.push('资料检查：见 `heuristic-audit.md`（仅供 CI / 资料完整度参考）');

  lines.push('');
  lines.push('## 发布阻碍');
  if (pack.blockers.length === 0) {
    lines.push('');
    lines.push('未发现明显阻碍，可以开始推广。');
  } else {
    lines.push('');
    for (const blocker of pack.blockers) lines.push(`- ${blocker.message}`);
  }

  lines.push('');
  lines.push('## GitHub About');
  lines.push('');
  lines.push(`**Description：** ${pack.githubAbout.description}`);
  lines.push(`**Topics：** ${pack.githubAbout.topics.join(', ')}`);

  lines.push('');
  lines.push('## Show HN');
  lines.push('');
  lines.push(`**Title：** ${pack.showHn.title}`);
  lines.push('');
  lines.push(pack.showHn.body);

  lines.push('');
  lines.push('## Reddit / V2EX');
  lines.push('');
  lines.push(`**Title：** ${pack.redditV2ex.title}`);
  lines.push('');
  lines.push(pack.redditV2ex.body);

  lines.push('');
  lines.push('## X Thread');
  lines.push('');
  pack.xThread.posts.forEach((post, index) => {
    lines.push(`${index + 1}. ${post}`);
  });

  lines.push('');
  lines.push('## Product Hunt');
  lines.push('');
  lines.push(`**Tagline：** ${pack.productHunt.tagline}`);
  lines.push('');
  lines.push(pack.productHunt.firstComment);

  lines.push('');
  lines.push('## Badges');
  lines.push('');
  for (const badge of pack.badges) lines.push(`- ${badge}`);

  lines.push('');
  lines.push('## 发布清单');
  lines.push('');
  for (const item of pack.checklist) lines.push(`- [ ] ${item}`);

  return lines.join('\n');
}

function strongestAngles(result) {
  const strong = result.checks
    .filter((check) => check.score / check.max >= 0.75)
    .slice(0, 4)
    .map((check) => angleForCheck(check));

  if (strong.length > 0) return strong;

  return [
    'Clearer README positioning',
    'Shorter path from install to first result',
    'More launch-ready examples and visuals'
  ];
}

function angleForCheck(check) {
  const map = {
    'demo-usage': 'Has a visible demo or usage path',
    examples: 'Includes examples users can copy',
    'first-screen': 'Makes the first README screen useful',
    'install-command': 'Offers a short copy-paste install path',
    'package-release': 'Has package and release metadata',
    'readme-pitch': 'Explains the project value early',
    topics: 'Uses discoverable topics and keywords',
    'visual-demo': 'Shows visual proof instead of only text'
  };
  return map[check.id] ?? check.summary;
}

function suggestedTopics(project) {
  const base = project.topics.length > 0 ? project.topics : ['open-source', 'github', 'developer-tools'];
  return [...new Set(base)].slice(0, 8);
}

function badgeSuggestions(project) {
  const repoPath = repoPathFromUrl(project.repositoryUrl);
  if (!repoPath) {
    return [
      'Add a CI badge once the repository URL is public.',
      'Add an npm version badge after publishing.',
      'Add a license badge if the project has a license.'
    ];
  }

  return [
    `[![CI](https://github.com/${repoPath}/actions/workflows/ci.yml/badge.svg)](https://github.com/${repoPath}/actions/workflows/ci.yml)`,
    `[![License](https://img.shields.io/github/license/${repoPath})](https://github.com/${repoPath}/blob/main/LICENSE)`,
    `[![Stars](https://img.shields.io/github/stars/${repoPath}?style=social)](https://github.com/${repoPath})`
  ];
}

function launchChecklist(result) {
  const risks = result.evidence?.launchRisks ?? [];
  const checklist = [
    'README first screen has title, one-liner, visual, install command, and first result.',
    'Launch copy is different for GitHub, Show HN, Reddit/V2EX, X, and Product Hunt.',
    'No TODO, placeholder text, private notes, or local URLs remain in public docs.',
    'Repo has license, package metadata, topics, examples, and release notes.',
    'Primary demo image or GIF renders correctly on GitHub mobile and desktop.'
  ];

  for (const risk of risks.slice(0, 3)) {
    checklist.unshift(`Fix blocker: ${risk.message}`);
  }

  return checklist;
}

function targetUsers(project) {
  const text = `${project.description} ${project.topics.join(' ')}`.toLowerCase();
  if (/readme|github|open-source|repo|launch/.test(text)) return 'open source maintainers and indie developers';
  if (/ai|llm|agent/.test(text)) return 'AI builders';
  if (/cli|terminal/.test(text)) return 'developers who prefer command-line tools';
  return 'developers';
}

function projectDescriptionForChinese(project) {
  const description = stripEnding(project.description || '');
  if (/audit an open source repo.*promotion copy/i.test(description)) {
    return '它可以读取开源仓库或论文材料，提取 README、Demo、安装命令、关键结论等证据，并生成适合小红书和微信转发的推广文案。';
  }
  if (/audit github repositories for launch readiness/i.test(description)) {
    return '它可以体检 GitHub 仓库的发布准备度，帮助维护者找出 README、Demo 和包装信息里的短板。';
  }
  return description || `${project.name} 是一个开源项目。`;
}

function repoPathFromUrl(url) {
  if (!url) return '';
  const match = String(url).match(/github\.com\/([^/\s]+\/[^/\s#?]+)/i);
  return match ? match[1].replace(/\.git$/i, '') : '';
}

function shortText(value, maxLength) {
  const text = stripEnding(value);
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3).trim()}...`;
}

function stripEnding(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim().replace(/[。.]$/, '');
}
