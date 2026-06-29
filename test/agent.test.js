import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { runToolAgent } from '../src/agent.js';

describe('runToolAgent', () => {
  it('executes tool calls then returns final JSON content', async () => {
    let callCount = 0;
    const result = await runToolAgent({
      messages: [{ role: 'user', content: 'Generate promo JSON' }],
      maxSteps: 3,
      executeTool: async (name, args) => {
        if (name === 'read_repo_evidence') {
          return { installCommand: args.sections?.[0] ?? 'npx demo .' };
        }
        return { ok: true };
      },
      callChat: async () => {
        callCount += 1;
        if (callCount === 1) {
          return {
            choices: [{
              message: {
                content: '',
                tool_calls: [{
                  id: 'call_1',
                  type: 'function',
                  function: {
                    name: 'read_repo_evidence',
                    arguments: JSON.stringify({ sections: ['installCommand'] })
                  }
                }]
              }
            }]
          };
        }

        return {
          choices: [{
            message: {
              content: JSON.stringify({ promotions: { xiaohongshu: { markdown: '# demo' } } })
            }
          }]
        };
      }
    });

    assert.match(result.content, /promotions/);
    assert.equal(result.toolCalls.length, 1);
    assert.equal(result.toolCalls[0].name, 'read_repo_evidence');
  });
});
