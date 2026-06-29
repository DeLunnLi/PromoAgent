/**
 * 配置文件支持模块
 * 支持 .source2launchrc, .source2launchrc.json, source2launch.config.cjs 等配置文件
 */

import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);

/**
 * @typedef {Object} Source2LaunchConfig
 * @property {string} [model] - AI 模型名称
 * @property {string} [baseUrl] - API 基础 URL
 * @property {string} [apiKey] - API 密钥
 * @property {number} [maxTokens] - 最大令牌数
 * @property {number} [temperature] - 温度参数
 * @property {boolean} [vision] - 是否启用视觉分析
 * @property {boolean} [stream] - 是否启用流式输出
 * @property {boolean} [cache] - 是否启用缓存
 * @property {string} [optimizeDir] - 优化包输出目录
 * @property {string} [imageProvider] - 图片生成提供商
 * @property {Object} [promo] - 推广配置
 * @property {string[]} [promo.platforms] - 默认推广平台
 * @property {Object} [templates] - 模板配置
 */

const CONFIG_FILES = [
  '.source2launchrc',
  '.source2launchrc.json',
  'source2launch.config.cjs',
  'source2launch.config.json'
];

/**
 * 加载配置文件
 * @param {string} cwd - 当前工作目录
 * @returns {Source2LaunchConfig|null} 配置对象，未找到返回 null
 */
export function loadConfig(cwd = process.cwd()) {
  for (const file of CONFIG_FILES) {
    const filePath = path.join(cwd, file);

    if (!existsSync(filePath)) {
      continue;
    }

    try {
      if (file.endsWith('.js')) {
        // 动态导入 JS 配置文件
        const config = require(filePath);
        return normalizeConfig(config?.default ?? config);
      }

      // JSON 配置文件
      const content = readFileSync(filePath, 'utf8');
      return normalizeConfig(JSON.parse(content));
    } catch (error) {
      console.error(`加载配置文件失败: ${filePath}`, error.message);
      continue;
    }
  }

  return null;
}

/**
 * 从 package.json 加载配置
 * @param {string} cwd - 当前工作目录
 * @returns {Source2LaunchConfig|null} 配置对象
 */
export function loadConfigFromPackageJson(cwd = process.cwd()) {
  try {
    const packagePath = path.join(cwd, 'package.json');
    if (!existsSync(packagePath)) {
      return null;
    }

    const packageJson = JSON.parse(readFileSync(packagePath, 'utf8'));
    if (packageJson.source2launch) {
      return normalizeConfig(packageJson.source2launch);
    }
  } catch {
    // 忽略错误
  }

  return null;
}

/**
 * 合并配置
 * @param {Source2LaunchConfig|null} fileConfig - 文件配置
 * @param {Source2LaunchConfig|null} packageConfig - package.json 配置
 * @returns {Source2LaunchConfig} 合并后的配置
 */
export function mergeConfigs(fileConfig, packageConfig) {
  const merged = {};

  if (packageConfig) {
    Object.assign(merged, packageConfig);
  }

  if (fileConfig) {
    Object.assign(merged, fileConfig);
  }

  return merged;
}

/**
 * 规范化配置
 * @param {Object} config - 原始配置
 * @returns {Source2LaunchConfig} 规范化后的配置
 */
function normalizeConfig(config) {
  if (!config || typeof config !== 'object') {
    return {};
  }

  const normalized = { ...config };

  // 数值参数校验
  if (normalized.maxTokens !== undefined) {
    normalized.maxTokens = Math.max(256, Number(normalized.maxTokens) || 4096);
  }

  if (normalized.temperature !== undefined) {
    normalized.temperature = Math.max(0, Math.min(2, Number(normalized.temperature) || 0.7));
  }

  // 布尔参数校验
  const booleanFields = ['vision', 'stream', 'cache'];
  for (const field of booleanFields) {
    if (normalized[field] !== undefined) {
      normalized[field] = Boolean(normalized[field]);
    }
  }

  return normalized;
}

/**
 * 获取完整配置（包含环境变量）
 * @param {string} cwd - 当前工作目录
 * @returns {Source2LaunchConfig} 完整配置
 */
export function getFullConfig(cwd = process.cwd()) {
  // 1. 加载配置文件
  const fileConfig = loadConfig(cwd);
  const packageConfig = loadConfigFromPackageJson(cwd);
  const config = mergeConfigs(fileConfig, packageConfig);

  // 2. 环境变量覆盖配置
  if (process.env.SOURCE2LAUNCH_MODEL || process.env.STAR_UP_MODEL) {
    config.model = process.env.SOURCE2LAUNCH_MODEL || process.env.STAR_UP_MODEL;
  }

  if (process.env.SOURCE2LAUNCH_BASE_URL || process.env.STAR_UP_BASE_URL) {
    config.baseUrl = process.env.SOURCE2LAUNCH_BASE_URL || process.env.STAR_UP_BASE_URL;
  }

  if (process.env.SOURCE2LAUNCH_API_KEY || process.env.STAR_UP_API_KEY) {
    config.apiKey = process.env.SOURCE2LAUNCH_API_KEY || process.env.STAR_UP_API_KEY;
  }

  if (process.env.SOURCE2LAUNCH_MAX_TOKENS || process.env.STAR_UP_MAX_TOKENS) {
    config.maxTokens = parseInt(process.env.SOURCE2LAUNCH_MAX_TOKENS || process.env.STAR_UP_MAX_TOKENS, 10);
  }

  if (process.env.SOURCE2LAUNCH_TEMPERATURE || process.env.STAR_UP_TEMPERATURE) {
    config.temperature = parseFloat(process.env.SOURCE2LAUNCH_TEMPERATURE || process.env.STAR_UP_TEMPERATURE);
  }

  if (process.env.SOURCE2LAUNCH_VISION || process.env.STAR_UP_VISION) {
    config.vision = (process.env.SOURCE2LAUNCH_VISION || process.env.STAR_UP_VISION) !== 'false';
  }

  if (process.env.SOURCE2LAUNCH_STREAM || process.env.STAR_UP_STREAM) {
    config.stream = (process.env.SOURCE2LAUNCH_STREAM || process.env.STAR_UP_STREAM) === 'true';
  }

  if (process.env.SOURCE2LAUNCH_CACHE || process.env.STAR_UP_CACHE) {
    config.cache = (process.env.SOURCE2LAUNCH_CACHE || process.env.STAR_UP_CACHE) !== 'false';
  }

  if (process.env.SOURCE2LAUNCH_OPTIMIZE_DIR || process.env.STAR_UP_OPTIMIZE_DIR) {
    config.optimizeDir = process.env.SOURCE2LAUNCH_OPTIMIZE_DIR || process.env.STAR_UP_OPTIMIZE_DIR;
  }

  return config;
}

/**
 * 生成示例配置文件
 * @returns {string} 示例配置内容
 */
export function generateExampleConfig() {
  return JSON.stringify({
    model: 'gpt-4.1-mini',
    baseUrl: 'https://api.openai.com/v1',
    maxTokens: 4096,
    temperature: 0.7,
    vision: true,
    stream: false,
    cache: true,
    optimizeDir: 'launch-assets',
    imageProvider: 'modelscope',
    promo: {
      platforms: ['xhs', 'wechat', 'zhihu'],
      defaultBrief: ''
    }
  }, null, 2);
}
