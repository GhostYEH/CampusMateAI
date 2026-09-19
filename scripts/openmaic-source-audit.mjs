#!/usr/bin/env node
/**
 * OpenMAIC source audit.
 *
 * Walks a pinned OpenMAIC checkout, hashes every auditable file and emits the
 * provenance artefacts under `third_party/openmaic/`: the provenance notice, the
 * SHA-256 manifest, the capability inventory and the upstream record.
 *
 * This is implemented in Node rather than PowerShell because Node `>=22.19.0` is
 * already a hard requirement for the managed service, so the audit stays
 * runnable on every host and CI image that can run the service itself. The
 * PowerShell entry point of the same name forwards to this file.
 *
 * Usage:
 *   node scripts/openmaic-source-audit.mjs \
 *     --source <checkout> --output <dir> --expected-commit <sha> \
 *     [--repository <url>] [--tag <tag>]
 */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFileSync, lstatSync, mkdirSync, readdirSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

export const DEFAULT_REPOSITORY = 'https://github.com/THU-MAIC/OpenMAIC.git';
export const DEFAULT_TAG = 'v1.0.3';

const EXCLUDED = /(^|\/)(\.git|node_modules|\.next|data|logs?)(\/|$)|(^|\/)(\.env($|\.)|.*\.(pem|key))/;

export function parseArguments(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) throw new Error(`Unexpected argument: ${token}`);
    const key = token.slice(2);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith('--')) throw new Error(`Missing value for --${key}`);
    values[key] = value;
    index += 1;
  }
  const { source, output } = values;
  const expectedCommit = values['expected-commit'];
  if (!source || !output || !expectedCommit) {
    throw new Error('--source, --output and --expected-commit are required');
  }
  return {
    source,
    output,
    expectedCommit,
    repository: values.repository ?? DEFAULT_REPOSITORY,
    tag: values.tag ?? DEFAULT_TAG,
  };
}

/** Maps one upstream path onto the CampusMate capability it will be migrated for. */
export function capabilityMapping(relativePath) {
  if (/^app\/api\//.test(relativePath)) {
    if (/\/(stages|stage-meta)\//.test(relativePath)) return 'workspace/stage';
    if (/\/(classroom|generate-classroom)\//.test(relativePath)) return 'generation/player';
    if (/\/(folders)\//.test(relativePath)) return 'folders';
    if (/\/(materials|extract-document|parse-pdf)\//.test(relativePath)) return 'materials';
    if (/\/(generate|pbl)\//.test(relativePath)) return 'generation';
    if (/\/(chat|agent)\//.test(relativePath)) return 'chat/multi-agent';
    if (/\/(web-search)\//.test(relativePath)) return 'web-search';
    if (/\/(provider|server-providers)\//.test(relativePath)) return 'provider-capabilities';
    if (/\/(export-video)\//.test(relativePath)) return 'video-export';
    if (/\/health\//.test(relativePath)) return 'health';
    if (/\/access-code\//.test(relativePath)) return 'service-auth';
    return 'campusmate-equivalent';
  }
  if (/^packages\/@openmaic\/dsl\//.test(relativePath)) return 'dsl';
  if (/^packages\/@openmaic\/(renderer|editor)\//.test(relativePath)) return 'editor/player';
  if (/^packages\/@openmaic\/(importer|storage)\//.test(relativePath)) return 'import/export';
  if (/^packages\/@openmaic\/generation\//.test(relativePath)) return 'generation';
  if (/^packages\/(pptxgenjs|mathml2omml)\//.test(relativePath)) return 'import/export';
  if (/^packages\//.test(relativePath)) return 'campusmate-equivalent';
  if (/^components\/(discovery|workbench)\//.test(relativePath)) return 'homepage/workspace';
  if (/^components\/(classroom|scene-renderers|stage)\//.test(relativePath)) return 'player';
  if (/^components\/(edit)\//.test(relativePath)) return 'editor';
  if (/^components\/(whiteboard|roundtable|audio)\//.test(relativePath)) return 'whiteboard/tts/multi-agent';
  if (/^components\//.test(relativePath)) return 'campusmate-equivalent';
  if (/^render-service\//.test(relativePath)) return 'render-service';
  if (/^skills\//.test(relativePath)) return 'provider-capabilities';
  return null;
}

function toPosix(value) {
  return value.split(sep).join('/');
}

/**
 * Collects every auditable file. Symlinked directories are not traversed (they
 * would let a checkout escape itself or loop), but a symlinked file is included
 * after proving its target stays inside the checkout.
 */
export function collectFiles(root) {
  const prefix = root.endsWith(sep) ? root : root + sep;
  const collected = [];
  const visit = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const full = join(directory, entry.name);
      const rel = toPosix(relative(root, full));
      if (EXCLUDED.test(rel)) continue;
      if (entry.isSymbolicLink()) {
        const target = realpathSync(full);
        if (!target.startsWith(prefix)) throw new Error(`Source symlink escapes checkout: ${rel}`);
        if (lstatSync(target).isDirectory()) continue;
        collected.push({ path: rel, sha256: sha256Of(full) });
        continue;
      }
      if (entry.isDirectory()) {
        visit(full);
        continue;
      }
      if (!entry.isFile()) continue;
      collected.push({ path: rel, sha256: sha256Of(full) });
    }
  };
  visit(root);
  collected.sort((left, right) => (left.path < right.path ? -1 : left.path > right.path ? 1 : 0));
  return collected;
}

function sha256Of(file) {
  return createHash('sha256').update(readFileSync(file)).digest('hex');
}

export function buildNotice({ tag, repository, commit }) {
  return [
    '# OpenMAIC provenance notice',
    '',
    `This directory records the audited source boundary for OpenMAIC \`${tag}\`.`,
    '',
    `- Repository: \`${repository}\``,
    `- Commit: \`${commit}\``,
    '- License: MIT; see `LICENSE`.',
    '- The source checkout itself, package managers, build output, runtime data, logs, credentials and local configuration are not vendored here.',
    '',
  ].join('\n');
}

export function audit({ source, output, expectedCommit, repository = DEFAULT_REPOSITORY, tag = DEFAULT_TAG }) {
  const sourcePath = resolve(source);
  if (lstatSync(sourcePath, { throwIfNoEntry: false })?.isDirectory() !== true) {
    throw new Error(`OpenMAIC source directory does not exist: ${source}`);
  }
  const outputPath = resolve(output);
  if (outputPath === sourcePath || outputPath.startsWith(sourcePath + sep)) {
    throw new Error('Audit output must not be inside the source checkout');
  }

  const actualCommit = execFileSync('git', ['-C', sourcePath, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  if (actualCommit !== expectedCommit) {
    throw new Error(`OpenMAIC source commit mismatch: expected ${expectedCommit}, got ${actualCommit}`);
  }

  const licensePath = join(sourcePath, 'LICENSE');
  if (lstatSync(licensePath, { throwIfNoEntry: false })?.isFile() !== true) {
    throw new Error('OpenMAIC LICENSE is missing');
  }

  const files = collectFiles(sourcePath);

  const routes = files
    .filter((file) => /^app\/api\/.+\.(ts|tsx)$/.test(file.path))
    .map((file) => ({ path: file.path, mapping: capabilityMapping(file.path) }));
  const prefixesOf = (regex) =>
    [...new Set(files.map((file) => regex.exec(file.path)?.[1]).filter(Boolean))].sort();
  const packages = prefixesOf(/^(packages\/(?:[^/]+\/)?[^/]+)/).map((path) => ({
    path,
    mapping: capabilityMapping(`${path}/`),
  }));
  const components = prefixesOf(/^(components\/[^/]+)/).map((path) => ({
    path,
    mapping: capabilityMapping(`${path}/`),
  }));

  const unclassified = [...routes, ...packages, ...components].filter((entry) => !entry.mapping);
  if (unclassified.length > 0) {
    throw new Error(`Unclassified OpenMAIC surfaces: ${unclassified.map((entry) => entry.path).join(', ')}`);
  }

  const notice = buildNotice({ tag, repository, commit: actualCommit });
  // Guard the exact defect this script previously shipped: a template that
  // leaked `$Tag`/`$Repository`/`$actualCommit` into the committed notice.
  if (/\$[A-Za-z]/.test(notice)) throw new Error('Generated NOTICE.md still contains an unexpanded placeholder');
  for (const expected of [repository, tag, actualCommit]) {
    if (!notice.includes(expected)) throw new Error(`Generated NOTICE.md is missing the resolved value: ${expected}`);
  }

  mkdirSync(outputPath, { recursive: true });
  writeFileSync(
    join(outputPath, 'source-manifest.sha256'),
    `${files.map((file) => `${file.sha256}  ${file.path}`).join('\r\n')}\r\n`,
    'utf8',
  );
  copyFileSync(licensePath, join(outputPath, 'LICENSE'));
  writeFileSync(join(outputPath, 'NOTICE.md'), notice, 'utf8');
  writeFileSync(
    join(outputPath, 'capability-inventory.json'),
    `${JSON.stringify(
      {
        source: { repository, tag, commit: actualCommit },
        routes,
        packages,
        components,
        renderService: files
          .filter((file) => /^render-service\//.test(file.path))
          .map((file) => ({ path: file.path, mapping: 'render-service' })),
        skills: files
          .filter((file) => /^skills\//.test(file.path))
          .map((file) => ({ path: file.path, mapping: 'provider-capabilities' })),
        unclassified,
      },
      null,
      2,
    )}\n`,
    'utf8',
  );
  writeFileSync(
    join(outputPath, 'UPSTREAM.json'),
    `${JSON.stringify({ repository, tag, commit: actualCommit, auditedAt: new Date().toISOString(), files }, null, 2)}\n`,
    'utf8',
  );

  return { files: files.length, commit: actualCommit };
}

const invokedDirectly = process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  try {
    const result = audit(parseArguments(process.argv.slice(2)));
    process.stdout.write(`Audited ${result.files} files at ${result.commit}\n`);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  }
}
