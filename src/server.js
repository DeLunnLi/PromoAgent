import http from 'node:http';

import { generateImageAsset, generateImageFromPrompt } from './image.js';

const DEFAULT_HOST = '127.0.0.1';
const DEFAULT_PORT = 4317;
const MAX_BODY_BYTES = 2 * 1024 * 1024;

export function createImageApiServer(options = {}, env = process.env) {
  return http.createServer((request, response) => {
    handleImageApiRequest(request, response, options, env).catch((error) => {
      sendJson(response, error.statusCode || 500, {
        error: {
          message: error.message,
          type: error.type || 'server_error'
        }
      });
    });
  });
}

export async function startImageApiServer(options = {}, env = process.env) {
  const host = options.host || env.SOURCE2LAUNCH_API_HOST || env.STAR_UP_API_HOST || DEFAULT_HOST;
  const port = Number(options.port || env.SOURCE2LAUNCH_API_PORT || env.STAR_UP_API_PORT || DEFAULT_PORT);
  const server = createImageApiServer(options, env);

  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, resolve);
  });

  return {
    host,
    port,
    server,
    url: `http://${host}:${port}`
  };
}

export async function runImageApiCli(argv = process.argv, env = process.env) {
  const options = parseServerArgs(argv.slice(2));

  if (options.help) {
    console.log([
      'source2launch-api',
      '',
      'Usage:',
      '  source2launch-api [options]',
      '',
      'Options:',
      '  --host <host>      Host to bind, default 127.0.0.1',
      '  --port <port>      Port to bind, default 4317',
      '  --token <token>    Require Authorization: Bearer <token>',
      '  -h, --help         Show help'
    ].join('\n'));
    return;
  }

  const serverInfo = await startImageApiServer(options, env);
  console.log(`Source2Launch image API listening on ${serverInfo.url}`);
  console.log('POST /v1/images/generations');
  console.log('POST /v1/images/edits');
}

export async function handleImageApiRequest(request, response, options = {}, env = process.env) {
  setCorsHeaders(response);

  if (request.method === 'OPTIONS') {
    response.writeHead(204);
    response.end();
    return;
  }

  const url = new URL(request.url, 'http://localhost');

  if (request.method === 'GET' && url.pathname === '/health') {
    sendJson(response, 200, {
      ok: true,
      service: 'source2launch image api'
    });
    return;
  }

  if (request.method !== 'POST') {
    sendJson(response, 405, {
      error: {
        message: 'Method not allowed',
        type: 'method_not_allowed'
      }
    });
    return;
  }

  assertAuthorized(request, options, env);

  if (url.pathname === '/v1/images/generations' || url.pathname === '/api/images/generate') {
    const body = await readJsonBody(request);
    rejectClientApiKey(body);
    const result = await generateImageFromPrompt(normalizeGenerationInput(body), imageOptionsFromBody(body), env);
    sendJson(response, 200, {
      ok: true,
      operation: 'generate',
      provider: body.provider || env.SOURCE2LAUNCH_IMAGE_PROVIDER || env.STAR_UP_IMAGE_PROVIDER || 'openai',
      result
    });
    return;
  }

  if (url.pathname === '/v1/images/edits' || url.pathname === '/api/images/edit') {
    const body = await readJsonBody(request);
    rejectClientApiKey(body);
    const asset = normalizeEditInput(body);
    const result = await generateImageAsset(asset, imageOptionsFromBody(body), env);
    sendJson(response, 200, {
      ok: true,
      operation: 'edit',
      provider: body.provider || env.SOURCE2LAUNCH_IMAGE_PROVIDER || env.STAR_UP_IMAGE_PROVIDER || 'openai',
      result
    });
    return;
  }

  sendJson(response, 404, {
    error: {
      message: 'Not found',
      type: 'not_found'
    }
  });
}

function normalizeGenerationInput(body) {
  return {
    id: body.id,
    prompt: body.prompt,
    n: body.n,
    size: body.size,
    quality: body.quality,
    imageUrl: body.imageUrl ?? body.image_url,
    imageBase64: body.imageBase64 ?? body.image_base64
  };
}

function normalizeEditInput(body) {
  const prompt = cleanText(body.prompt);
  if (!prompt) throw clientError('Image edit requires a prompt.');

  return {
    id: cleanText(body.id) || 'api-image-edit',
    operation: 'edit',
    prompt,
    size: body.size,
    quality: body.quality,
    n: body.n,
    imageUrl: body.imageUrl ?? body.image_url,
    imageBase64: body.imageBase64 ?? body.image_base64,
    sourceImages: body.sourceImages ?? body.source_images ?? body.image,
    mask: body.mask
  };
}

function imageOptionsFromBody(body) {
  return {
    asyncMode: body.asyncMode ?? body.async_mode,
    baseUrl: body.baseUrl ?? body.base_url,
    imageUrl: body.imageUrl ?? body.image_url,
    loras: body.loras,
    model: body.model,
    outputFormat: body.outputFormat ?? body.output_format,
    pollIntervalMs: body.pollIntervalMs ?? body.poll_interval_ms,
    provider: body.provider,
    quality: body.quality,
    size: body.size,
    taskTimeoutMs: body.taskTimeoutMs ?? body.task_timeout_ms
  };
}

function rejectClientApiKey(body) {
  if (body.apiKey || body.api_key || body.authorization) {
    throw clientError('Do not send provider API keys in the request body. Configure them on the server environment.');
  }
}

function assertAuthorized(request, options, env) {
  const token = options.token || env.SOURCE2LAUNCH_API_SERVER_TOKEN || env.STAR_UP_API_SERVER_TOKEN;
  if (!token) return;

  const authorization = request.headers.authorization || '';
  const headerToken = request.headers['x-source2launch-token'];
  if (authorization === `Bearer ${token}` || headerToken === token) return;

  const error = clientError('Unauthorized image API request.');
  error.statusCode = 401;
  error.type = 'unauthorized';
  throw error;
}

async function readJsonBody(request) {
  const chunks = [];
  let size = 0;

  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      const error = clientError('Request body is too large.');
      error.statusCode = 413;
      throw error;
    }
    chunks.push(chunk);
  }

  if (chunks.length === 0) return {};

  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw clientError('Request body must be valid JSON.');
  }
}

function sendJson(response, statusCode, payload) {
  setCorsHeaders(response);
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8'
  });
  response.end(`${JSON.stringify(payload, null, 2)}\n`);
}

function setCorsHeaders(response) {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Headers', 'authorization, content-type, x-source2launch-token');
  response.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
}

function clientError(message) {
  const error = new Error(message);
  error.statusCode = 400;
  error.type = 'invalid_request';
  return error;
}

function cleanText(value) {
  return String(value ?? '').trim();
}

function parseServerArgs(args) {
  const options = {
    help: false,
    host: null,
    port: null,
    token: null
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];

    if (arg === '--help' || arg === '-h') {
      options.help = true;
    } else if (arg === '--host') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) throw new Error('--host expects a host value');
      options.host = value;
      index += 1;
    } else if (arg === '--port') {
      const value = Number(args[index + 1]);
      if (!Number.isFinite(value) || value < 1 || value > 65535) throw new Error('--port expects a valid port');
      options.port = value;
      index += 1;
    } else if (arg === '--token') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) throw new Error('--token expects a token value');
      options.token = value;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  return options;
}
