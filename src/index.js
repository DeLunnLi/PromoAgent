import { execFile as execFileCallback } from 'node:child_process';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';

const execFile = promisify(execFileCallback);

/**
 * @typedef {Object} CheckTemplate
 * @property {string} id - 检查项唯一标识
 * @property {string} label - 检查项显示名称
 * @property {number} max - 该检查项的最大分数
 */

/**
 * @typedef {Object} CheckResult
 * @property {string} id - 检查项ID
 * @property {string} label - 检查项名称
 * @property {number} max - 最大分数
 * @property {number} score - 实际得分
 * @property {string} summary - 检查结果摘要
 * @property {Finding[]} findings - 发现的问题列表
 */

/**
 * @typedef {Object} Finding
 * @property {string} severity - 严重程度 (high|medium|low)
 * @property {string} message - 问题描述
 * @property {string} fix - 修复建议
 */

/**
 * @typedef {Object} AnalysisResult
 * @property {string} version - 版本号
 * @property {string} target - 分析目标路径或URL
 * @property {string} source - 数据来源 (local|github)
 * @property {number} score - 总分
 * @property {string} grade - 评分等级 (A|B|C|D|F)
 * @property {ProjectInfo} project - 项目信息
 * @property {EvidenceInfo} evidence - 证据信息
 * @property {RepositoryInfo} repository - 仓库信息
 * @property {CheckResult[]} checks - 各维度检查结果
 * @property {TopFix[]} topFixes - 优先修复建议
 */

/**
 * @typedef {Object} ProjectInfo
 * @property {string} name - 项目名称
 * @property {string|null} packageName - 包名
 * @property {string} description - 项目描述
 * @property {string|null} repositoryUrl - 仓库URL
 * @property {string|null} homepage - 主页地址
 * @property {string|null} installCommand - 安装命令
 * @property {string[]} topics - 主题标签
 */

/**
 * @typedef {Object} EvidenceInfo
 * @property {string} readmeOpening - README 开头段落
 * @property {string} readmeFirstScreen - README 首屏内容
 * @property {HeadingInfo[]} headings - 标题列表
 * @property {string[]} installCommands - 安装命令列表
 * @property {string[]} visuals - 视觉引用列表
 * @property {string[]} visualUrls - 图片URL列表
 * @property {LaunchRisk[]} launchRisks - 发布风险
 * @property {Object} packageScripts - 包脚本
 * @property {string[]} examplePaths - 示例文件路径
 */

/**
 * @typedef {Object} HeadingInfo
 * @property {number} level - 标题级别 (1-4)
 * @property {string} text - 标题文本
 */

/**
 * @typedef {Object} LaunchRisk
 * @property {string} id - 风险ID
 * @property {string} message - 风险描述
 */

/**
 * @typedef {Object} RepositoryInfo
 * @property {string} root - 仓库根目录
 * @property {number} filesScanned - 扫描的文件数
 * @property {string|null} readme - README 文件路径
 * @property {string|null} manifest - 清单文件路径
 * @property {number|null} stars - GitHub Stars 数量
 * @property {string[]} topics - 主题标签
 * @property {string|null} latestRelease - 最新发布版本
 */

/**
 * @typedef {Object} TopFix
 * @property {string} check - 相关检查项ID
 * @property {string} severity - 严重程度
 * @property {string} message - 问题描述
 * @property {string} fix - 修复建议
 */

/**
 * @typedef {Object} GitHubRepoInfo
 * @property {string} owner - 仓库所有者
 * @property {string} repo - 仓库名
 * @property {string} cloneUrl - 克隆URL
 * @property {string} webUrl - Web访问URL
 */

/**
 * @typedef {Object} AnalysisContext
 * @property {Object|null} metadata - GitHub 元数据
 * @property {string} source - 数据来源
 * @property {string} target - 目标标识
 */

/** @type {Object<string, CheckTemplate>} */
const CHECKS = {
  readmePitch: { id: 'readme-pitch', label: 'README one-liner', max: 16 },
  visualDemo: { id: 'visual-demo', label: 'GIF or visual demo', max: 12 },
  install: { id: 'install-command', label: 'Install command', max: 12 },
  demoUsage: { id: 'demo-usage', label: 'Demo and usage', max: 12 },
  topics: { id: 'topics', label: 'Topics and keywords', max: 10 },
  examples: { id: 'examples', label: 'Examples', max: 10 },
  firstScreen: { id: 'first-screen', label: 'README first screen', max: 12 },
  packageRelease: { id: 'package-release', label: 'Release/package completeness', max: 16 }
};

const SKIP_DIRS = new Set([
  '.cache',
  '.git',
  '.hg',
  '.next',
  '.svn',
  '.turbo',
  '.venv',
  '__pycache__',
  'build',
  'coverage',
  'dist',
  'node_modules',
  'out',
  'target',
  'vendor',
  'venv'
]);

/**
 * 分析目标仓库
 * @param {string} input - 目标路径或 GitHub URL
 * @param {Object} options - 选项
 * @param {string} [options.cwd] - 当前工作目录
 * @returns {Promise<AnalysisResult>} 分析结果
 */
export async function analyzeTarget(input = '.', options = {}) {
  const target = String(input || '.').trim();
  const githubRepo = parseGitHubRepo(target);

  if (githubRepo) {
    const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'star-up-'));
    const clonePath = path.join(tempRoot, githubRepo.repo);

    try {
      await execFile('git', ['clone', '--depth', '1', githubRepo.cloneUrl, clonePath], {
        maxBuffer: 1024 * 1024 * 8,
        timeout: 45_000
      });
      const metadata = await fetchGitHubMetadata(githubRepo.owner, githubRepo.repo);
      return analyzeRepositoryPath(clonePath, {
        metadata,
        source: 'github',
        target: githubRepo.webUrl
      });
    } finally {
      await fs.rm(tempRoot, { force: true, recursive: true });
    }
  }

  const root = path.resolve(options.cwd ?? process.cwd(), target);
  const stat = await fs.stat(root).catch(() => null);
  if (!stat || !stat.isDirectory()) {
    throw new Error(`Target is not a directory or GitHub repo URL: ${target}`);
  }

  return analyzeRepositoryPath(root, {
    metadata: null,
    source: 'local',
    target: root
  });
}

/**
 * 分析仓库路径
 * @param {string} root - 仓库根目录
 * @param {AnalysisContext} context - 分析上下文
 * @returns {Promise<AnalysisResult>} 分析结果
 */
export async function analyzeRepositoryPath(root, context = {}) {
  const facts = await collectFacts(root, context.metadata ?? null);
  const project = projectInfo(facts, root, context);
  const evidence = evidenceInfo(facts);
  const checks = [
    checkReadmePitch(facts),
    checkVisualDemo(facts),
    checkInstallCommand(facts),
    checkDemoUsage(facts),
    checkTopics(facts),
    checkExamples(facts),
    checkFirstScreen(facts),
    checkPackageRelease(facts)
  ];
  const score = checks.reduce((sum, check) => sum + check.score, 0);
  const topFixes = checks
    .flatMap((check) => check.findings.map((finding) => ({
      ...finding,
      check: check.id,
      impact: check.max - check.score
    })))
    .sort((left, right) => {
      const severityOrder = { high: 0, medium: 1, low: 2 };
      return severityOrder[left.severity] - severityOrder[right.severity] || right.impact - left.impact;
    })
    .slice(0, 6)
    .map(({ impact, ...finding }) => finding);

  return {
    version: '0.2.0',
    target: context.target ?? root,
    source: context.source ?? 'local',
    score,
    grade: grade(score),
    project,
    evidence,
    repository: {
      root,
      filesScanned: facts.files.length,
      readme: facts.readmePath,
      manifest: facts.manifestPath,
      stars: facts.metadata?.stargazers_count ?? null,
      topics: facts.topics,
      latestRelease: facts.metadata?.latest_release ?? null
    },
    checks,
    topFixes
  };
}

async function collectFacts(root, metadata) {
  const files = await walk(root);
  const readmePath = findRootFile(files, /^readme(\.(md|mdx|markdown|rst|txt))?$/i);
  const readmeText = readmePath ? await readText(path.join(root, readmePath)) : '';
  const packagePath = findRootFile(files, /^package\.json$/i);
  const packageJson = packagePath ? await readJson(path.join(root, packagePath)) : null;
  const pyprojectPath = findRootFile(files, /^pyproject\.toml$/i);
  const pyprojectText = pyprojectPath ? await readText(path.join(root, pyprojectPath)) : '';
  const cargoPath = findRootFile(files, /^Cargo\.toml$/);
  const cargoText = cargoPath ? await readText(path.join(root, cargoPath)) : '';
  const goModPath = findRootFile(files, /^go\.mod$/);
  const goModText = goModPath ? await readText(path.join(root, goModPath)) : '';
  const tags = await gitTags(root);
  const topics = uniqueStrings([
    ...(metadata?.topics ?? []),
    ...(Array.isArray(packageJson?.keywords) ? packageJson.keywords : [])
  ]);

  return {
    root,
    files,
    readmePath,
    readmeText,
    packagePath,
    packageJson,
    pyprojectPath,
    pyprojectText,
    cargoPath,
    cargoText,
    goModPath,
    goModText,
    manifestPath: packagePath ?? pyprojectPath ?? cargoPath ?? goModPath ?? null,
    metadata,
    tags,
    topics
  };
}

function projectInfo(facts, root, context) {
  const packageName = facts.packageJson?.name ? String(facts.packageJson.name) : '';
  const readmeTitle = firstHeading(facts.readmeText);
  const name = firstPresent([
    facts.metadata?.name,
    packageName,
    readmeTitle,
    path.basename(root)
  ]);
  const description = trimForSummary(firstPresent([
    facts.metadata?.description,
    facts.packageJson?.description,
    openingParagraph(facts.readmeText),
    `${name} is an open source project.`
  ]));
  const repositoryUrl = normalizeRepositoryUrl(firstPresent([
    facts.metadata?.html_url,
    packageRepositoryUrl(facts.packageJson),
    context.source === 'github' ? context.target : ''
  ]));
  const installCommand = bestInstallCommand(facts);

  return {
    name,
    packageName: packageName || null,
    description,
    repositoryUrl: repositoryUrl || null,
    homepage: firstPresent([facts.metadata?.homepage, facts.packageJson?.homepage]) || null,
    installCommand: installCommand || null,
    topics: facts.topics
  };
}

function evidenceInfo(facts) {
  const readmeFirstScreen = facts.readmeText ? compactSnippet(facts.readmeText.slice(0, 1_800), 1_800) : '';
  const installCommandList = installCommands(facts.readmeText);

  return {
    readmeOpening: openingParagraph(facts.readmeText),
    readmeFirstScreen,
    headings: readmeHeadings(facts.readmeText).slice(0, 16),
    installCommands: installCommandList.slice(0, 5),
    visuals: visualReferences(facts.readmeText).slice(0, 5),
    visualUrls: extractImageUrls(facts.readmeText).slice(0, 3),
    launchRisks: launchRisks(facts),
    packageScripts: packageScripts(facts.packageJson),
    examplePaths: facts.files.filter((file) => /^(examples?|samples?|demos?|playground|templates)\//i.test(normalizePath(file))).slice(0, 12)
  };
}

function launchRisks(facts) {
  const risks = [];
  const readmePlain = stripCodeBlocks(facts.readmeText ?? '');
  const haystack = [
    readmePlain,
    facts.packageJson ? JSON.stringify(facts.packageJson) : '',
    facts.pyprojectText,
    facts.cargoText,
    facts.goModText
  ].join('\n');

  addRiskIf(risks, /\b(TODO|FIXME|TBD|WIP)\b/i.test(haystack), 'placeholder-notes', 'Repo text still contains TODO/FIXME/TBD/WIP markers.');
  addRiskIf(risks, /\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b/i.test(haystack), 'local-url', 'Repo text references local development URLs.');
  addRiskIf(risks, /\b(example\.com|your[-_ ]?(project|repo|name)|replace[-_ ]?(me|with)|lorem ipsum)\b/i.test(haystack), 'template-placeholder', 'Repo text still contains template placeholders.');
  addRiskIf(risks, !facts.readmePath, 'missing-readme', 'No root README was found.');
  addRiskIf(risks, installCommands(facts.readmeText).length === 0, 'missing-install', 'No copy-paste install command was found.');
  addRiskIf(risks, visualReferences(facts.readmeText).length === 0, 'missing-visual', 'No README visual, GIF, screenshot, or video was found.');
  addRiskIf(risks, facts.topics.length < 3, 'few-topics', 'Fewer than 3 topic or keyword signals were found.');
  addRiskIf(risks, !hasRootFile(facts.files, /^(license|licence)(\.(md|txt))?$/i) && !facts.packageJson?.license && !facts.metadata?.license, 'missing-license', 'No obvious license signal was found.');

  return risks;
}

function addRiskIf(risks, condition, id, message) {
  if (condition) risks.push({ id, message });
}

function readmeHeadings(markdown) {
  if (!markdown) return [];
  return markdown
    .split('\n')
    .map((line) => line.match(/^(#{1,4})\s+(.+)$/))
    .filter(Boolean)
    .map((match) => ({
      level: match[1].length,
      text: stripMarkdown(match[2])
    }));
}

function visualReferences(markdown) {
  if (!markdown) return [];
  const matches = markdown.matchAll(/!\[([^\]]*)]\(([^)]+)\)|<img\b[^>]*>|<video\b[^>]*>|https?:\/\/[^\s)]+(?:youtu\.be|youtube\.com|asciinema\.org)[^\s)]*/gi);
  return [...matches].map((match) => compactSnippet(match[0], 180));
}

function extractImageUrls(markdown) {
  if (!markdown) return [];
  const urls = [];

  for (const match of markdown.matchAll(/!\[[^\]]*]\(([^)]+)\)/g)) {
    const candidate = normalizeImageUrl(match[1]);
    if (candidate) urls.push(candidate);
  }

  for (const match of markdown.matchAll(/<img\b[^>]*\bsrc=["']([^"']+)["']/gi)) {
    const candidate = normalizeImageUrl(match[1]);
    if (candidate) urls.push(candidate);
  }

  return [...new Set(urls)];
}

function normalizeImageUrl(rawValue) {
  const raw = String(rawValue ?? '').trim().split(/\s/)[0];
  if (!/^https?:\/\//i.test(raw)) return null;
  if (/\.(png|jpe?g|webp|gif|svg)(?:[?#]|$)/i.test(raw)) return raw;
  if (/githubusercontent\.com|modelscope\.|aliyuncs\.com|shields\.io|img\.shields/i.test(raw)) return raw;
  return null;
}

function packageScripts(packageJson) {
  if (!packageJson?.scripts || typeof packageJson.scripts !== 'object') return {};
  const entries = Object.entries(packageJson.scripts).slice(0, 8);
  return Object.fromEntries(entries);
}

function bestInstallCommand(facts) {
  const commands = installCommands(facts.readmeText);
  if (commands.length > 0) {
    return commands.reduce((best, command) => (command.length < best.length ? command : best), commands[0]);
  }

  if (facts.packageJson?.name && facts.packageJson?.bin) {
    return `npx ${facts.packageJson.name}`;
  }

  return '';
}

function packageRepositoryUrl(packageJson) {
  if (!packageJson?.repository) return '';
  if (typeof packageJson.repository === 'string') return packageJson.repository;
  return packageJson.repository.url ?? '';
}

function normalizeRepositoryUrl(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  if (/^git@github\.com:/i.test(raw)) {
    return raw.replace(/^git@github\.com:/i, 'https://github.com/').replace(/\.git$/i, '');
  }
  return raw.replace(/^git\+/i, '').replace(/\.git$/i, '');
}

function checkReadmePitch(facts) {
  const check = createCheck(CHECKS.readmePitch);

  if (!facts.readmeText) {
    check.summary = 'No root README found';
    check.findings.push(finding('high', 'Add a root README with a plain-language pitch.', 'Start with a H1 and one sentence that says who it is for, what it does, and why it is different.'));
    return check;
  }

  const title = firstHeading(facts.readmeText);
  const opening = openingParagraph(facts.readmeText);
  const words = wordCount(opening);
  const generic = /\b(simple|tiny|lightweight|awesome|easy-to-use)\b/i.test(opening) && words < 12;
  const outcome = /\b(for|to|helps?|lets?|so you|without|with|build|scan|generate|deploy|monitor|test|debug|analy[sz]e|convert|ship|automate)\b/i.test(opening);
  let score = 0;

  if (title) score += 3;
  else check.findings.push(finding('medium', 'The README does not start with a clear H1 title.', 'Add a product-style H1 before badges or setup details.'));

  if (opening) score += 4;
  else check.findings.push(finding('high', 'The README opening does not contain a usable one-sentence pitch.', 'Put a concise value proposition directly below the title.'));

  if (words >= 8 && words <= 35) score += 4;
  else if (words > 0) {
    score += 2;
    check.findings.push(finding('medium', 'The first README sentence is not sized like a launch pitch.', 'Rewrite it as one sentence of roughly 8-35 words.'));
  }

  if (outcome) score += 3;
  else check.findings.push(finding('medium', 'The opening sentence does not clearly say the outcome for the user.', 'Use language like "Scan X to find Y" or "Helps Z do W without V".'));

  if (!generic && opening) score += 2;
  else check.findings.push(finding('low', 'The opening sounds generic.', 'Replace generic adjectives with the specific repo category, user, and result.'));

  check.score = Math.min(check.max, score);
  check.summary = opening ? trimForSummary(opening) : 'README exists, but the pitch is weak';
  return check;
}

function checkVisualDemo(facts) {
  const check = createCheck(CHECKS.visualDemo);
  const readme = facts.readmeText;

  if (!readme) {
    check.summary = 'No README visuals';
    check.findings.push(finding('medium', 'There is no GIF, screenshot, or video in the README.', 'Add a short GIF or screenshot above the install section.'));
    return check;
  }

  const hasGifOrVideo = /!\[[^\]]*]\([^)]*\.(gif)(?:[?#][^)]*)?\)|<video\b|youtu\.be|youtube\.com|asciinema\.org|terminalizer|vhs/i.test(readme);
  const imageMatch = readme.match(/!\[[^\]]*]\([^)]*\.(png|jpe?g|webp|svg)(?:[?#][^)]*)?\)|<img\b/i);
  const firstVisualIndex = imageMatch?.index ?? Infinity;

  if (hasGifOrVideo) {
    check.score = 12;
    check.summary = 'README includes a GIF or video demo';
  } else if (imageMatch && firstVisualIndex < 2_000) {
    check.score = 8;
    check.summary = 'README has an early static visual';
    check.findings.push(finding('low', 'The README has a screenshot but no motion demo.', 'Use a 5-10 second GIF or terminal recording to show the core workflow.'));
  } else if (imageMatch) {
    check.score = 6;
    check.summary = 'README has a visual, but it appears late';
    check.findings.push(finding('medium', 'The README visual is buried too far down.', 'Move the best screenshot or GIF into the first screen.'));
  } else {
    check.summary = 'No visual proof in README';
    check.findings.push(finding('medium', 'There is no GIF, screenshot, or video in the README.', 'Add a short GIF or screenshot above the install section.'));
  }

  return check;
}

function checkInstallCommand(facts) {
  const check = createCheck(CHECKS.install);
  const commands = installCommands(facts.readmeText);

  if (commands.length === 0) {
    check.summary = 'No obvious install command';
    check.findings.push(finding('high', 'The README does not show a copy-paste install command.', 'Add one short install command such as `npx ...`, `pip install ...`, or `brew install ...`.'));
    return check;
  }

  const shortest = commands.reduce((best, command) => (command.length < best.length ? command : best), commands[0]);
  if (shortest.length <= 60) check.score = 12;
  else if (shortest.length <= 90) check.score = 10;
  else if (shortest.length <= 130) check.score = 7;
  else check.score = 4;

  check.summary = `Shortest install command is ${shortest.length} chars`;

  if (shortest.length > 90) {
    check.findings.push(finding('medium', 'The shortest install command is long enough to create friction.', 'Offer a shorter quickstart path before advanced install options.'));
  }

  if (!appearsEarly(facts.readmeText, shortest, 2_000)) {
    check.score = Math.max(0, check.score - 2);
    check.findings.push(finding('medium', 'The install command appears too late in the README.', 'Move the primary install command into the first screen or Quickstart section.'));
  }

  return check;
}

function checkDemoUsage(facts) {
  const check = createCheck(CHECKS.demoUsage);
  const readme = facts.readmeText;
  const lower = readme.toLowerCase();
  const hasSection = /^#{2,4}\s+.*\b(usage|quick ?start|demo|examples?|getting started)\b/im.test(readme);
  const hasCode = codeBlockCount(readme) > 0;
  const hasLiveDemo = /https?:\/\/[^\s)]+(demo|docs|github\.io|vercel\.app|netlify\.app|stackblitz|codesandbox|playground)/i.test(readme);
  const hasDemoWord = /\b(demo|playground|try it|live)\b/i.test(readme);
  const hasExampleDir = topLevelDir(facts.files, /^(examples?|samples?|demos?|playground)$/i);

  let score = 0;
  if (hasSection) score += 4;
  if (hasCode) score += 3;
  if (hasLiveDemo || (hasDemoWord && checkVisualSignal(readme))) score += 3;
  if (hasExampleDir) score += 2;

  check.score = score;
  check.summary = score >= 9 ? 'Usage path is visible' : 'Usage path needs more proof';

  if (!hasSection) {
    check.findings.push(finding('high', 'The README lacks a clear Usage, Demo, or Quickstart section.', 'Add a section that shows the first successful run from install to output.'));
  }
  if (!hasCode) {
    check.findings.push(finding('medium', 'The README does not include a runnable usage snippet.', 'Show the exact command or minimal code needed to see value.'));
  }
  if (!hasLiveDemo && !lower.includes('demo')) {
    check.findings.push(finding('low', 'There is no obvious demo link or demo section.', 'Link to a live demo, recorded demo, or generated output example.'));
  }

  return check;
}

function checkTopics(facts) {
  const check = createCheck(CHECKS.topics);
  const count = facts.topics.length;

  if (count >= 5) check.score = 10;
  else if (count >= 3) check.score = 8;
  else if (count >= 1) check.score = 5;

  check.summary = count > 0 ? `${count} topic/keyword signals` : 'No topic or keyword signals';

  if (count < 3) {
    check.findings.push(finding('medium', 'The repo has too few discoverability topics or package keywords.', 'Add 3-5 precise GitHub topics and package keywords that match the category users search for.'));
  }

  return check;
}

function checkExamples(facts) {
  const check = createCheck(CHECKS.examples);
  const exampleDir = topLevelDir(facts.files, /^(examples?|samples?|demos?|playground|templates)$/i);
  const exampleFiles = facts.files.filter((file) => /^(examples?|samples?|demos?|playground|templates)\//i.test(normalizePath(file)));
  const blocks = codeBlockCount(facts.readmeText);

  if (exampleDir) check.score += 5;
  if (exampleFiles.length >= 2) check.score += 2;
  if (blocks >= 2) check.score += 3;
  else if (blocks === 1) check.score += 1;

  check.score = Math.min(check.max, check.score);
  check.summary = exampleDir ? `${exampleFiles.length} example file(s)` : `${blocks} README code block(s), no examples dir`;

  if (!exampleDir && blocks < 2) {
    check.findings.push(finding('medium', 'There are not enough examples for a visitor to copy.', 'Add an `examples/` directory or at least two README examples for common use cases.'));
  } else if (!exampleDir) {
    check.findings.push(finding('low', 'The repo has README examples but no examples directory.', 'Add an `examples/` directory for users who want to clone and run something real.'));
  }

  return check;
}

function checkFirstScreen(facts) {
  const check = createCheck(CHECKS.firstScreen);

  if (!facts.readmeText) {
    check.summary = 'No README first screen';
    check.findings.push(finding('high', 'The repo has no README first screen to convert visitors.', 'Add a root README with title, pitch, visual, install, and first result.'));
    return check;
  }

  const first = facts.readmeText.slice(0, 1_500);
  const opening = openingParagraph(first);
  const hasTitle = /^#\s+\S+/m.test(first.slice(0, 300));
  const hasVisual = checkVisualSignal(first);
  const hasInstallOrUsage = installCommands(first).length > 0 || /\b(usage|quick ?start|demo)\b/i.test(first);
  const badgesDominate = badgeDominance(first);

  if (hasTitle) check.score += 2;
  if (opening && wordCount(opening) >= 8) check.score += 3;
  if (hasVisual) check.score += 3;
  if (hasInstallOrUsage) check.score += 3;
  if (!badgesDominate) check.score += 1;

  check.summary = check.score >= 9 ? 'First screen has the core launch signals' : 'First screen is missing conversion signals';

  if (!hasVisual) {
    check.findings.push(finding('medium', 'The README first screen has no visual proof.', 'Move a GIF, screenshot, or output image above deeper documentation.'));
  }
  if (!hasInstallOrUsage) {
    check.findings.push(finding('medium', 'The README first screen does not show how to try the project.', 'Put install plus first run in the opening viewport.'));
  }
  if (badgesDominate) {
    check.findings.push(finding('low', 'Badges dominate the first screen before the product value is clear.', 'Move nonessential badges below the pitch and demo.'));
  }

  return check;
}

function checkPackageRelease(facts) {
  const check = createCheck(CHECKS.packageRelease);
  const manifest = manifestInfo(facts);
  const hasLicense = hasRootFile(facts.files, /^(license|licence)(\.(md|txt))?$/i) || Boolean(facts.metadata?.license) || Boolean(manifest.license);
  const hasChangelog = hasRootFile(facts.files, /^changelog(\.(md|txt))?$/i) || hasRootFile(facts.files, /^releases?(\.(md|txt))?$/i);
  const hasRelease = facts.tags.length > 0 || Boolean(facts.metadata?.latest_release) || hasChangelog;

  if (hasLicense) check.score += 3;
  if (manifest.hasIdentity) check.score += 5;
  else if (manifest.exists) check.score += 2;
  if (manifest.hasEntrypoint) check.score += 3;
  if (hasRelease) check.score += 3;
  if (manifest.hasRepositoryLink) check.score += 2;

  check.summary = manifest.exists ? `${manifest.type} manifest found` : 'No package manifest found';

  if (!manifest.exists) {
    check.findings.push(finding('high', 'No package manifest was found.', 'Add package metadata for the ecosystem you publish to, including name, version, description, license, and entrypoint.'));
  } else if (!manifest.hasIdentity) {
    check.findings.push(finding('medium', 'The package manifest is missing launch metadata.', 'Fill in name, version, description, and license fields.'));
  }
  if (!manifest.hasEntrypoint) {
    check.findings.push(finding('medium', 'The package does not expose an obvious runnable entrypoint.', 'Add a CLI bin, main/module export, console script, or documented binary entrypoint.'));
  }
  if (!hasRelease) {
    check.findings.push(finding('low', 'There is no release signal such as tags, changelog, or GitHub release.', 'Create a first tagged release and add a short changelog.'));
  }
  if (!hasLicense) {
    check.findings.push(finding('medium', 'No license signal was found.', 'Add a LICENSE file and matching manifest license field.'));
  }

  return check;
}

function createCheck(template) {
  return {
    id: template.id,
    label: template.label,
    max: template.max,
    score: 0,
    summary: '',
    findings: []
  };
}

function finding(severity, message, fix) {
  return { severity, message, fix };
}

function parseGitHubRepo(value) {
  const sshMatch = value.match(/^git@github\.com:([^/\s]+)\/([^/\s]+?)(?:\.git)?$/i);
  if (sshMatch) {
    const owner = sshMatch[1];
    const repo = sshMatch[2];
    return {
      owner,
      repo,
      cloneUrl: `https://github.com/${owner}/${repo}.git`,
      webUrl: `https://github.com/${owner}/${repo}`
    };
  }

  let url;
  try {
    url = new URL(value);
  } catch {
    return null;
  }

  if (!/^github\.com$/i.test(url.hostname)) return null;
  const [owner, rawRepo] = url.pathname.split('/').filter(Boolean);
  if (!owner || !rawRepo) return null;
  const repo = rawRepo.replace(/\.git$/i, '');
  return {
    owner,
    repo,
    cloneUrl: `https://github.com/${owner}/${repo}.git`,
    webUrl: `https://github.com/${owner}/${repo}`
  };
}

async function fetchGitHubMetadata(owner, repo) {
  const headers = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'source2launch'
  };
  if (process.env.GITHUB_TOKEN) {
    headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  }

  const repoResponse = await fetch(`https://api.github.com/repos/${owner}/${repo}`, { headers }).catch(() => null);
  if (!repoResponse?.ok) return null;
  const repoJson = await repoResponse.json();
  const releaseResponse = await fetch(`https://api.github.com/repos/${owner}/${repo}/releases/latest`, { headers }).catch(() => null);
  const releaseJson = releaseResponse?.ok ? await releaseResponse.json() : null;

  return {
    full_name: repoJson.full_name ?? `${owner}/${repo}`,
    html_url: repoJson.html_url ?? `https://github.com/${owner}/${repo}`,
    name: repoJson.name ?? repo,
    description: repoJson.description ?? '',
    homepage: repoJson.homepage ?? '',
    license: repoJson.license?.spdx_id ?? null,
    stargazers_count: repoJson.stargazers_count ?? null,
    topics: Array.isArray(repoJson.topics) ? repoJson.topics : [],
    latest_release: releaseJson?.tag_name ?? null
  };
}

async function walk(root, options = {}) {
  const maxDepth = options.maxDepth ?? 6;
  const maxFiles = options.maxFiles ?? 2_000;
  const files = [];

  async function visit(directory, depth) {
    if (depth > maxDepth || files.length >= maxFiles) return;

    const entries = await fs.readdir(directory, { withFileTypes: true }).catch(() => []);
    entries.sort((left, right) => left.name.localeCompare(right.name));

    for (const entry of entries) {
      if (files.length >= maxFiles) break;
      const absolute = path.join(directory, entry.name);
      const relative = normalizePath(path.relative(root, absolute));

      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name)) await visit(absolute, depth + 1);
      } else if (entry.isFile()) {
        files.push(relative);
      }
    }
  }

  await visit(root, 0);
  return files;
}

function findRootFile(files, pattern) {
  return files.find((file) => !normalizePath(file).includes('/') && pattern.test(path.basename(file))) ?? null;
}

function hasRootFile(files, pattern) {
  return Boolean(findRootFile(files, pattern));
}

async function readText(filePath) {
  const text = await fs.readFile(filePath, 'utf8').catch(() => '');
  return text.slice(0, 250_000);
}

async function readJson(filePath) {
  try {
    return JSON.parse(await readText(filePath));
  } catch {
    return null;
  }
}

async function gitTags(root) {
  try {
    const { stdout } = await execFile('git', ['-C', root, 'tag', '--list'], {
      maxBuffer: 1024 * 1024,
      timeout: 5_000
    });
    return stdout.split('\n').map((tag) => tag.trim()).filter(Boolean);
  } catch {
    return [];
  }
}

function firstHeading(markdown) {
  const match = markdown.match(/^#\s+(.+)$/m);
  return match ? stripMarkdown(match[1]).trim() : '';
}

function openingParagraph(markdown) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const paragraph = [];
  let inFence = false;
  let consumedHeading = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (/^```|^~~~/.test(trimmed)) {
      inFence = !inFence;
      continue;
    }
    if (inFence || !trimmed) {
      if (paragraph.length > 0) break;
      continue;
    }
    if (/^<!--/.test(trimmed)) continue;
    if (/^#\s+/.test(trimmed) && !consumedHeading) {
      consumedHeading = true;
      continue;
    }
    if (/^>\s?/.test(trimmed)) continue;
    if (/^[-*_]{3,}$/.test(trimmed)) continue;
    if (isBadgeOrImageOnly(trimmed)) continue;
    paragraph.push(trimmed);
  }

  return stripMarkdown(paragraph.join(' ')).replace(/\s+/g, ' ').trim();
}

function isBadgeOrImageOnly(line) {
  if (/shields\.io|badge|badgen\.net|img\.shields/i.test(line)) return true;
  const withoutImages = line.replace(/!\[[^\]]*]\([^)]+\)/g, '').trim();
  return withoutImages.length === 0;
}

function stripMarkdown(value) {
  return value
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/~~~[\s\S]*?~~~/g, ' ')
    .replace(/!\[([^\]]*)]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)]\([^)]+\)/g, '$1')
    .replace(/[`*>#|~]/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function wordCount(value) {
  if (!value) return 0;
  const latin = value.match(/[A-Za-z0-9]+(?:'[A-Za-z]+)?/g) ?? [];
  const cjk = value.match(/[\u4e00-\u9fff\u3400-\u4dbf]/g) ?? [];
  const mixed = latin.length + cjk.length;
  if (mixed > 0) return mixed;
  return value.split(/\s+/).filter(Boolean).length;
}

function codeBlockCount(markdown) {
  return (markdown.match(/```[\s\S]*?```/g) ?? []).length + (markdown.match(/~~~[\s\S]*?~~~/g) ?? []).length;
}

function installCommands(markdown) {
  if (!markdown) return [];
  const candidates = [];
  const codeBlocks = markdown.match(/```[\s\S]*?```|~~~[\s\S]*?~~~/g) ?? [];
  for (const block of codeBlocks) {
    for (const line of block.split('\n')) {
      candidates.push(cleanCommand(line));
    }
  }

  const inlineMatches = markdown.match(/`([^`\n]*(?:npm|pnpm|yarn|npx|pip|pipx|uv|brew|go install|cargo install|docker run|gem install)[^`\n]*)`/gi) ?? [];
  for (const match of inlineMatches) {
    candidates.push(cleanCommand(match.replace(/^`|`$/g, '')));
  }

  for (const line of markdown.split('\n')) {
    candidates.push(cleanCommand(line));
  }

  return uniqueStrings(candidates.filter((command) => isInstallCommand(command) && command.length <= 300));
}

function stripCodeBlocks(markdown) {
  return String(markdown ?? '').replace(/```[\s\S]*?```/g, '').replace(/~~~[\s\S]*?~~~/g, '');
}

function cleanCommand(line) {
  return stripMarkdown(line)
    .replace(/^\s*(\$|>|❯|#)\s*/, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function isInstallCommand(command) {
  return [
    /\b(npm|pnpm|yarn)\s+(i|install|add|create)\b/i,
    /\bnpx\s+[@\w./-]+/i,
    /\bpipx?\s+install\b/i,
    /\buv\s+(tool\s+install|add|pip\s+install)\b/i,
    /\bbrew\s+install\b/i,
    /\bgo\s+install\b/i,
    /\bcargo\s+install\b/i,
    /\bdocker\s+run\b/i,
    /\bgem\s+install\b/i
  ].some((pattern) => pattern.test(command));
}

function appearsEarly(haystack, needle, limit) {
  const index = haystack.indexOf(needle);
  return index >= 0 && index <= limit;
}

function checkVisualSignal(markdown) {
  return /!\[[^\]]*]\([^)]*\.(gif|png|jpe?g|webp|svg)(?:[?#][^)]*)?\)|<img\b|<video\b|youtu\.be|youtube\.com|asciinema\.org/i.test(markdown);
}

function topLevelDir(files, pattern) {
  return files.some((file) => {
    const [first] = normalizePath(file).split('/');
    return pattern.test(first);
  });
}

function badgeDominance(markdown) {
  const firstLines = markdown.split('\n').slice(0, 12);
  const badgeLines = firstLines.filter((line) => /shields\.io|badge|badgen\.net|img\.shields/i.test(line)).length;
  const plainWords = wordCount(stripMarkdown(firstLines.filter((line) => !isBadgeOrImageOnly(line.trim())).join(' ')));
  return badgeLines >= 3 && plainWords < 25;
}

function manifestInfo(facts) {
  if (facts.packageJson) {
    return {
      type: 'package.json',
      exists: true,
      hasIdentity: Boolean(facts.packageJson.name && facts.packageJson.version && facts.packageJson.description),
      hasEntrypoint: Boolean(facts.packageJson.bin || facts.packageJson.main || facts.packageJson.module || facts.packageJson.exports),
      hasRepositoryLink: Boolean(facts.packageJson.repository || facts.packageJson.homepage || facts.packageJson.bugs),
      license: facts.packageJson.license
    };
  }

  if (facts.pyprojectText) {
    return {
      type: 'pyproject.toml',
      exists: true,
      hasIdentity: /name\s*=/.test(facts.pyprojectText) && /version\s*=/.test(facts.pyprojectText) && /description\s*=/.test(facts.pyprojectText),
      hasEntrypoint: /\[project\.scripts]|\[tool\.poetry\.scripts]/.test(facts.pyprojectText),
      hasRepositoryLink: /Homepage|Repository|repository|homepage/.test(facts.pyprojectText),
      license: /license\s*=/.test(facts.pyprojectText)
    };
  }

  if (facts.cargoText) {
    return {
      type: 'Cargo.toml',
      exists: true,
      hasIdentity: /name\s*=/.test(facts.cargoText) && /version\s*=/.test(facts.cargoText) && /description\s*=/.test(facts.cargoText),
      hasEntrypoint: true,
      hasRepositoryLink: /repository\s*=|homepage\s*=/.test(facts.cargoText),
      license: /license\s*=/.test(facts.cargoText)
    };
  }

  if (facts.goModText) {
    return {
      type: 'go.mod',
      exists: true,
      hasIdentity: /module\s+\S+/.test(facts.goModText),
      hasEntrypoint: facts.files.some((file) => /^cmd\//.test(normalizePath(file))) || facts.files.includes('main.go'),
      hasRepositoryLink: /github\.com\//.test(facts.goModText),
      license: null
    };
  }

  return {
    type: null,
    exists: false,
    hasIdentity: false,
    hasEntrypoint: false,
    hasRepositoryLink: false,
    license: null
  };
}

function trimForSummary(value) {
  if (value.length <= 96) return value;
  return `${value.slice(0, 93).trim()}...`;
}

function compactSnippet(value, maxLength) {
  const normalized = String(value ?? '').replace(/\s+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength - 3).trim()}...`;
}

function uniqueStrings(values) {
  return [...new Set(values.map((value) => String(value).trim()).filter(Boolean))];
}

function firstPresent(values) {
  return values.map((value) => String(value ?? '').trim()).find(Boolean) ?? '';
}

function normalizePath(value) {
  return value.split(path.sep).join('/');
}

function grade(score) {
  if (score >= 85) return 'A';
  if (score >= 70) return 'B';
  if (score >= 55) return 'C';
  if (score >= 40) return 'D';
  return 'F';
}
