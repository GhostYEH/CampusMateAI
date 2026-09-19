import { createServer } from './server.ts';
import { loadConfig } from './config.ts';

const config = loadConfig();
const server = createServer({
  readiness: async () => ({
    runtime: true,
    database: Boolean(config.databaseUrl),
  }),
});

server.listen(config.port, config.host, () => {
  process.stdout.write(`OpenMAIC internal service listening on ${config.host}:${config.port}\n`);
});
