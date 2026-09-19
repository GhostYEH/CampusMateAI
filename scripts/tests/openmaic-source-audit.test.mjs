import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';

import { audit, buildNotice, capabilityMapping } from '../openmaic-source-audit.mjs';

const repoRoot = new URL('../..', import.meta.url).pathname.replace(/^\//, '').replaceAll('/', '\\');
const wrapper = join(repoRoot, 'scripts', 'openmaic-source-audit.ps1');

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

function makeOutput() {
  return join(mkdtempSync(join(tmpdir(), 'openmaic-audit-output-')), 'audit');
}

function normalize(text) {
  return String(text).replaceAll('\r\n', '\n').replace(/\n+$/, '');
}

test('rejects a source without the pinned commit', () => {
  const fixture = makeFixture();
  assert.throws(
    () => audit({ source: fixture.root, output: makeOutput(), expectedCommit: '0'.repeat(40) }),
    /commit mismatch/i,
  );
});

test('refuses to write the audit inside the source checkout', () => {
  const fixture = makeFixture();
  assert.throws(
    () => audit({ source: fixture.root, output: join(fixture.root, 'audit'), expectedCommit: fixture.head }),
    /must not be inside the source checkout/i,
  );
});

test('inventories every product surface before migration', () => {
  const fixture = makeFixture();
  const output = makeOutput();
  audit({ source: fixture.root, output, expectedCommit: fixture.head });

  const inventory = JSON.parse(readFileSync(join(output, 'capability-inventory.json'), 'utf8'));
  assert.ok(inventory.routes.length > 0);
  assert.ok(inventory.packages.length > 0);
  assert.equal(inventory.unclassified.length, 0);
  assert.equal(inventory.source.commit, fixture.head);
  assert.equal(JSON.parse(readFileSync(join(output, 'UPSTREAM.json'), 'utf8')).commit, fixture.head);

  const manifest = readFileSync(join(output, 'source-manifest.sha256'), 'utf8');
  assert.match(manifest, /^[0-9a-f]{64} {2}LICENSE$/m);
  // Credential-shaped and vendored paths never enter the manifest.
  assert.equal(/node_modules|\.env|\.pem|\.key/.test(manifest), false);
});

test('resolves the provenance notice instead of leaking placeholders', () => {
  const fixture = makeFixture();
  const output = makeOutput();
  audit({ source: fixture.root, output, expectedCommit: fixture.head });

  const notice = normalize(readFileSync(join(output, 'NOTICE.md'), 'utf8'));
  assert.equal(
    notice,
    [
      '# OpenMAIC provenance notice',
      '',
      'This directory records the audited source boundary for OpenMAIC `v1.0.3`.',
      '',
      '- Repository: `https://github.com/THU-MAIC/OpenMAIC.git`',
      '- Tag: `v1.0.3`',
      `- Commit: \`${fixture.head}\``,
      '- License: MIT; see `LICENSE`.',
      '- The source checkout itself, package managers, build output, runtime data, logs, credentials and local configuration are not vendored here.',
    ].join('\n'),
  );
  for (const placeholder of ['$Tag', '$Repository', '$actualCommit']) {
    assert.equal(notice.includes(placeholder), false, `NOTICE.md leaked ${placeholder}`);
  }
});

test('honours an overridden repository and tag in the notice', () => {
  const fixture = makeFixture();
  const output = makeOutput();
  audit({
    source: fixture.root,
    output,
    expectedCommit: fixture.head,
    repository: 'https://example.invalid/OpenMAIC.git',
    tag: 'v9.9.9',
  });
  const notice = normalize(readFileSync(join(output, 'NOTICE.md'), 'utf8'));
  assert.match(notice, /boundary for OpenMAIC `v9\.9\.9`\./);
  assert.match(notice, /- Repository: `https:\/\/example\.invalid\/OpenMAIC\.git`/);
  assert.equal(notice.includes('$Tag'), false);
});

test('buildNotice never returns an unresolved placeholder', () => {
  const notice = buildNotice({ tag: 'v1.0.3', repository: 'https://example.invalid/r.git', commit: 'a'.repeat(40) });
  assert.equal(/\$[A-Za-z]/.test(notice), false);
  assert.match(notice, /`a{40}`/);
});

test('capability mapping classifies the audited surfaces', () => {
  assert.equal(capabilityMapping('app/api/stages/route.ts'), 'workspace/stage');
  assert.equal(capabilityMapping('packages/@openmaic/dsl/src/stage.ts'), 'dsl');
  assert.equal(capabilityMapping('components/classroom/index.tsx'), 'player');
  assert.equal(capabilityMapping('render-service/src/main.ts'), 'render-service');
  assert.equal(capabilityMapping('README.md'), null);
});

// The wrapper only exists for hosts that call the audit through PowerShell. It is
// skipped rather than failed when the host cannot spawn child processes at all.
function powerShellCanSpawnChildren() {
  for (const host of process.platform === 'win32' ? ['pwsh', 'powershell'] : ['pwsh']) {
    const probe = run(host, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', '& node --version'], repoRoot);
    if (probe.status === 0 && /^v\d+\./.test(String(probe.stdout).trim())) return host;
  }
  return null;
}

const wrapperHost = powerShellCanSpawnChildren();

test(
  'the PowerShell entry point forwards to the audit implementation',
  { skip: wrapperHost ? false : 'no PowerShell host that can spawn child processes' },
  () => {
    const fixture = makeFixture();
    const output = makeOutput();
    const result = run(wrapperHost, [
      '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', wrapper,
      '-Source', fixture.root,
      '-Output', output,
      '-ExpectedCommit', fixture.head,
    ], repoRoot);
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    assert.match(readFileSync(join(output, 'NOTICE.md'), 'utf8'), /Commit: `[0-9a-f]{40}`/);
  },
);
