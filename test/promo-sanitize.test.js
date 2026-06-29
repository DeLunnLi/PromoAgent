import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { resolveEffectiveImageModel, sanitizePromoContent, sanitizeMarkdown } from '../src/promo-sanitize.js';

describe('promo sanitize', () => {
  const result = {
    project: {
      name: 'source2launch',
      installCommand: 'npx source2launch .',
      repositoryUrl: 'https://github.com/x/y'
    }
  };

  it('fixes zhihu fabrications and command drift', () => {
    const out = sanitizePromoContent({
      promotions: {
        zhihu: {
          suggestedQuestions: ['开源项目如何讲清楚？'],
          markdown: [
            '# 标题',
            '数据显示，访客只看前 10 秒。',
            'star_up . --boost 能生成文案。',
            '帮助 Z tanpa V。',
            '#开源'
          ].join('\n')
        }
      }
    }, result);

    const md = out.promotions.zhihu.markdown;
    assert.doesNotMatch(md, /数据显示/);
    assert.match(md, /source2launch optimize/);
    assert.match(md, /## 快速上手/);
    assert.match(md, /## 建议回答的问题/);
  });

  it('adds xhs title section and emoji', () => {
    const out = sanitizePromoContent({
      promotions: {
        xiaohongshu: {
          titles: ['Star 个位数？先扫 README', '一行命令查阻碍', '别硬写首屏了'],
          markdown: '## 正文\n做了 3 个月开源，Star 一直个位数？\n\n亲测一行命令。\n\n## 标签\n#开源'
        }
      }
    }, result);

    const md = out.promotions.xiaohongshu.markdown;
    assert.match(md, /## 标题备选/);
    assert.match(md, /😭|✨|😅/);
    assert.match(md, /npx source2launch \./);
  });

  it('breaks wechat styles into multiple lines', () => {
    const out = sanitizePromoContent({
      promotions: {
        wechatMoments: {
          markdown: [
            '## 风格 A · 朋友安利',
            '发现个挺香的小工具。跑了一下 npx source2launch . 挺省事。https://github.com/x/y'
          ].join('\n')
        }
      }
    }, result);

    const md = out.promotions.wechatMoments.markdown;
    assert.match(md, /发现个挺香的小工具。\n\n跑了一下/);
    assert.match(md, /https:\/\/github\.com\/x\/y\s*$/m);
  });

  it('falls back to Qwen-Image when edit model has no reference', () => {
    assert.equal(
      resolveEffectiveImageModel({ STAR_UP_IMAGE_MODEL: 'FireRedTeam/FireRed-Image-Edit-1.1' }, false),
      'Qwen/Qwen-Image'
    );
    assert.equal(
      resolveEffectiveImageModel({ STAR_UP_IMAGE_MODEL: 'Qwen/Qwen-Image' }, false),
      'Qwen/Qwen-Image'
    );
  });

  it('strips unverified star growth claims', () => {
    const md = sanitizeMarkdown('第二天多了 50 个 star，省了半小时。');
    assert.doesNotMatch(md, /50 个 star/);
    assert.doesNotMatch(md, /半小时/);
  });
});
