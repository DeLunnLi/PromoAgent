import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { buildPublishPlan, formatPublishPlan } from '../src/publish.js';

describe('publish plan', () => {
  it('builds review items from current promotions JSON', () => {
    const plan = buildPublishPlan({
      ai: {
        content: {
          promotions: {
            xiaohongshu: {
              titles: ['论文图怎么发'],
              markdown: '# 小红书\n\n正文',
              tags: ['#论文']
            },
            zhihu: {
              title: '这篇论文解决了什么问题？',
              markdown: '# 知乎\n\n正文',
              suggestedQuestions: ['如何理解这篇论文？']
            },
            showHn: {
              title: 'Show HN: Demo',
              markdown: 'Body'
            }
          }
        }
      }
    }, {
      platform: 'xhs',
      publishMode: 'review'
    });

    assert.equal(plan.status, 'review_required');
    assert.equal(plan.items.length, 1);
    assert.equal(plan.items[0].platform, 'xhs');
    assert.equal(plan.items[0].payload.title, '论文图怎么发');
    assert.match(formatPublishPlan(plan), /Human has reviewed/);
  });
});
