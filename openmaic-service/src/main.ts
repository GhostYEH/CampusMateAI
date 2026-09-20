import { ServiceAuthenticator } from './auth/authenticator.ts';
import { createArchiveRoutes } from './archive/routes.ts';
import { loadConfig, loadDotEnv } from './config.ts';
import { ServiceDatabase } from './db/database.ts';
import { SqliteReplayStore } from './db/replayStore.ts';
import { createDiscoveryRoutes } from './discovery/routes.ts';
import { createDiscussionRoutes } from './discussion/routes.ts';
import { createEditorRoutes } from './editor/routes.ts';
import { createMaterialRoutes } from './material/routes.ts';
import { createPlayerRoutes } from './player/routes.ts';
import { createJobRoutes } from './jobs/routes.ts';
import { JobRepository } from './jobs/repository.ts';
import { createGenerationRoutes } from './generation/routes.ts';
import { createProviderJobWorker } from './provider/worker.ts';
import { createWhiteboardRoutes } from './whiteboard/routes.ts';
import { createProviderRoutes } from './provider/routes.ts';
import { createServer } from './server.ts';
import { createWorkspaceRoutes } from './workspace/routes.ts';
import { WorkspaceRepository } from './workspace/repository.ts';
import { createTtsRoutes } from './tts/routes.ts';
import { createSceneNarrationRoutes } from './tts/scene-narration-routes.ts';

// Provider credentials may live in a local .env file next to the service;
// real environment variables still win.
loadDotEnv();

// Startup is fail-closed. A missing internal secret or database location stops
// the process instead of degrading into an unauthenticated or amnesiac service.
const config = loadConfig();

const database = new ServiceDatabase(config.databasePath);
const replayStore = new SqliteReplayStore(database);
const authenticator = new ServiceAuthenticator({ secret: config.internalSecret, replayStore });
const jobs = new JobRepository(database);
const workspaces = new WorkspaceRepository(database);
const worker = createProviderJobWorker({
  database,
  jobs,
  workspaces,
  provider: config.provider,
  tts: config.tts,
  render: config.render,
});

function databaseIsReady(): boolean {
  try {
    const row = database.raw.prepare('SELECT count(*) AS total FROM schema_migrations').get();
    return Number(row?.total ?? 0) > 0;
  } catch {
    return false;
  }
}

const server = createServer({
  authenticator,
  database,
  readiness: () => ({ runtime: true, database: databaseIsReady() }),
  // The advertised capability set is derived from these routes, so a capability
  // can never be reported before its handlers exist.
  routes: [
    ...createWorkspaceRoutes({ database }),
    ...createDiscoveryRoutes({ database }),
    ...createArchiveRoutes({ database, jobs, render: config.render }),
    ...createEditorRoutes({ database }),
    ...createMaterialRoutes({ database }),
    ...createPlayerRoutes({ database, capabilities: { externalCdnAvailable: Boolean(config.externalCdnUrl) } }),
    ...createJobRoutes({ database }),
    ...createGenerationRoutes({ database, provider: config.provider }),
    ...createWhiteboardRoutes({ database }),
    ...createProviderRoutes({ database, providers: {
      llm: Boolean(config.provider),
      webSearch: false,
      image: false,
      video: false,
      tts: Boolean(config.tts),
      render: Boolean(config.render),
      external3d: Boolean(config.externalCdnUrl),
    } }),
    ...createTtsRoutes({ database, tts: config.tts }),
    // 按场景的讲解音频。与上面的自由文本 `/tts` 并存：后者保持既有契约不动，
    // 前者才是"讲课"的入口——讲稿由服务端从场景正文派生，音频因此与页一一对应。
    ...createSceneNarrationRoutes({ database, workspaces, tts: config.tts }),
    ...createDiscussionRoutes({ database, provider: config.provider }),
  ],
});

server.on('error', (error) => {
  process.stderr.write(`OpenMAIC internal service failed to start: ${error.message}\n`);
  process.exitCode = 1;
});

let stopping = false;
async function shutdown() {
  if (stopping) return;
  stopping = true;
  await worker.stop();
  server.close(() => {
    database.close();
    process.exit(0);
  });
}

process.on('SIGINT', () => { void shutdown(); });
process.on('SIGTERM', () => { void shutdown(); });

server.listen(config.port, config.host, () => {
  worker.start();
  process.stdout.write(`OpenMAIC internal service listening on ${config.host}:${config.port}\n`);
});
