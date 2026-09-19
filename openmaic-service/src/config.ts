export interface ServiceConfig {
  host: string;
  port: number;
  databaseUrl: string;
  internalSecret: string;
}

function positiveInteger(value: string | undefined, fallback: number) {
  const parsed = Number(value ?? fallback);
  if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 65535) {
    throw new Error('OPENMAIC_PORT must be a valid TCP port');
  }
  return parsed;
}

export function loadConfig(env = process.env): ServiceConfig {
  return {
    host: env.OPENMAIC_HOST?.trim() || '127.0.0.1',
    port: positiveInteger(env.OPENMAIC_PORT, 4010),
    databaseUrl: env.OPENMAIC_DATABASE_URL?.trim() || '',
    internalSecret: env.OPENMAIC_INTERNAL_SECRET?.trim() || '',
  };
}
