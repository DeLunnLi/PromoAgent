const PLATFORM_FILES = {
  xhs: 'platform/xhs.md',
  zhihu: 'platform/zhihu.md',
  wechat: 'platform/wechat.md',
  showHn: 'platform/show-hn.md',
  productHunt: 'platform/producthunt-kit.md'
};

export function buildCampaign(result, manifest, context = {}) {
  const project = result.project ?? {};
  const aiContent = context.aiPromoContent ?? null;
  const projectIntake = context.projectIntake ?? null;
  const launchPack = context.launchPack ?? null;

  return {
    version: '0.2',
    status: aiContent ? 'review_required' : 'needs_model_config',
    project: {
      name: project.name,
      description: project.description,
      repositoryUrl: project.repositoryUrl,
      installCommand: project.installCommand,
      topics: project.topics ?? []
    },
    source: {
      summarySource: manifest.summarySource ?? projectIntake?.summarySource ?? 'local',
      summaryModel: manifest.summaryModel ?? projectIntake?.aiModel ?? null,
      hasPdfContext: Boolean(context.hasPdfContext),
      hasDocContext: Boolean(context.hasDocContext)
    },
    generation: {
      promoSource: manifest.promoSource,
      promoModel: manifest.promoModel ?? null,
      imageStatus: imageStatus(manifest),
      mode: manifest.mode,
      skipped: [...manifest.skipped]
    },
    files: {
      index: 'INDEX.md',
      sourceSummary: 'project-summary.md',
      contentReview: 'content-review.md',
      promoCopy: 'promo-copy.md',
      platforms: PLATFORM_FILES,
      images: manifest.images
    },
    reviewGate: buildReviewGate(result, manifest, aiContent, launchPack),
    publish: {
      defaultMode: 'review',
      execution: 'not_executed',
      note: 'Generated content must be reviewed by a human before platform API calls or browser-assisted filling.'
    },
    generatedFiles: [...manifest.generated]
  };
}

export function formatContentReview(result, manifest, context = {}) {
  const aiContent = context.aiPromoContent ?? null;
  const launchPack = context.launchPack ?? null;
  const reviewGate = buildReviewGate(result, manifest, aiContent, launchPack);
  const lines = [];

  lines.push(`# ${result.project.name} · 内容审核清单`);
  lines.push('');
  lines.push('> 由 Source2Launch 自动生成。发布前请人工确认，不代表平台已发布。');
  lines.push('');
  lines.push(`状态：**${reviewGate.status === 'ready_for_review' ? '待人工审核' : '需要补充配置'}**`);
  lines.push('');

  lines.push('## 必查事实');
  lines.push('');
  for (const item of reviewGate.mustVerify) {
    lines.push(`- [ ] ${item}`);
  }

  lines.push('');
  lines.push('## 三轴审核');
  lines.push('');
  appendRubricAxis(lines, reviewGate.qualityRubric.fidelity);
  appendRubricAxis(lines, reviewGate.qualityRubric.engagement);
  appendRubricAxis(lines, reviewGate.qualityRubric.alignment);

  lines.push('');
  lines.push('## 平台草稿');
  lines.push('');
  for (const platform of reviewGate.platforms) {
    lines.push(`- [${platform.ready ? 'x' : ' '}] ${platform.label}：${platform.file}${platform.note ? ` — ${platform.note}` : ''}`);
  }

  lines.push('');
  lines.push('## 风险提示');
  lines.push('');
  for (const item of reviewGate.risks) {
    lines.push(`- ${item}`);
  }

  if (Array.isArray(launchPack?.checklist) && launchPack.checklist.length > 0) {
    lines.push('');
    lines.push('## 发布前清单');
    lines.push('');
    for (const item of launchPack.checklist.slice(0, 8)) {
      lines.push(`- [ ] ${item}`);
    }
  }

  lines.push('');
  lines.push('## 下一步');
  lines.push('');
  if (aiContent) {
    lines.push('1. 逐个平台检查 `platform/` 中的草稿。');
    lines.push('2. 删除无法从 README、论文、截图、命令或代码中验证的表述。');
    lines.push('3. 确认图片、链接、标签和账号后，再运行 `source2launch publish promotion.json --publish-mode review` 生成发布计划。');
  } else {
    lines.push('1. 配置 `SOURCE2LAUNCH_MODELSCOPE_API_KEY` 或 `SOURCE2LAUNCH_API_KEY`。');
    lines.push('2. 重新运行 `source2launch optimize . --output launch-assets/`。');
    lines.push('3. 再审核平台文案、配图和发布计划。');
  }

  return lines.join('\n');
}

function appendRubricAxis(lines, axis) {
  lines.push(`### ${axis.label}`);
  lines.push('');
  for (const item of axis.checks) lines.push(`- [ ] ${item}`);
  if (axis.risks.length > 0) {
    lines.push('');
    lines.push(`风险：${axis.risks.join('；')}`);
  }
  if (axis.improvements.length > 0) {
    lines.push(`改进：${axis.improvements.join('；')}`);
  }
  lines.push('');
}

export function formatShowHnDraft(result, promotions = {}, launchPack = null) {
  const showHn = promotions.showHn ?? {};
  if (showHn.markdown) return showHn.markdown.trim();

  const pack = launchPack?.showHn;
  const lines = [];
  lines.push(`# ${result.project.name} · Show HN`);
  lines.push('');
  lines.push('> 发布前请确认标题、仓库链接和演示路径。');
  lines.push('');
  if (showHn.title || pack?.title) lines.push(`**Title:** ${showHn.title || pack.title}`);
  lines.push('');
  lines.push(showHn.body || pack?.body || '配置 API Key 后重新生成 Show HN 草稿。');
  return lines.join('\n');
}

export function formatProductHuntKit(result, promotions = {}, launchPack = null) {
  const productHunt = promotions.productHunt ?? {};
  if (productHunt.markdown) return productHunt.markdown.trim();

  const pack = launchPack?.productHunt;
  const lines = [];
  lines.push(`# ${result.project.name} · Product Hunt Kit`);
  lines.push('');
  lines.push('> 结构化 launch 草稿。提交前请按 Product Hunt 页面逐项复制并人工确认。');
  lines.push('');
  lines.push('## Name');
  lines.push(result.project.name);
  lines.push('');
  lines.push('## Tagline');
  lines.push(productHunt.tagline || pack?.tagline || result.project.description || '配置 API Key 后重新生成 tagline。');
  lines.push('');
  lines.push('## First Comment');
  lines.push('');
  lines.push(productHunt.firstComment || productHunt.body || pack?.firstComment || '配置 API Key 后重新生成 maker comment。');
  lines.push('');
  lines.push('## Gallery Plan');
  lines.push('');
  lines.push('- [ ] 封面图：展示真实输出或产品界面，不使用虚构数据。');
  lines.push('- [ ] 第二张：README / 论文关键图表 / 终端运行截图。');
  lines.push('- [ ] 第三张：生成的平台文案或 launch-assets 目录。');
  return lines.join('\n');
}

function buildReviewGate(result, manifest, aiContent, launchPack) {
  const project = result.project ?? {};
  const platforms = [
    platformStatus('小红书', PLATFORM_FILES.xhs, aiContent?.promotions?.xiaohongshu),
    platformStatus('知乎', PLATFORM_FILES.zhihu, aiContent?.promotions?.zhihu),
    platformStatus('微信', PLATFORM_FILES.wechat, aiContent?.promotions?.wechatMoments),
    platformStatus('Show HN', PLATFORM_FILES.showHn, aiContent?.promotions?.showHn || launchPack?.showHn),
    platformStatus('Product Hunt', PLATFORM_FILES.productHunt, aiContent?.promotions?.productHunt || launchPack?.productHunt)
  ];

  const mustVerify = [
    '安装命令、仓库链接、论文标题和作者信息必须来自输入证据。',
    '不得编造 star 数、用户数、benchmark、媒体报道、录用状态或实验结论。',
    '配图必须来自真实截图、论文图表、生成封面或明确标注的视觉草案。',
    '小红书/知乎/微信正文需要符合账号口吻，不要直接保留模型解释性文字。'
  ];
  if (project.installCommand) mustVerify.unshift(`安装命令是否仍为 \`${project.installCommand}\`。`);
  if (project.repositoryUrl) mustVerify.unshift(`仓库链接是否仍为 ${project.repositoryUrl}。`);

  const risks = [];
  if (!aiContent) risks.push('未配置 AI Key，平台文案为占位或本地模板，需要重新生成。');
  if (!manifest.images?.xhs && !manifest.images?.wechat) risks.push('未生成配图；小红书、微信、Product Hunt 发布前应补真实截图或生成封面。');
  if (Array.isArray(result.evidence?.launchRisks)) {
    for (const risk of result.evidence.launchRisks.slice(0, 4)) {
      risks.push(risk.message ?? String(risk));
    }
  }
  if (risks.length === 0) risks.push('未发现自动化层面的明显风险；仍需人工确认事实和平台语气。');

  return {
    status: aiContent ? 'ready_for_review' : 'needs_model_config',
    qualityRubric: buildQualityRubric(aiContent),
    mustVerify,
    platforms,
    risks
  };
}

function buildQualityRubric(aiContent) {
  const provided = aiContent?.promotionStrategy?.qualityRubric ?? {};
  return {
    fidelity: normalizeRubricAxis(provided.fidelity, {
      label: 'Fidelity',
      checks: [
        '核心 claim 是否能在 README、论文、截图、命令或代码里找到来源。',
        '标题、作者、仓库链接、安装命令、论文结论是否准确。',
        '没有编造 benchmark、用户数、star 增长、媒体报道或录用状态。'
      ],
      risks: ['来源证据不足时，模型可能把方法描述写成已验证结果。'],
      improvements: ['删掉无法核实的强结论，补充来源截图、论文页码、README 片段或运行命令。']
    }),
    engagement: normalizeRubricAxis(provided.engagement, {
      label: 'Engagement',
      checks: [
        '开头是否具体到一个读者场景，而不是泛泛介绍项目。',
        '读者是否能在前几行看到问题、价值和下一步动作。',
        'CTA 是否指向读论文、试命令、看仓库或查看图表。'
      ],
      risks: ['文案可能过于模板化，标题像广告而不是作者分享。'],
      improvements: ['保留一个具体痛点、一个证据和一个行动，删除空泛形容词。']
    }),
    alignment: normalizeRubricAxis(provided.alignment, {
      label: 'Alignment',
      checks: [
        '小红书、知乎、微信、Show HN、Product Hunt 是否使用不同结构。',
        '标签、标题长度、图片比例和语气是否适配对应平台。',
        '配图是否支撑正文 claim，而不是只做装饰。'
      ],
      risks: ['同一段文字跨平台复用会降低真实感和平台匹配度。'],
      improvements: ['按平台重写开头、段落节奏、标签和配图顺序。']
    })
  };
}

function normalizeRubricAxis(value, fallback) {
  return {
    label: value?.label ?? fallback.label,
    checks: normalizeStringList(value?.checks, fallback.checks),
    risks: normalizeStringList(value?.risks, fallback.risks),
    improvements: normalizeStringList(value?.improvements, fallback.improvements)
  };
}

function normalizeStringList(value, fallback) {
  const list = Array.isArray(value) ? value : value ? [value] : fallback;
  return list.map((item) => String(item).trim()).filter(Boolean).slice(0, 5);
}

function platformStatus(label, file, content) {
  const ready = hasPlatformContent(content);
  return {
    label,
    file,
    ready,
    note: ready ? '已生成草稿，待人工审核' : '未生成 AI 草稿'
  };
}

function hasPlatformContent(value) {
  if (!value) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  return Boolean(value.markdown || value.body || value.title || value.tagline || value.firstComment);
}

function imageStatus(manifest) {
  if (manifest.images?.xhs || manifest.images?.wechat) return 'generated';
  return 'not_generated';
}
