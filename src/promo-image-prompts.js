import { shouldComposeXhsCover } from './promo-image-compose.js';

const DEFAULT_NEGATIVE_PROMPT = [
  'text, letters, words, watermark, logo, signature, username, caption, title, subtitle',
  'human, face, portrait, silhouette, body, hands, fingers',
  'blurry, low quality, jpeg artifacts, noisy, oversaturated, neon purple gradient',
  'chaotic layout, cluttered, messy, duplicate elements, AI slop',
  'xiaohongshu logo, app UI mockup, fake brand mark, phone bezel, macOS window buttons'
].join(', ');

const STYLE_PRESETS = {
  poster: {
    xhs: [
      '竖版 3:4 扁平插画海报（整张画布就是封面，绝对不是手机截图，不要手机边框不要设备外框）。',
      '背景：米白到浅天蓝渐变；上方 35% 仅留白渐变。',
      '下方横排三枚小圆角方块图标：终端窗口、纯色金色五角星、文档页，等距排列。',
      '矢量扁平、轻阴影、低饱和、细节清晰，小红书科技风。',
      '禁止：手机、平板、浏览器窗口、字母、数字、logo、人脸、水印。'
    ],
    wechat: [
      '方形 1:1 封面，与小红书同款视觉：米白浅蓝背景。',
      '中央横排三枚圆角图标：终端、纯色金色五角星、文档页，扁平插画，轻阴影。',
      '不要文字、不要手机外框、不要水印。'
    ]
  },
  minimal: {
    xhs: [
      '竖版 3:4 开发者工具海报，奶油色背景，中央金色星形与代码括号 {} 组合图标。',
      '轻阴影，扁平插画，上方留白，细节清晰，不要空画面。',
      '不要文字、人脸、手机外框、窗口按钮。'
    ],
    wechat: [
      '方形封面，米白背景，中央星形与代码括号图标，扁平风格，无文字。'
    ]
  },
  terminal: {
    xhs: [
      '竖版 3:4，深蓝灰背景，中央 stylized 终端窗口与星星图标，IDE 官网配图风格。',
      '窗口内仅色块无文字，上方留白，专业克制，无手机外框。'
    ],
    wechat: [
      '方形封面，深色终端窗口与星形图标，极简，无文字无人脸。'
    ]
  },
  vibrant: {
    xhs: [
      '竖版 3:4，低饱和马卡龙色（浅绿、浅橙、米白），等距小场景：笔记本 + 星星 + 文件夹。',
      '可爱清爽，上方留白，无文字无 logo。'
    ],
    wechat: [
      '方形清新等距插画，开源工具主题，浅色背景，无文字。'
    ]
  },
  result: {
    xhs: [
      'Vertical 3:4 tech product dashboard poster, dark navy blue background (#0d1117 to #1a1f2e gradient).',
      'Central focus: a stylized terminal window with frosted glass effect, occupying upper 60% of canvas.',
      'Inside the terminal window display:',
      '- Three small colored circles (red, yellow, green) at top left as window controls',
      '- A launch evidence board made of abstract cards, checkmarks, and source snippets represented by shapes only',
      '- Three clear visual zones: project summary, platform copy, image asset plan',
      '- Four horizontal checklist bars with checkmarks and caution icons, no numbers and no grade badge',
      'Lower portion: decorative elements including golden stars, code brackets, soft glow effects.',
      'Style: modern dark IDE interface, glassmorphism, subtle neon accents, professional developer tool aesthetic.',
      'NO real text, NO human faces, NO watermarks, NO smartphone mockups.'
    ],
    wechat: [
      'Square 1:1 tech dashboard illustration, dark navy blue background.',
      'Central stylized terminal window with abstract project evidence cards and launch asset checklist.',
      'Glassmorphism effects, neon accents, modern dark IDE style.',
      'NO real readable text, NO human faces, NO watermarks.'
    ]
  },
  beforeafter: {
    xhs: [
      'Vertical 3:4 split-screen comparison poster, soft cream and light blue gradient background.',
      'LEFT side (30% width): muted gray tones, chaotic messy lines, dim faded star, question mark shape, represents "before".',
      'RIGHT side (70% width): bright clean blue-white tones, organized terminal window shape, bright golden glowing star, upward arrow, represents "after".',
      'Center divider: a golden star icon between the two sides, symbolizing transformation.',
      'Style: clean flat illustration, modern tech marketing visual, professional and aspirational.',
      'NO real screenshots, NO readable text, NO human faces, NO watermarks.'
    ],
    wechat: [
      'Square 1:1 split-screen comparison illustration.',
      'Left: muted chaotic elements; right: bright organized terminal and glowing star.',
      'Flat illustration, no readable text, no human faces, no watermarks.'
    ]
  }
};

export function resolvePromoImageStyle(env = process.env) {
  const style = String(env.SOURCE2LAUNCH_IMAGE_STYLE ?? env.STAR_UP_IMAGE_STYLE ?? env.SOURCE2LAUNCH_PROMO_IMAGE_STYLE ?? env.STAR_UP_PROMO_IMAGE_STYLE ?? 'poster').trim().toLowerCase();
  const validStyles = Object.keys(STYLE_PRESETS);
  return validStyles.includes(style) ? style : 'poster';
}

export function listAvailableImageStyles() {
  return Object.keys(STYLE_PRESETS).map(key => ({
    id: key,
    description: getStyleDescription(key)
  }));
}

function getStyleDescription(style) {
  const descriptions = {
    poster: '标准插画海报风格，三图标设计，适合通用场景',
    minimal: '极简风格，星形与代码括号组合，清爽简约',
    terminal: '深色终端风格，IDE 官网配图感，专业开发者向',
    vibrant: '马卡龙色系等距插画，可爱清新风格',
    result: '效果展示风格，展示资料检查、平台文案和配图计划，突出工具价值',
    beforeafter: '前后对比风格，暗示优化提升，适合讲故事'
  };
  return descriptions[style] ?? style;
}

export function buildPromoImageNegativePrompt(env = process.env) {
  const custom = String(env.SOURCE2LAUNCH_IMAGE_NEGATIVE_PROMPT ?? env.STAR_UP_IMAGE_NEGATIVE_PROMPT ?? '').trim();
  return custom || DEFAULT_NEGATIVE_PROMPT;
}

export function extractPromoVisualTheme(result) {
  const project = result?.project ?? {};
  const topics = (project.topics ?? []).slice(0, 5);
  const name = project.name ?? '';
  const hints = [];

  if (/star|github|repo|readme|launch|audit|cli|open.?source/i.test(`${topics.join(' ')} ${name}`)) {
    hints.push('开源仓库收藏');
  }
  if (/ai|llm|model|agent/i.test(`${topics.join(' ')} ${name}`)) {
    hints.push('AI 辅助');
  }
  if (/cli|terminal|command/i.test(`${topics.join(' ')} ${project.installCommand ?? ''}`)) {
    hints.push('命令行工具');
  }

  return hints.length > 0 ? hints.join('、') : '开发者效率';
}

export function buildPromoImagePrompt(result, options = {}) {
  const platform = normalizeImagePlatform(options.platform ?? 'xhs');
  const env = options.env ?? process.env;

  if (options.prompt) {
    return String(options.prompt).trim();
  }

  const model = options.model ?? env.SOURCE2LAUNCH_IMAGE_MODEL ?? env.STAR_UP_IMAGE_MODEL ?? env.MODELSCOPE_IMAGE_MODEL ?? '';
  const provider = options.provider ?? 'modelscope';
  const project = result.project;

  if (provider === 'modelscope' && options.hasReference && /(?:fire|image-edit|-edit-)/i.test(String(model))) {
    return buildEditEnhancePrompt(project, extractPromoVisualTheme(result));
  }

  const style = resolvePromoImageStyle(env);
  const theme = extractPromoVisualTheme(result);

  if (platform === 'wechat') {
    return buildWechatPosterPrompt(theme, STYLE_PRESETS[style].wechat, style);
  }

  if (shouldComposeXhsCover(platform, env) && style === 'poster') {
    return buildSquareComposePrompt(theme);
  }

  if (style === 'poster') {
    return buildXhsPosterPrompt(theme);
  }

  const preset = STYLE_PRESETS[style].xhs;
  return [
    ...preset,
    `主题：${theme}。`,
    '纯视觉插画，不得出现可读文字。',
    'FULL BLEED POSTER CANVAS ONLY — NOT smartphone mockup, NOT device bezel.'
  ].join(' ');
}

const POSTER_VISUAL_RICHNESS = 'subtle dot grid texture, faint floating geometric accents (brackets, circles, soft blobs), layered depth, Dribbble-quality developer tool aesthetic';

const POSTER_ICON_ROW = 'three polished isometric rounded-square icons in one horizontal row — stylized code editor, glowing gold star, document with folded corner — soft shadows and crisp detail, no readable text inside icons';

function buildXhsPosterPrompt(theme) {
  return [
    'Vertical 3:4 premium tech product launch illustration, full-bleed canvas.',
    'NOT smartphone mockup, NOT device bezel.',
    `Soft cream to light sky-blue gradient, ${POSTER_VISUAL_RICHNESS}.`,
    'Upper half open clean space reserved for typography overlay.',
    `Lower third: ${POSTER_ICON_ROW}.`,
    `Mood (do not render as text): ${theme}.`,
    'No letters, no words, no logos, no faces, no watermarks in the illustration.'
  ].join(' ');
}

function buildSquareComposePrompt(theme) {
  return [
    'Square 1:1 premium tech product launch illustration, full-bleed canvas.',
    'NOT smartphone mockup, NOT device bezel.',
    `Soft cream to light sky-blue gradient, ${POSTER_VISUAL_RICHNESS}.`,
    'Upper two thirds open clean space reserved for typography overlay.',
    `Lower third: ${POSTER_ICON_ROW}.`,
    `Mood (do not render as text): ${theme}.`,
    'No letters, no words, no logos, no faces, no watermarks in the illustration.'
  ].join(' ');
}

function buildWechatPosterPrompt(theme, fallbackLines = [], style = 'poster') {
  if (style !== 'poster' && fallbackLines.length > 0) {
    return [...fallbackLines, `主题：${theme}。`, '无文字无 logo。'].join(' ');
  }

  return [
    'Square 1:1 premium tech product launch illustration, full-bleed canvas.',
    'NOT smartphone mockup, NOT device bezel.',
    `Soft cream to light sky-blue gradient, ${POSTER_VISUAL_RICHNESS}.`,
    'Upper half open space for typography overlay.',
    `Center-lower area: ${POSTER_ICON_ROW}.`,
    `Mood (do not render as text): ${theme}.`,
    'No letters, no words, no logos, no faces, no watermarks in the illustration.'
  ].join(' ');
}

export function buildPromoImageRequestExtras(options = {}, env = process.env) {
  const extras = {};
  const negative = String(env.SOURCE2LAUNCH_IMAGE_NEGATIVE_PROMPT ?? env.STAR_UP_IMAGE_NEGATIVE_PROMPT ?? '').trim();
  if (negative) {
    extras.negative_prompt = negative;
  }

  if ((env.SOURCE2LAUNCH_IMAGE_PROMPT_EXTEND ?? env.STAR_UP_IMAGE_PROMPT_EXTEND) === 'true' && isQwenFamilyModel(options.model ?? env.SOURCE2LAUNCH_IMAGE_MODEL ?? env.STAR_UP_IMAGE_MODEL)) {
    extras.prompt_extend = true;
  }

  return extras;
}

function buildEditEnhancePrompt(project, theme) {
  return [
    'Enhance this screenshot into a polished social cover while keeping UI content readable.',
    `Theme: ${theme}.`,
    'Style: clean tech poster, soft neutral background, subtle depth.',
    'Do not add any new text, logos, watermarks, faces, or fake platform branding.',
    'Crop-friendly vertical composition with breathing room at top.'
  ].join(' ');
}

function normalizeImagePlatform(platform) {
  const normalized = String(platform ?? 'xhs').trim().toLowerCase();
  if (['wechat', 'weixin', 'wx'].includes(normalized)) return 'wechat';
  return 'xhs';
}

function isQwenFamilyModel(modelId) {
  return /qwen/i.test(String(modelId ?? ''));
}
