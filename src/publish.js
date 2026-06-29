const PLATFORM_LABELS = {
  twitter: 'X / Twitter',
  linkedin: 'LinkedIn',
  producthunt: 'Product Hunt',
  hackernews: 'Hacker News / Show HN',
  zhihu: 'Zhihu',
  xhs: 'Xiaohongshu',
  'wechat-official': 'WeChat Official Account',
  'wechat-moments': 'WeChat Moments'
};

const PLATFORM_DELIVERY = {
  twitter: {
    apiCapable: true,
    adapter: 'x-api',
    officialApi: 'POST /2/tweets',
    reviewNote: 'Verify text, link, media, and account before posting through the X API.'
  },
  linkedin: {
    apiCapable: true,
    adapter: 'linkedin-posts-api',
    officialApi: 'LinkedIn Posts API',
    reviewNote: 'Verify organization/person author, media assets, and link preview before publishing.'
  },
  producthunt: {
    apiCapable: false,
    adapter: 'manual-launch-review',
    officialApi: 'Product Hunt API access is limited for launch workflows.',
    reviewNote: 'Use this payload as launch-page copy and maker-comment draft; keep final submission manual.'
  },
  hackernews: {
    apiCapable: false,
    adapter: 'manual-show-hn',
    officialApi: 'No official posting API for Show HN.',
    reviewNote: 'Use this as a Show HN draft; submit manually from the logged-in account after checking guidelines.'
  },
  zhihu: {
    apiCapable: false,
    adapter: 'assist-fill',
    officialApi: 'No general public posting API for normal user answers.',
    reviewNote: 'Use browser-assisted filling only after user review; publish manually.'
  },
  xhs: {
    apiCapable: false,
    adapter: 'assist-fill',
    officialApi: 'No general public posting API for normal user notes.',
    reviewNote: 'Use browser-assisted filling only after user review; publish manually.'
  },
  'wechat-official': {
    apiCapable: true,
    adapter: 'wechat-official-api',
    officialApi: 'Draft and free-publish APIs',
    reviewNote: 'Verify title, cover, media IDs, article body, and account permissions before publishing.'
  },
  'wechat-moments': {
    apiCapable: false,
    adapter: 'manual-moments',
    officialApi: 'No public WeChat Moments publishing API.',
    reviewNote: 'Use this as a manual Moments draft.'
  }
};

const BROWSER_ASSIST_TARGETS = {
  twitter: {
    openUrl: 'https://x.com/compose/post',
    surface: 'Post composer'
  },
  linkedin: {
    openUrl: 'https://www.linkedin.com/feed/',
    surface: 'LinkedIn post composer'
  },
  producthunt: {
    openUrl: 'https://www.producthunt.com/launch',
    surface: 'Product Hunt launch flow'
  },
  hackernews: {
    openUrl: 'https://news.ycombinator.com/submit',
    surface: 'Hacker News submit page'
  },
  zhihu: {
    openUrl: 'https://www.zhihu.com/',
    surface: 'Zhihu answer/article composer'
  },
  xhs: {
    openUrl: 'https://creator.xiaohongshu.com/publish/publish',
    surface: 'Xiaohongshu creator publish page'
  },
  'wechat-official': {
    openUrl: 'https://mp.weixin.qq.com/',
    surface: 'WeChat Official Account draft editor'
  },
  'wechat-moments': {
    openUrl: 'weixin://',
    surface: 'WeChat Moments composer'
  }
};

const ALL_PLATFORMS = [
  'twitter',
  'linkedin',
  'producthunt',
  'hackernews',
  'zhihu',
  'xhs',
  'wechat-official',
  'wechat-moments'
];

export function buildPublishPlan(input, options = {}) {
  const content = normalizePromotionContent(input);
  const platformNames = normalizePublishPlatforms(options.platform ?? options.promo ?? 'all');
  const approved = Boolean(options.approved || options.yes);
  const publishMode = normalizePublishMode(options.publishMode);
  const media = normalizeList(options.media);
  const items = platformNames
    .map((platform) => buildPublishItem(content, platform, {
      approved,
      media,
      publishMode
    }))
    .filter(Boolean);

  return {
    version: '0.1',
    status: approved ? 'approved' : 'review_required',
    publishMode,
    approved,
    reviewRequired: !approved,
    execution: 'not_executed',
    note: approved
      ? 'Payloads are marked approved, but no platform API call has been executed by this preview plan.'
      : 'Review the payloads below. Add --yes only after a human has approved the content.',
    items
  };
}

export function formatPublishPlan(plan) {
  const lines = [];
  lines.push(`Publish plan (${plan.status})`);
  lines.push(`Mode: ${plan.publishMode}`);
  lines.push(`Approved: ${plan.approved ? 'yes' : 'no'}`);
  lines.push(`Execution: ${plan.execution}`);
  if (plan.note) lines.push(`Note: ${plan.note}`);

  for (const item of plan.items ?? []) {
    lines.push('');
    lines.push(`${item.label} [${item.status}]`);
    lines.push(`Adapter: ${item.delivery.adapter}`);
    lines.push(`Official API: ${item.delivery.officialApi}`);
    lines.push(`API capable: ${item.delivery.apiCapable ? 'yes' : 'no'}`);
    if (item.delivery.reviewNote) lines.push(`Review note: ${item.delivery.reviewNote}`);
    appendPayload(lines, item.payload);
    appendAssist(lines, item.browserAssist);
    appendChecklist(lines, item.reviewChecklist);
  }

  return lines.join('\n');
}

function buildPublishItem(content, platform, options) {
  const payload = platformPayload(content, platform, options);
  if (!payload) return null;
  const delivery = PLATFORM_DELIVERY[platform] ?? {
    apiCapable: false,
    adapter: 'manual',
    officialApi: 'Unknown',
    reviewNote: 'Review manually before publishing.'
  };
  const status = publishItemStatus(delivery, options);

  return {
    platform,
    label: PLATFORM_LABELS[platform] ?? platform,
    status,
    payload,
    delivery,
    ...(options.publishMode === 'assist' ? { browserAssist: browserAssistPlan(platform, payload) } : {}),
    reviewChecklist: reviewChecklistFor(platform, payload)
  };
}

function publishItemStatus(delivery, options) {
  if (!options.approved) return 'review_required';
  if (options.publishMode === 'api' && !delivery.apiCapable) return 'manual_review_required';
  if (options.publishMode === 'assist') return 'assist_ready';
  return 'approved';
}

function platformPayload(content, platform, options) {
  const variants = content.platformVariants ?? {};
  const promotions = content.promotions ?? {};
  const tweetPack = content.tweetPack ?? {};
  const visualPlan = content.visualPlan ?? {};
  const media = options.media;

  if (platform === 'twitter') {
    const post = variants.xTwitter ?? {};
    const twitter = promotions.twitter ?? {};
    return {
      text: post.post || tweetPack.singleTweet || twitter.markdown || '',
      thread: post.thread || tweetPack.thread || markdownToThread(twitter.markdown),
      hashtags: tweetPack.hashtags || [],
      media,
      imageIdeas: tweetPack.imageIdeas || []
    };
  }

  if (platform === 'linkedin') {
    const post = variants.linkedin ?? {};
    return {
      text: post.post || tweetPack.launchTweet || tweetPack.singleTweet || '',
      carouselOutline: post.carouselOutline || [],
      firstComment: post.commentPrompt || '',
      media,
      recommendedClips: visualPlan.recommendedClips || []
    };
  }

  if (platform === 'producthunt') {
    const post = variants.productHunt ?? {};
    const productHunt = promotions.productHunt ?? {};
    return {
      tagline: post.tagline || productHunt.tagline || '',
      description: post.description || productHunt.description || productHunt.markdown || '',
      makerComment: post.makerComment || productHunt.firstComment || '',
      launchChecklist: post.launchChecklist || [],
      media,
      recommendedClips: visualPlan.recommendedClips || []
    };
  }

  if (platform === 'hackernews') {
    const post = variants.hackerNews ?? {};
    const showHn = promotions.showHn ?? {};
    return {
      title: post.title || showHn.title || '',
      body: post.body || showHn.body || showHn.markdown || '',
      firstComment: post.firstComment || showHn.firstComment || '',
      riskNotes: post.riskNotes || []
    };
  }

  if (platform === 'zhihu') {
    const post = variants.zhihu ?? {};
    const zhihu = promotions.zhihu ?? {};
    return {
      title: post.title || zhihu.title || '',
      hook: post.hook || '',
      body: post.answer || zhihu.body || zhihu.markdown || '',
      outline: post.answerOutline || [],
      citationsToUse: post.citationsToUse || zhihu.suggestedQuestions || [],
      media
    };
  }

  if (platform === 'xhs') {
    const post = variants.xiaohongshu ?? {};
    const xhs = promotions.xiaohongshu ?? {};
    return {
      title: firstValue(post.titles) || firstValue(xhs.titles) || '',
      titleOptions: post.titles || xhs.titles || [],
      coverTexts: post.coverTexts || xhs.titles || [],
      body: post.body || xhs.body || xhs.markdown || '',
      carousel: post.carousel || [],
      tags: post.tags || xhs.tags || [],
      media
    };
  }

  if (platform === 'wechat-official') {
    const post = variants.wechatOfficial ?? {};
    const wechat = promotions.wechatOfficial ?? {};
    return {
      title: post.title || wechat.title || '',
      summary: post.summary || wechat.summary || '',
      coverText: post.coverText || '',
      sectionOutline: post.sectionOutline || [],
      body: post.body || wechat.body || wechat.markdown || '',
      media
    };
  }

  if (platform === 'wechat-moments') {
    const post = variants.wechatMoments ?? {};
    const wechat = promotions.wechatMoments ?? {};
    return {
      body: post.body || wechat.body || wechat.markdown || '',
      media
    };
  }

  return null;
}

function normalizePromotionContent(input) {
  if (!input || typeof input !== 'object') {
    throw new Error('Publish input must be a promotion JSON object.');
  }
  if (input.ai?.content) return input.ai.content;
  if (input.content?.platformVariants || input.content?.tweetPack) return input.content;
  if (input.platformVariants || input.tweetPack) return input;
  throw new Error('Publish input must include ai.content, content, platformVariants, or tweetPack.');
}

function normalizePublishPlatforms(value) {
  const normalized = String(value ?? 'all').trim().toLowerCase();
  if (normalized === 'all' || normalized === 'both') return [...ALL_PLATFORMS];
  if (['launch', 'launchkit', 'launch-kit'].includes(normalized)) {
    return ['linkedin', 'producthunt', 'hackernews'];
  }
  const aliases = {
    x: 'twitter',
    twitter: 'twitter',
    'x-twitter': 'twitter',
    linkedin: 'linkedin',
    'linked-in': 'linkedin',
    producthunt: 'producthunt',
    'product-hunt': 'producthunt',
    ph: 'producthunt',
    hackernews: 'hackernews',
    'hacker-news': 'hackernews',
    hn: 'hackernews',
    showhn: 'hackernews',
    'show-hn': 'hackernews',
    zhihu: 'zhihu',
    xhs: 'xhs',
    xiaohongshu: 'xhs',
    rednote: 'xhs',
    wechat: 'wechat-official',
    wechatofficial: 'wechat-official',
    'wechat-official': 'wechat-official',
    'wechat-article': 'wechat-official',
    moments: 'wechat-moments',
    'wechat-moments': 'wechat-moments'
  };
  const platform = aliases[normalized];
  if (!platform) {
    throw new Error(`Unsupported publish platform: ${value}`);
  }
  return [platform];
}

function normalizePublishMode(value) {
  const normalized = String(value ?? 'review').trim().toLowerCase();
  if (['review', 'dry-run', 'api', 'assist'].includes(normalized)) return normalized;
  throw new Error('--publish-mode expects review, dry-run, api, or assist');
}

function markdownToThread(markdown) {
  if (!markdown) return [];
  return String(markdown)
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 6);
}

function reviewChecklistFor(platform, payload) {
  const checklist = [
    'Human has reviewed the final text.',
    'Claims match source evidence.',
    'Links, commands, and images are correct.',
    'Account, audience, and platform are correct.'
  ];
  if (platform === 'twitter') checklist.push('Thread order and hashtag count are acceptable.');
  if (platform === 'producthunt') checklist.push('Tagline is short and no fake traction is claimed.');
  if (platform === 'hackernews') checklist.push('Title starts with Show HN and the project is tryable.');
  if (platform === 'wechat-official') checklist.push('Cover image and media IDs are prepared before API publishing.');
  if (!hasMeaningfulPayload(payload)) checklist.push('Payload is sparse; regenerate or edit before publishing.');
  return checklist;
}

function browserAssistPlan(platform, payload) {
  const target = BROWSER_ASSIST_TARGETS[platform] ?? {
    openUrl: '',
    surface: `${platform} composer`
  };
  return {
    mode: 'logged_in_browser_fill',
    openUrl: target.openUrl,
    surface: target.surface,
    requiresLoggedInBrowser: true,
    finalAction: 'user_clicks_publish_after_review',
    disallowedActions: [
      'do_not_login_or_collect_credentials',
      'do_not_read_or_export_cookies',
      'do_not_bypass_captcha_or_risk_checks',
      'do_not_click_publish_or_submit_automatically',
      'do_not_call_private_or_reverse_engineered_platform_apis'
    ],
    fields: assistFieldsFor(platform, payload),
    manualConfirmation: [
      'Confirm the logged-in account is correct.',
      'Confirm text, images, links, and tags are accurate.',
      'Confirm the platform preview looks right.',
      'Click publish manually only after review.'
    ]
  };
}

function assistFieldsFor(platform, payload) {
  if (platform === 'twitter') {
    return compactFields([
      textField('postText', payload.text),
      listField('threadPosts', payload.thread),
      listField('hashtags', payload.hashtags),
      mediaField(payload.media)
    ]);
  }

  if (platform === 'linkedin') {
    return compactFields([
      textField('postText', payload.text),
      listField('carouselOutline', payload.carouselOutline),
      textField('firstComment', payload.firstComment),
      mediaField(payload.media)
    ]);
  }

  if (platform === 'producthunt') {
    return compactFields([
      textField('tagline', payload.tagline),
      textField('description', payload.description),
      textField('makerComment', payload.makerComment),
      listField('launchChecklist', payload.launchChecklist),
      mediaField(payload.media)
    ]);
  }

  if (platform === 'hackernews') {
    return compactFields([
      textField('title', payload.title),
      textField('urlOrBody', payload.body),
      textField('firstComment', payload.firstComment)
    ]);
  }

  if (platform === 'zhihu') {
    return compactFields([
      textField('title', payload.title),
      textField('hook', payload.hook),
      textField('body', payload.body),
      listField('citationsToUse', payload.citationsToUse),
      mediaField(payload.media)
    ]);
  }

  if (platform === 'xhs') {
    return compactFields([
      textField('title', payload.title),
      listField('coverTexts', payload.coverTexts),
      textField('body', payload.body),
      listField('tags', payload.tags),
      listField('carouselCards', payload.carousel),
      mediaField(payload.media)
    ]);
  }

  if (platform === 'wechat-official') {
    return compactFields([
      textField('title', payload.title),
      textField('summary', payload.summary),
      textField('coverText', payload.coverText),
      textField('body', payload.body),
      listField('sectionOutline', payload.sectionOutline),
      mediaField(payload.media)
    ]);
  }

  if (platform === 'wechat-moments') {
    return compactFields([
      textField('body', payload.body),
      mediaField(payload.media)
    ]);
  }

  return Object.entries(payload)
    .filter(([, value]) => hasFieldValue(value))
    .map(([name, value]) => ({ name, type: Array.isArray(value) ? 'list' : 'text', value }));
}

function hasMeaningfulPayload(payload) {
  return Object.values(payload).some((value) => {
    if (Array.isArray(value)) return value.length > 0;
    return Boolean(String(value ?? '').trim());
  });
}

function appendAssist(lines, assist) {
  if (!assist) return;
  lines.push('');
  lines.push('Browser assist');
  lines.push(`Mode: ${assist.mode}`);
  lines.push(`Open: ${assist.openUrl}`);
  lines.push(`Surface: ${assist.surface}`);
  lines.push(`Final action: ${assist.finalAction}`);
  appendListValues(lines, 'Fields to fill', assist.fields?.map((field) => `${field.name}: ${formatValue(field.value)}`));
  appendListValues(lines, 'Disallowed actions', assist.disallowedActions);
  appendListValues(lines, 'Manual confirmation', assist.manualConfirmation);
}

function appendPayload(lines, payload) {
  lines.push('');
  lines.push('Payload');
  for (const [key, value] of Object.entries(payload)) {
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      lines.push(`${key}:`);
      value.forEach((item, index) => {
        lines.push(`  ${index + 1}. ${formatValue(item)}`);
      });
    } else if (value) {
      lines.push(`${key}: ${value}`);
    }
  }
}

function appendChecklist(lines, checklist) {
  if (!Array.isArray(checklist) || checklist.length === 0) return;
  lines.push('');
  lines.push('Review checklist');
  checklist.forEach((item) => lines.push(`- ${item}`));
}

function appendListValues(lines, title, values) {
  if (!Array.isArray(values) || values.length === 0) return;
  lines.push('');
  lines.push(title);
  values.forEach((item) => lines.push(`- ${item}`));
}

function normalizeList(value) {
  const values = Array.isArray(value) ? value : [value];
  return values
    .flatMap((item) => String(item ?? '').split(','))
    .map((item) => item.trim())
    .filter(Boolean);
}

function textField(name, value) {
  return hasFieldValue(value) ? { name, type: 'text', value } : null;
}

function listField(name, value) {
  return Array.isArray(value) && value.length > 0 ? { name, type: 'list', value } : null;
}

function mediaField(value) {
  return Array.isArray(value) && value.length > 0 ? { name: 'media', type: 'media', value } : null;
}

function compactFields(fields) {
  return fields.filter(Boolean);
}

function hasFieldValue(value) {
  if (Array.isArray(value)) return value.length > 0;
  return Boolean(String(value ?? '').trim());
}

function firstValue(values) {
  return Array.isArray(values) ? values.find(Boolean) : null;
}

function formatValue(value) {
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
