import path from 'node:path';

const RASTER_IMAGE = /\.(png|jpe?g|webp|gif)$/i;

export function projectDescriptionForChinese(project) {
  const description = project.description ?? '';
  if (/audit an open source repo.*promotion copy/i.test(description)) {
    return '它可以读取开源仓库或论文材料，提取 README、Demo、安装命令、关键结论等证据，并一键生成各平台推广文案和配图。';
  }
  if (/audit github repositories for launch readiness/i.test(description)) {
    return '它可以体检 GitHub 仓库的发布准备度，帮助维护者找出 README、Demo 和包装信息里的短板。';
  }
  if (description.length > 120) {
    return `${description.slice(0, 117)}…`;
  }
  return description || `${project.name} 是一个开源开发者工具。`;
}

export function inferTargetUsers(project) {
  const haystack = `${project.description} ${project.topics.join(' ')}`.toLowerCase();
  if (/readme|open-source|github|repo|launch|paper|content|promotion/.test(haystack)) {
    return '开源作者、独立开发者、开发者工具爱好者';
  }
  if (/ai|llm|agent|prompt/.test(haystack)) {
    return 'AI 应用开发者、Agent 工程师、独立开发者';
  }
  if (/react|vue|frontend|css|ui/.test(haystack)) {
    return '前端工程师、UI 工程师、Web 开发者';
  }
  if (/cli|terminal|shell/.test(haystack)) {
    return 'CLI 工具用户、后端工程师、效率工具爱好者';
  }
  return '开发者、开源项目维护者、喜欢试新工具的工程师';
}

export function hashtags(project, defaults = ['#开源项目', '#GitHub', '#程序员', '#开发者工具']) {
  const topicTags = project.topics
    .slice(0, 4)
    .map((topic) => `#${topic.replace(/[^\p{Letter}\p{Number}_-]/gu, '')}`)
    .filter((tag) => tag.length > 1);

  return [...new Set([...defaults, ...topicTags])].slice(0, 8);
}

export function strongestChecks(result) {
  const strong = result.checks
    .filter((check) => check.score / check.max >= 0.75)
    .sort((left, right) => (right.score / right.max) - (left.score / right.max))
    .slice(0, 4);

  if (strong.length > 0) return strong;

  return [...result.checks]
    .sort((left, right) => right.score - left.score)
    .slice(0, 3);
}

export function sceneStrengths(result) {
  const project = result.project;
  const scenes = strongestChecks(result)
    .map((check) => checkToScene(check, project))
    .filter(Boolean);

  if (scenes.length > 0) return scenes.slice(0, 4);

  return [
    projectDescriptionForChinese(project),
    project.installCommand ? `一行命令就能试：\`${project.installCommand}\`` : 'README 里有清晰的使用路径',
    project.repositoryUrl ? `仓库：${project.repositoryUrl}` : '适合先 star 再慢慢看'
  ].slice(0, 3);
}

export function xhsTitleOptions(project, result) {
  const name = project.name;
  const options = [
    `开源作者必看｜${name} 做发布包`,
    `开源项目怎么发布？试试 ${name}`,
    `3 分钟搞懂 ${name} 是干什么的`,
    `最近收藏的开发者工具：${name}`
  ];

  if (result.score >= 80) {
    options.unshift(`${name}：一个展示很完整的开源项目`);
  } else {
    options.unshift(`${name}：潜力不错，展示还能再打磨`);
  }

  return options.slice(0, 5);
}

export function xhsHook(project, result) {
  if (/launch|readme|paper|promotion|content/i.test(`${project.description} ${project.topics.join(' ')}`)) {
    return result.score >= 80
      ? '做了开源项目或论文，最难的往往不是写一句宣传语，而是把证据讲清楚。'
      : '很多项目功能已经有了，但发布时缺少清晰证据、平台文案和配图计划。';
  }
  return `如果你最近在找值得试的开发者工具，${project.name} 可以先放进收藏夹。`;
}

export function wechatMomentsVariants(project, result, strengths) {
  const description = projectDescriptionForChinese(project);
  const install = project.installCommand ? `\n\n\`${project.installCommand}\`` : '';
  const link = project.repositoryUrl ? `\n\n${project.repositoryUrl}` : '';
  const bullets = strengths.slice(0, 3).map((item) => `- ${item}`).join('\n');

  return {
    recommend: [
      `最近发现一个开源工具：${project.name}`,
      '',
      description,
      '',
      '几个我觉得实用的点：',
      bullets,
      install,
      link
    ].filter(Boolean).join('\n'),
    insight: [
      `如果你也在做开源，可以看看 ${project.name} 的展示方式。`,
      '',
      description,
      '',
      '它做得比较好的地方：',
      bullets,
      install,
      link
    ].filter(Boolean).join('\n'),
    quick: [
      `分享一个开发者工具：${project.name}`,
      '',
      strengths[0] ?? description,
      install,
      link
    ].filter(Boolean).join('\n')
  };
}

export function buildTemplateData(result) {
  const project = result.project;
  const strengths = sceneStrengths(result);
  const topFixes = result.topFixes.length > 0
    ? result.topFixes.slice(0, 5).map((fix) => `- ${fix.fix}`)
    : ['- 当前没有发现高优先级改进项。'];
  const tags = hashtags(project);
  const titleOptions = xhsTitleOptions(project, result);
  const wechatVariants = wechatMomentsVariants(project, result, strengths);

  return {
    grade: result.grade,
    hook: xhsHook(project, result),
    homepage_url: project.homepage ?? '',
    install_command: project.installCommand ?? '',
    project_description: projectDescriptionForChinese(project),
    project_name: project.name,
    repo_url: project.repositoryUrl ?? '',
    score: String(result.score),
    stars: result.repository.stars === null ? 'unknown' : String(result.repository.stars),
    strengths: strengths.map((item) => `- ${item}`).join('\n'),
    tags: tags.join(' '),
    target_users: inferTargetUsers(project),
    title_options: titleOptions.map((title, index) => `${index + 1}. ${title}`).join('\n'),
    top_fixes: topFixes.join('\n'),
    topics: project.topics.length > 0 ? project.topics.join(', ') : 'none',
    wechat_recommend: wechatVariants.recommend,
    wechat_insight: wechatVariants.insight,
    wechat_quick: wechatVariants.quick,
    cover_image: '',
    cover_image_wechat: ''
  };
}

export function appendCoverImageSection(lines, coverImage, platformLabel) {
  if (!coverImage) return;
  lines.push('');
  lines.push('## 推广配图');
  lines.push('');
  lines.push(`![${platformLabel}封面](${coverImage})`);
  lines.push('');
  lines.push('> 由 `source2launch optimize` 自动生成，发布时可作为封面或首图。');
}

export function coverImageMarkdown(coverImage, platformLabel) {
  if (!coverImage) return '';
  const lines = [];
  appendCoverImageSection(lines, coverImage, platformLabel);
  return lines.join('\n');
}

export function resolvePromoImageContext(result, cwd, options = {}) {
  if (options.imageUrl) {
    return { imageUrl: options.imageUrl, imageFile: options.imageFile || null };
  }

  const remoteUrl = findRemoteRasterUrl(result);
  if (remoteUrl) {
    return { imageUrl: remoteUrl, imageFile: null };
  }

  const localRelative = findLocalRasterVisual(result);
  if (localRelative && result.project.repositoryUrl) {
    const rawUrl = toGithubRawUrl(result.project.repositoryUrl, localRelative);
    if (rawUrl) {
      return { imageUrl: rawUrl, imageFile: null };
    }
  }

  if (localRelative) {
    return { imageUrl: null, imageFile: pathResolve(cwd, localRelative) };
  }

  return { imageUrl: null, imageFile: null };
}

function checkToScene(check, project) {
  switch (check.id) {
    case 'install-command': {
      const match = check.summary.match(/(\d+)/);
      if (project.installCommand) {
        return `复制 \`${project.installCommand}\` 就能跑${match ? '，安装命令很短' : ''}`;
      }
      return 'README 里能看到清晰的安装/运行方式';
    }
    case 'examples': {
      const match = check.summary.match(/(\d+)/);
      return match ? `examples/ 里有 ${match[1]} 个示例，照着改就能用` : '自带示例目录，上手成本低';
    }
    case 'topics': {
      const match = check.summary.match(/(\d+)/);
      const sample = project.topics.slice(0, 2).join('、');
      return match
        ? `GitHub Topics 配了 ${match[1]} 个关键词${sample ? `（如 ${sample}）` : ''}，更容易被搜到`
        : 'Topics 设置有助于 GitHub 内搜索曝光';
    }
    case 'visual-demo':
      return 'README 有 GIF 或视频演示，首屏就能看懂在做什么';
    case 'demo-usage':
      return '使用路径清楚：打开 README 就知道下一步该做什么';
    case 'first-screen':
      return 'README 首屏信息完整，项目名、价值、Demo、安装命令都在前面';
    case 'readme-pitch':
      return '一句话定位清楚，不用翻很久才知道项目解决什么问题';
    case 'package-release':
      return '发布信息较完整，npm/版本号等信号有助于建立信任';
    default:
      return null;
  }
}

function findRemoteRasterUrl(result) {
  for (const url of result.evidence?.visualUrls ?? []) {
    if (RASTER_IMAGE.test(url.split('?')[0])) return url;
  }

  for (const visual of result.evidence?.visuals ?? []) {
    const markdownMatch = visual.match(/!\[[^\]]*]\(([^)]+)\)/);
    if (!markdownMatch) continue;
    const candidate = markdownMatch[1].trim().split(/\s/)[0];
    if (/^https?:\/\//i.test(candidate) && RASTER_IMAGE.test(candidate.split('?')[0])) {
      return candidate;
    }
  }

  return null;
}

function findLocalRasterVisual(result) {
  for (const visual of result.evidence?.visuals ?? []) {
    const markdownMatch = visual.match(/!\[[^\]]*]\(([^)]+)\)/);
    if (!markdownMatch) continue;
    const candidate = markdownMatch[1].trim().split(/\s/)[0];
    if (!/^https?:\/\//i.test(candidate) && RASTER_IMAGE.test(candidate)) {
      return candidate;
    }
  }
  return null;
}

function toGithubRawUrl(repositoryUrl, relativePath) {
  const match = String(repositoryUrl).match(/github\.com\/([^/]+)\/([^/]+)/i);
  if (!match) return null;
  const owner = match[1];
  const repo = match[2].replace(/\.git$/i, '');
  return `https://raw.githubusercontent.com/${owner}/${repo}/main/${relativePath.replace(/^\.\//, '')}`;
}

function pathResolve(cwd, relativePath) {
  return path.resolve(cwd, relativePath);
}
