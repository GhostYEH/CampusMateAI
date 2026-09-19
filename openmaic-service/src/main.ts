import { ServiceAuthenticator } from './auth/authenticator.ts';
import { loadConfig } from './config.ts';
import { ServiceDatabase } from './db/database.ts';
import { SqliteReplayStore } from './db/replayStore.ts';
import { createServer } from './server.ts';

// Startup is fail-closed. A missing internal secret or database location stops
// the process instead of degrading into an unauthenticated or amnesiac service.
const config = loadConfig();

const database = new ServiceDatabase(config.databasePath);
const replayStore = new SqliteReplayStore(database);
const authenticator = new ServiceAuthenticator({ secret: config.internalSecret, replayStore });

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
  routes: [],
});

server.on('error', (error) => {
  process.stderr.write(`OpenMAIC internal service failed to start: ${error.message}\n`);
  process.exitCode = 1;
});

function shutdown() {
  server.close(() => {
    database.close();
    process.exit(0);
  });
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

server.listen(config.port, config.host, () => {
  process.stdout.write(`OpenMAIC internal service listening on ${config.host}:${config.port}\n`);
});
