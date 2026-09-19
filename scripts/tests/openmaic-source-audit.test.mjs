import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';

const repoRoot = new URL('../..', import.meta.url).pathname.replace(/^\//, '').replaceAll('/', '\\');
const script = join(repoRoot, 'scripts', 'openmaic-source-audit.ps1');

function run(command, args, cwd) {
  return spawnSync(command, args, { cwd, encoding: 'utf8', windowsHide: true });
}

function makeFixture() {
  const root = mkdtempSync(join(tmpdir(), 'openmaic-audit-fixture-'));
  for (const directory of [
    'app/api/health',
    'packages/@openmaic/dsl/src',
    'components/classroom',
    'render-service',
  ]) mkdirSync(join(root, directory), { recursive: true });
  writeFileSync(join(root, 'LICENSE'), 'MIT License\nCopyright (c) 2026 THU-MAIC\n');
  writeFileSync(join(root, 'app/api/health/route.ts'), 'export const GET = () => Response.json({ status: "ok" });\n');
  writeFileSync(join(root, 'packages/@openmaic/dsl/src/stage.ts'), 'export type SceneType = "slide" | "quiz" | "interactive" | "pbl";\n');
  writeFileSync(join(root, 'components/classroom/index.tsx'), 'export function Classroom() { return null; }\n');
  writeFileSync(join(root, 'render-service/package.json'), '{"name":"render-service"}\n');
  run('git', ['init', '--quiet'], root);
  run('git', ['config', 'user.email', 'test@example.invalid'], root);
  run('git', ['config', 'user.name', 'OpenMAIC audit test'], root);
  run('git', ['add', '.'], root);
  const commit = run('git', ['commit', '--quiet', '-m', 'fixture'], root);
  assert.equal(commit.status, 0, commit.stderr);
  const head = run('git', ['rev-parse', 'HEAD'], root).stdout.trim();
  return { root, head };
}

test('rejects a source without the pinned commit', () => {
  const fixture = makeFixture();
  const output = join(mkdtempSync(join(tmpdir(), 'openmaic-audit-output-')), 'audit');
  const result = run('pwsh', [
    '-NoProfile', '-File', script,
    '-Source', fixture.root,
    '-Output', output,
    '-ExpectedCommit', '0000000000000000000000000000000000000000',
  ], repoRoot);
  assert.notEqual(result.status, 0);
  assert.match(`${result.stdout}\n${result.stderr}`, /commit mismatch/i);
});

test('inventories every product surface before migration', () => {
  const fixture = makeFixture();
  const output = join(mkdtempSync(join(tmpdir(), 'openmaic-audit-output-')), 'audit');
  const result = run('pwsh', [
    '-NoProfile', '-File', script,
    '-Source', fixture.root,
    '-Output', output,
    '-ExpectedCommit', fixture.head,
  ], repoRoot);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  const inventory = JSON.parse(readFileSync(join(output, 'capability-inventory.json'), 'utf8'));
  assert.ok(inventory.routes.length > 0);
  assert.ok(inventory.packages.length > 0);
  assert.equal(inventory.unclassified.length, 0);
  assert.equal(JSON.parse(readFileSync(join(output, 'UPSTREAM.json'), 'utf8')).commit, fixture.head);
});
