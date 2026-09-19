import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const sourceRoot = new URL('../src/', import.meta.url);
const sourcePath = sourceRoot.pathname.replace(/^\//, '').replaceAll('/', '\\');
const files = readdirSync(sourcePath).filter((file) => file.endsWith('.ts'));

for (const file of files) {
  const result = spawnSync(process.execPath, ['--experimental-strip-types', '--check', join(sourcePath, file)], {
    stdio: 'inherit',
    windowsHide: true,
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
