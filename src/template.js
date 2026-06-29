import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildTemplateData } from './promo-shared.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATE_ROOT = path.resolve(__dirname, '..', 'templates');

const TEMPLATE_ALIASES = {
  report: 'audit/improvement-report.md',
  audit: 'audit/improvement-report.md',
  xhs: 'promo/xiaohongshu.md',
  xiaohongshu: 'promo/xiaohongshu.md',
  moments: 'promo/wechat-moments.md',
  'wechat-moments': 'promo/wechat-moments.md',
  pyq: 'promo/wechat-moments.md',
  wechat: 'promo/wechat-moments.md',
  wx: 'promo/wechat-moments.md',
  'wechat-official': 'promo/wechat-official-account.md',
  'wechat-official-account': 'promo/wechat-official-account.md',
  mp: 'promo/wechat-official-account.md',
  gzh: 'promo/wechat-official-account.md',
  zhihu: 'promo/zhihu-answer.md',
  zh: 'promo/zhihu-answer.md'
};

export function templateChoices() {
  return Object.keys(TEMPLATE_ALIASES).sort();
}

export async function renderTemplate(result, templateName, extra = {}) {
  const templatePath = resolveTemplate(templateName);
  const template = await fs.readFile(templatePath, 'utf8');
  const data = { ...buildTemplateData(result), ...extra };

  return template.replace(/{{\s*([a-zA-Z0-9_]+)\s*}}/g, (match, key) => {
    return Object.hasOwn(data, key) ? data[key] : match;
  });
}

function resolveTemplate(templateName) {
  const normalized = String(templateName ?? '').trim().toLowerCase();
  const relative = TEMPLATE_ALIASES[normalized];
  if (!relative) {
    throw new Error(`Unknown template: ${templateName}. Available templates: ${templateChoices().join(', ')}`);
  }
  return path.join(TEMPLATE_ROOT, relative);
}
