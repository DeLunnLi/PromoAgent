import sharp from 'sharp';

const FONT_STACK = 'PingFang SC, Hiragino Sans GB, Microsoft YaHei, Noto Sans CJK SC, sans-serif';

export function shouldApplyPromoTextOverlay(env = process.env) {
  return (env.SOURCE2LAUNCH_IMAGE_TEXT_OVERLAY ?? env.STAR_UP_IMAGE_TEXT_OVERLAY) !== 'false';
}

export function buildPromoCoverText(result, options = {}) {
  const env = options.env ?? process.env;
  const platform = normalizeOverlayPlatform(options.platform ?? 'xhs');
  const project = result?.project ?? {};
  const topics = (project.topics ?? []).join(' ');
  const blob = `${topics} ${project.name ?? ''} ${project.description ?? ''}`;

  const title = String(env.SOURCE2LAUNCH_IMAGE_TITLE ?? env.STAR_UP_IMAGE_TITLE ?? project.name ?? 'Source2Launch').trim();
  const subtitle = String(env.SOURCE2LAUNCH_IMAGE_SUBTITLE ?? env.STAR_UP_IMAGE_SUBTITLE ?? '').trim()
    || defaultSubtitle(blob, platform);
  const badges = parseBadges(
    env.SOURCE2LAUNCH_IMAGE_BADGES
    ?? env.STAR_UP_IMAGE_BADGES
    ?? (platform === 'wechat' ? 'AI 读懂项目,发布资料,人工审核' : 'AI 项目理解,多平台文案,人工审核')
  );

  return { title, subtitle, badges, platform };
}

export async function applyPromoTextOverlay(buffer, options = {}) {
  const meta = await sharp(buffer).metadata();
  const width = meta.width ?? options.width ?? 1024;
  const height = meta.height ?? options.height ?? 1024;
  const text = options.text ?? {};
  const platform = normalizeOverlayPlatform(options.platform ?? text.platform ?? 'xhs');
  const svg = buildOverlaySvg(width, height, { ...text, platform }, platform);

  return sharp(buffer)
    .composite([{ input: Buffer.from(svg), top: 0, left: 0 }])
    .png()
    .toBuffer();
}

function defaultSubtitle(blob, platform) {
  if (/ai|llm|model|agent/i.test(blob)) {
    return platform === 'wechat'
      ? '大模型读懂开源项目，生成多平台文案'
      : 'README 没人看？先让 AI 读懂你的项目';
  }
  return platform === 'wechat'
    ? '开源项目与论文的发布资料生成'
    : '一行命令 · 项目理解 · 多平台发布草稿';
}

function parseBadges(raw) {
  return String(raw ?? '')
    .split(/[,，|]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 4);
}

function buildOverlaySvg(width, height, text, platform) {
  const title = escapeXml(text.title ?? 'Source2Launch');
  const subtitle = escapeXml(text.subtitle ?? '');
  const badges = (text.badges ?? []).map(escapeXml);
  const isVertical = height > width * 1.1 || platform === 'xhs';

  const titleSize = isVertical ? Math.round(width * 0.1) : Math.round(width * 0.11);
  const subtitleSize = isVertical ? Math.round(width * 0.048) : Math.round(width * 0.052);
  const titleY = isVertical ? Math.round(height * 0.16) : Math.round(height * 0.14);
  const subtitleY = titleY + Math.round(titleSize * 1.15);
  const badgeY = subtitleY + Math.round(subtitleSize * 1.35);
  const badgeFont = Math.round(subtitleSize * 0.62);
  const badgeGap = Math.round(badgeFont * 0.9);
  const badgePadX = Math.round(badgeFont * 0.85);
  const badgePadY = Math.round(badgeFont * 0.45);
  const badgeHeight = badgeFont + badgePadY * 2;

  let badgeMarkup = '';
  if (badges.length > 0) {
    const totalWidth = badges.reduce((sum, badge) => {
      return sum + estimateTextWidth(badge, badgeFont) + badgePadX * 2 + badgeGap;
    }, -badgeGap);
    let cursorX = (width - totalWidth) / 2;

    for (const badge of badges) {
      const badgeWidth = estimateTextWidth(badge, badgeFont) + badgePadX * 2;
      badgeMarkup += `
        <rect x="${cursorX.toFixed(1)}" y="${(badgeY - badgePadY).toFixed(1)}"
          width="${badgeWidth.toFixed(1)}" height="${badgeHeight.toFixed(1)}"
          rx="${Math.round(badgeHeight / 2)}" fill="rgba(255,255,255,0.72)" stroke="rgba(30,58,95,0.12)"/>
        <text x="${(cursorX + badgeWidth / 2).toFixed(1)}" y="${(badgeY + badgeFont * 0.78).toFixed(1)}"
          text-anchor="middle" font-family="${FONT_STACK}" font-size="${badgeFont}"
          font-weight="600" fill="#1e3a5f">${badge}</text>`;
      cursorX += badgeWidth + badgeGap;
    }
  }

  return `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="titleFade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="rgba(255,255,255,0.55)"/>
      <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="${width}" height="${Math.round(height * (isVertical ? 0.42 : 0.38))}" fill="url(#titleFade)"/>
  <text x="${width / 2}" y="${titleY}" text-anchor="middle"
    font-family="${FONT_STACK}" font-size="${titleSize}" font-weight="700"
    fill="#102a43">${title}</text>
  <text x="${width / 2}" y="${subtitleY}" text-anchor="middle"
    font-family="${FONT_STACK}" font-size="${subtitleSize}" font-weight="500"
    fill="#486581">${subtitle}</text>
  ${badgeMarkup}
</svg>`;
}

function estimateTextWidth(text, fontSize) {
  let width = 0;
  for (const char of String(text)) {
    width += /[\u4e00-\u9fff]/.test(char) ? fontSize : fontSize * 0.58;
  }
  return width;
}

function escapeXml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function normalizeOverlayPlatform(platform) {
  const normalized = String(platform ?? 'xhs').trim().toLowerCase();
  if (['wechat', 'weixin', 'wx'].includes(normalized)) return 'wechat';
  return 'xhs';
}
