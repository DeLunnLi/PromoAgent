export const AGENT_TOOL_DEFINITIONS = [
  {
    type: 'function',
    function: {
      name: 'web_search',
      description: 'Search the web for reference promo posts, Show HN examples, Xiaohongshu writing patterns, or competitor positioning. Use before writing platform copy.',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Search query, e.g. "小红书 开源 README 推广" or "Show HN open source README audit"'
          },
          max_results: {
            type: 'integer',
            description: 'Number of results to return (1-10)',
            minimum: 1,
            maximum: 10
          }
        },
        required: ['query']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'fetch_page_text',
      description: 'Fetch readable text from a public URL returned by web_search. Use to inspect a reference article or Show HN thread.',
      parameters: {
        type: 'object',
        properties: {
          url: { type: 'string', description: 'Public http(s) URL' },
          max_chars: {
            type: 'integer',
            description: 'Maximum characters to return (500-12000)',
            minimum: 500,
            maximum: 12000
          }
        },
        required: ['url']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'read_project_summary',
      description: 'Read and summarize the scanned repository plus optional attached PDF/text documents. Use before writing promo copy to understand project positioning, risks, and document context.',
      parameters: {
        type: 'object',
        properties: {
          sections: {
            type: 'array',
            items: {
              type: 'string',
              enum: ['overview', 'readme', 'risks', 'fixes', 'documents', 'hints', 'evidence']
            },
            description: 'Summary sections to return. Defaults to all major sections.'
          },
          include_documents: {
            type: 'boolean',
            description: 'Whether to include parsed PDF/text documents in the summary'
          }
        }
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'read_pdf_document',
      description: 'Parse a local PDF into structured markdown/text. Uses pdftotext first, stream parsing fallback, optional OCR for scanned PDFs.',
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Path to a local PDF file relative to repo or absolute'
          },
          use_ocr: {
            type: 'boolean',
            description: 'Force OCR via pdftoppm + tesseract when text extraction fails'
          },
          max_chars: {
            type: 'integer',
            description: 'Maximum characters to return (default 24000)',
            minimum: 1000,
            maximum: 50000
          }
        },
        required: ['path']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'read_repo_evidence',
      description: 'Read verified facts from the scanned repository audit. Always use before citing install commands, risks, or README details.',
      parameters: {
        type: 'object',
        properties: {
          sections: {
            type: 'array',
            items: {
              type: 'string',
              enum: [
                'summary',
                'launchRisks',
                'topFixes',
                'readmeOpening',
                'readmeFirstScreen',
                'checks',
                'installCommand',
                'headings',
                'visuals',
                'repository'
              ]
            },
            description: 'Evidence sections to load. Defaults to summary + risks + fixes + installCommand + readmeOpening.'
          }
        }
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'generate_promo_image',
      description: 'Generate a promo cover image for Xiaohongshu (3:4) or WeChat (square). Requires Gradio or ModelScope image provider configured.',
      parameters: {
        type: 'object',
        properties: {
          platform: {
            type: 'string',
            enum: ['xhs', 'wechat'],
            description: 'Target platform'
          },
          prompt: {
            type: 'string',
            description: 'Image generation prompt in English or Chinese'
          },
          filename: {
            type: 'string',
            description: 'Optional output filename, e.g. xhs-cover.jpg'
          }
        },
        required: ['platform', 'prompt']
      }
    }
  }
];

export function filterToolDefinitions(enabledTools) {
  if (!Array.isArray(enabledTools) || enabledTools.length === 0) {
    return AGENT_TOOL_DEFINITIONS;
  }

  const allowed = new Set(enabledTools);
  return AGENT_TOOL_DEFINITIONS.filter((tool) => allowed.has(tool.function.name));
}
