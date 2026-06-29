/**
 * 项目介绍文档生成器
 * 从项目理解和 AI 分析结果生成结构化的 PROJECT_INTRO.md
 */

/**
 * @typedef {Object} ProjectProfile
 * @property {string} name - 项目名称
 * @property {string} oneLiner - 一句话介绍
 * @property {string} overview - 项目概述
 * @property {string[]} targetUsers - 目标用户
 * @property {string[]} problems - 解决的问题
 * @property {string[]} solutions - 解决方案
 * @property {string[]} keyFeatures - 核心功能
 * @property {string[]} useCases - 使用场景
 * @property {string|null} installCommand - 安装命令
 * @property {string} quickstart - 快速开始
 * @property {string} howItWorks - 工作原理
 * @property {string[]} techStack - 技术栈
 * @property {string[]} projectStructure - 项目结构
 * @property {string[]} limitations - 当前限制
 * @property {string[]} roadmap - 后续路线建议
 */

/**
 * 从 AI 理解和本地证据构建 ProjectProfile
 * @param {Object} intake - 项目理解结果
 * @param {Object} result - 分析结果
 * @returns {ProjectProfile}
 */
export function buildProjectProfile(intake, result = {}) {
  const brief = intake.aiBrief?.projectBrief ?? {};
  const project = result.project ?? {};
  const evidence = result.evidence ?? {};

  return {
    name: project.name ?? brief.oneLiner?.split(' ')[0] ?? 'Project',
    oneLiner: brief.oneLiner ?? project.description ?? 'A CLI tool for project understanding.',
    overview: brief.overview ?? project.description ?? '',
    targetUsers: brief.targetUsers ?? [],
    problems: brief.problem ? [brief.problem] : [],
    solutions: brief.solution ? [brief.solution] : [],
    keyFeatures: extractKeyFeatures(brief, evidence),
    useCases: [],
    installCommand: project.installCommand ?? null,
    quickstart: brief.tryItNow ?? '',
    howItWorks: brief.howItWorks ?? '',
    techStack: extractTechStack(result),
    projectStructure: evidence.examplePaths?.slice(0, 8) ?? [],
    limitations: brief.honestLimits ?? [],
    roadmap: brief.starBlockers?.map(b => b.fix).filter(Boolean) ?? []
  };
}

/**
 * 格式化 PROJECT_INTRO.md 文档
 * @param {ProjectProfile} profile
 * @param {Object} meta - 元信息
 * @returns {string}
 */
export function formatProjectIntroMarkdown(profile, meta = {}) {
  const lines = [];

  // 标题
  lines.push(`# ${profile.name}`);
  lines.push('');

  // 元信息
  if (meta.source) {
    lines.push(`> 由 Source2Launch --intro 生成 · ${meta.source}${meta.model ? ` · ${meta.model}` : ''}`);
    lines.push('');
  }

  // 一句话介绍
  if (profile.oneLiner) {
    lines.push('## 一句话介绍');
    lines.push('');
    lines.push(profile.oneLiner);
    lines.push('');
  }

  // 项目概述
  if (profile.overview) {
    lines.push('## 解决的问题');
    lines.push('');
    lines.push(profile.overview);
    lines.push('');
  }

  // 目标用户
  if (profile.targetUsers.length > 0) {
    lines.push('## 目标用户');
    lines.push('');
    for (const user of profile.targetUsers) {
      lines.push(`- ${user}`);
    }
    lines.push('');
  }

  // 核心能力
  const features = profile.keyFeatures;
  if (features.length > 0) {
    lines.push('## 核心能力');
    lines.push('');
    for (const feature of features.slice(0, 6)) {
      lines.push(`- ${feature}`);
    }
    lines.push('');
  }

  // 使用场景
  if (profile.useCases.length > 0) {
    lines.push('## 使用场景');
    lines.push('');
    for (const useCase of profile.useCases) {
      lines.push(`- ${useCase}`);
    }
    lines.push('');
  }

  // 快速开始
  if (profile.installCommand || profile.quickstart) {
    lines.push('## 快速开始');
    lines.push('');

    if (profile.installCommand) {
      lines.push('### 安装');
      lines.push('');
      lines.push('```sh');
      lines.push(profile.installCommand);
      lines.push('```');
      lines.push('');
    }

    if (profile.quickstart) {
      lines.push('### 运行');
      lines.push('');
      lines.push(profile.quickstart);
      lines.push('');
    }
    lines.push('');
  }

  // 工作原理
  if (profile.howItWorks) {
    lines.push('## 工作原理');
    lines.push('');
    lines.push(profile.howItWorks);
    lines.push('');
  }

  // 技术栈
  if (profile.techStack.length > 0) {
    lines.push('## 技术栈');
    lines.push('');
    lines.push(profile.techStack.join(' · '));
    lines.push('');
  }

  // 项目结构
  if (profile.projectStructure.length > 0) {
    lines.push('## 项目结构');
    lines.push('');
    lines.push('```');
    for (const path of profile.projectStructure) {
      lines.push(path);
    }
    lines.push('```');
    lines.push('');
  }

  // 当前限制
  if (profile.limitations.length > 0) {
    lines.push('## 当前限制');
    lines.push('');
    for (const limitation of profile.limitations) {
      lines.push(`- ${limitation}`);
    }
    lines.push('');
  }

  // 后续路线
  if (profile.roadmap.length > 0) {
    lines.push('## 后续路线建议');
    lines.push('');
    for (const item of profile.roadmap.slice(0, 5)) {
      lines.push(`- ${item}`);
    }
    lines.push('');
  }

  // 生成提示
  lines.push('---');
  lines.push('');
  lines.push('*本文档由 [Source2Launch](https://github.com/DeLunnLi/star_up) 自动生成*');

  return lines.join('\n');
}

/**
 * 提取核心功能
 */
function extractKeyFeatures(brief, evidence) {
  const features = [];

  if (brief.differentiators) {
    features.push(...brief.differentiators);
  }

  // 从 packageScripts 推断功能
  const scripts = evidence.packageScripts ?? {};
  const scriptKeys = Object.keys(scripts).slice(0, 4);
  for (const key of scriptKeys) {
    if (!features.some(f => f.includes(key))) {
      features.push(`支持 ${key} 命令`);
    }
  }

  return features;
}

/**
 * 提取技术栈
 */
function extractTechStack(result) {
  const stack = [];
  const facts = result;

  if (facts.packageJson) stack.push('Node.js');
  if (facts.pyprojectText) stack.push('Python');
  if (facts.cargoText) stack.push('Rust');
  if (facts.goModText) stack.push('Go');

  // 从 README 推断
  const readme = facts.evidence?.readmeFirstScreen ?? '';
  if (/python|py/i.test(readme)) stack.push('Python');
  if (/typescript|ts/i.test(readme)) stack.push('TypeScript');
  if (/rust|cargo/i.test(readme)) stack.push('Rust');
  if (/go\s+module|golang/i.test(readme)) stack.push('Go');

  return [...new Set(stack)];
}

/**
 * 格式化 CLI 输出（无文件写入）
 * @param {Object} intake
 * @param {Object} result
 * @returns {string}
 */
export function formatIntroCliOutput(intake, result) {
  const profile = buildProjectProfile(intake, result);
  const meta = {
    source: intake.summarySource === 'ai' ? '大模型生成' : '本地证据',
    model: intake.aiModel
  };

  return formatProjectIntroMarkdown(profile, meta);
}
