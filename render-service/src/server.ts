import { createServer as createHttpServer, type IncomingMessage, type ServerResponse } from 'node:http';

export const MAX_RENDER_BODY_BYTES = 2 * 1024 * 1024;
export const MAX_SCENES = 50;

export interface RenderDocument {
  stage?: { name?: unknown };
  scenes?: Array<{ title?: unknown }>;
}

export interface RenderServerOptions {
  token: string;
  renderer: (document: RenderDocument) => Promise<Buffer>;
  maxBodyBytes?: number;
}

function json(response: ServerResponse, status: number, body: Record<string, unknown>) {
  response.statusCode = status;
  response.setHeader('content-type', 'application/json; charset=utf-8');
  response.setHeader('cache-control', 'no-store');
  response.end(JSON.stringify(body));
}

async function body(request: IncomingMessage, maxBytes: number): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const part of request) {
    const chunk = Buffer.isBuffer(part) ? part : Buffer.from(part);
    size += chunk.length;
    if (size > maxBytes) throw Object.assign(new Error('payload too large'), { tooLarge: true });
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

export function validateRenderDocument(value: unknown): RenderDocument {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('document must be an object');
  const document = value as RenderDocument;
  if (!Array.isArray(document.scenes) || document.scenes.length === 0 || document.scenes.length > MAX_SCENES) {
    throw new Error('document scenes are outside the supported bound');
  }
  return document;
}

export function createRenderServer(options: RenderServerOptions) {
  const maxBytes = options.maxBodyBytes ?? MAX_RENDER_BODY_BYTES;
  if (!options.token.trim()) throw new Error('render service token is required');
  return createHttpServer(async (request, response) => {
    const pathname = new URL(request.url ?? '/', 'http://render-service.internal').pathname;
    if (request.method === 'GET' && pathname === '/internal/health') {
      json(response, 200, { status: 'ok' });
      return;
    }
    if (pathname !== '/internal/render' || request.method !== 'POST') {
      json(response, 404, { error: 'not_found' });
      return;
    }
    if (request.headers['x-render-service-token'] !== options.token) {
      json(response, 401, { error: 'unauthorized' });
      return;
    }
    try {
      const raw = await body(request, maxBytes);
      const parsed = JSON.parse(raw.toString('utf8')) as Record<string, unknown>;
      const document = validateRenderDocument(parsed.document);
      const video = await options.renderer(document);
      if (!Buffer.isBuffer(video) || video.length === 0) throw new Error('renderer returned no video');
      response.statusCode = 200;
      response.setHeader('content-type', 'video/mp4');
      response.setHeader('content-length', String(video.length));
      response.setHeader('cache-control', 'no-store');
      response.end(video);
    } catch (error) {
      const tooLarge = Boolean(error && typeof error === 'object' && 'tooLarge' in error);
      json(response, tooLarge ? 413 : 422, { error: tooLarge ? 'payload_too_large' : 'render_failed' });
    }
  });
}
