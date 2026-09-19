export interface RenderConfig {
  host: string;
  port: number;
  token: string;
  ffmpegPath: string;
  timeoutMs: number;
}

export class RenderConfigError extends Error {}

export function loadConfig(env: Record<string, string | undefined> = process.env): RenderConfig {
  const token = (env.RENDER_SERVICE_TOKEN ?? '').trim();
  if (!token) throw new RenderConfigError('RENDER_SERVICE_TOKEN is required');
  const port = Number(env.RENDER_SERVICE_PORT ?? 9000);
  if (!Number.isInteger(port) || port <= 0 || port > 65535) throw new RenderConfigError('RENDER_SERVICE_PORT must be a valid TCP port');
  const timeoutSeconds = Number(env.RENDER_SERVICE_TIMEOUT_SECONDS ?? 120);
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 600) throw new RenderConfigError('RENDER_SERVICE_TIMEOUT_SECONDS must be between 1 and 600');
  return {
    host: (env.RENDER_SERVICE_HOST ?? '127.0.0.1').trim() || '127.0.0.1',
    port,
    token,
    ffmpegPath: (env.FFMPEG_PATH ?? 'ffmpeg').trim() || 'ffmpeg',
    timeoutMs: timeoutSeconds * 1000,
  };
}
