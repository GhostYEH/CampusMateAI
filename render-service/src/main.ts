import { loadConfig } from './config.ts';
import { createFfmpegRenderer } from './renderer.ts';
import { createRenderServer } from './server.ts';

const config = loadConfig();
const server = createRenderServer({ token: config.token, renderer: createFfmpegRenderer(config) });
server.on('error', (error) => { process.stderr.write(`render-service failed: ${error.message}\n`); process.exitCode = 1; });
server.listen(config.port, config.host, () => {
  process.stdout.write(`render-service listening on ${config.host}:${config.port}\n`);
});
