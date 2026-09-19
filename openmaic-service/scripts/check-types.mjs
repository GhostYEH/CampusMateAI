import { readdirSync, statSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { stripTypeScriptTypes } from 'node:module';

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

// `node --check` parses the file as-is and does NOT run the type-stripping
// transform, so checking a `.ts` file directly reports syntax errors for plain
// TypeScript. Strip first (the same transform the runtime applies), then check
// the emitted JavaScript — otherwise this script either rejects valid sources or
// silently proves nothing.
const scratch = mkdtempSync(join(tmpdir(), 'openmaic-types-'));
let failed = false;

try {
  for (const file of files) {
    const source = readFileSync(file, 'utf8');
    if (source.trim().length === 0) {
      console.error(`Refusing to accept an empty source file: ${file}`);
      process.exit(1);
    }
    let emitted;
    try {
      emitted = stripTypeScriptTypes(source, { mode: 'strip' });
    } catch (error) {
      console.error(`Type-strip failed: ${file}`);
      console.error(error instanceof Error ? error.message : String(error));
      failed = true;
      break;
    }
    const scratchFile = join(scratch, `${files.indexOf(file)}.mjs`);
    writeFileSync(scratchFile, emitted, 'utf8');
    const result = spawnSync(process.execPath, ['--check', scratchFile], {
      stdio: 'inherit',
      windowsHide: true,
    });
    if (result.status !== 0) {
      console.error(`Syntax check failed: ${file}`);
      failed = true;
      break;
    }
  }
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

if (failed) process.exit(1);
console.log(`Checked ${files.length} TypeScript source files.`);
