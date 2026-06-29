import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const MAX_BRIEF_CHARS = 8_000;

export function resolvePromoBrief(options = {}, env = process.env, cwd = process.cwd()) {
  const inline = String(
    options.promoBrief
    ?? options.brief
    ?? env.SOURCE2LAUNCH_PROMO_BRIEF
    ?? env.STAR_UP_PROMO_BRIEF
    ?? ''
  ).trim();

  const filePath = String(
    options.promoBriefFile
    ?? options.briefFile
    ?? env.SOURCE2LAUNCH_PROMO_BRIEF_FILE
    ?? env.STAR_UP_PROMO_BRIEF_FILE
    ?? ''
  ).trim();

  const parts = [];
  if (inline) parts.push(inline);
  if (filePath) parts.push(readBriefFile(filePath, cwd));

  const brief = parts.join('\n\n').trim();
  if (!brief) return null;
  return brief.slice(0, MAX_BRIEF_CHARS);
}

export function buildPromoBriefSection(brief) {
  const text = String(brief ?? '').trim();
  if (!text) return '';

  return [
    '## 用户创作引导（必须遵循，但不得违背证据）',
    '以下是维护者提供的风格/思路/受众偏好。优先级高于默认模板写法，但仍须遵守「可信度铁律」：',
    '',
    text,
    '',
    '执行规则：',
    '- 引导只影响语气、结构、重点平台、叙事角度',
    '- 若引导与 evidence / installCommand 冲突，以 evidence 为准',
    '- 不得因引导而编造 star 增长、用户数、媒体报道'
  ].join('\n');
}

function readBriefFile(filePath, cwd) {
  const resolved = path.isAbsolute(filePath) ? filePath : path.resolve(cwd, filePath);
  if (!existsSync(resolved)) {
    throw new Error(`Promo brief file not found: ${filePath}`);
  }
  return readFileSync(resolved, 'utf8').slice(0, MAX_BRIEF_CHARS);
}
