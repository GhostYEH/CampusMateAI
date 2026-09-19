import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const sourceRoot = fileURLToPath(new URL('../src/', import.meta.url));

/** Walk `src/` recursively so nested modules are checked, not just top-level files. */
function collectTypeScriptFiles(directory) {
  const found = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const full = join(directory, entry.name);
    if (entry.isDirectory()) {
      found.push(...collectTypeScriptFiles(full));
    } else if (entry.isFile() && (entry.name.endsWith('.ts') || entry.name.endsWith('.mts'))) {
      found.push(full);
    }
  }
  return found;
}

const files = collectTypeScriptFiles(sourceRoot).sort();
if (files.length === 0) {
  console.error(`No TypeScript sources found under ${sourceRoot}`);
  process.exit(1);
}

for (const file of files) {
  if (statSync(file).size === 0) {
    console.error(`Refusing to accept an empty source file: ${file}`);
    process.exit(1);
  }
  const result = spawnSync(process.execPath, ['--experimental-strip-types', '--check', file], {
    stdio: 'inherit',
    windowsHide: true,
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

console.log(`Checked ${files.length} TypeScript source files.`);
