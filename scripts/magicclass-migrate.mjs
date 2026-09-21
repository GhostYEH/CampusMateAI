#!/usr/bin/env node
/**
 * Rebrand every versioned legacy contract without turning identifiers into
 * invalid display text. Human-facing content uses "magic class"; source
 * identifiers, file names, package names, and environment keys use valid
 * magicclass/magicclass/MAGICCLASS spellings.
 */
import { execFileSync } from 'node:child_process';
import {
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from 'node:fs';
import { dirname, join, posix, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = dirname(dirname(fileURLToPath(import.meta.url)));
const LEGACY_LOWER = ['open', 'maic'].join('');
const LEGACY_UPPER = LEGACY_LOWER.toUpperCase();
const LEGACY_TITLE = `${LEGACY_LOWER.slice(0, 1).toUpperCase()}${LEGACY_LOWER.slice(1, 4)}${LEGACY_UPPER.slice(4)}`;
const LEGACY_PUNCTUATED = ['magic', "'class"].join('');
const LEGACY_APP_DIR = `${LEGACY_LOWER}-app`;

export const DISPLAY_BRAND = 'magic class';
export const PACKAGE_BRAND = 'magicclass';
export const IDENTIFIER_BRAND = ['Magic', 'Class'].join('');
const UPPER_BRAND = PACKAGE_BRAND.toUpperCase();

const LEGACY_TOKEN_RE = new RegExp(LEGACY_LOWER, 'gi');
const TEXT_EXTENSIONS = new Set([
  '.bat', '.cjs', '.css', '.env', '.html', '.ini', '.java', '.js', '.json', '.jsx',
  '.kt', '.md', '.mdx', '.mjs', '.properties', '.ps1', '.py', '.sh', '.snap',
  '.sha256', '.sql', '.svg', '.toml', '.ts', '.tsx', '.txt', '.xml', '.yaml', '.yml',
]);
const TEXT_NAMES = new Set([
  '.dockerignore', '.env.example', '.gitignore', '.npmrc', 'Dockerfile', 'LICENSE',
  'NOTICE', 'README', 'README.md', 'SECURITY',
]);
const CODE_EXTENSIONS = new Set(['.cjs', '.java', '.js', '.jsx', '.kt', '.mjs', '.py', '.ts', '.tsx']);

function toFsPath(repoPath) {
  return join(REPO, repoPath.split('/').join(sep));
}

function basename(repoPath) {
  return posix.basename(repoPath);
}

function dirnamePath(repoPath) {
  return posix.dirname(repoPath);
}

function isTextPath(repoPath) {
  const name = basename(repoPath);
  if (TEXT_NAMES.has(name)) return true;
  const dot = name.lastIndexOf('.');
  return dot >= 0 && TEXT_EXTENSIONS.has(name.slice(dot).toLowerCase());
}

function isCodePath(repoPath) {
  const name = basename(repoPath);
  const dot = name.lastIndexOf('.');
  return dot >= 0 && CODE_EXTENSIONS.has(name.slice(dot).toLowerCase());
}

function isBinary(buffer) {
  return buffer.subarray(0, Math.min(buffer.length, 8192)).includes(0);
}

function trackedPaths() {
  return execFileSync('git', ['ls-files', '-z'], { cwd: REPO }).toString('utf8').split('\0').filter(Boolean);
}

/** Normalize names first, reserving the spaced spelling for display surfaces. */
export function replaceTechnicalTokens(value) {
  return String(value)
    .split(LEGACY_PUNCTUATED).join(DISPLAY_BRAND)
    .replace(LEGACY_TOKEN_RE, (match) => {
      if (match === LEGACY_UPPER) return UPPER_BRAND;
      if (match === LEGACY_LOWER) return PACKAGE_BRAND;
      return IDENTIFIER_BRAND;
    });
}

/** Paths must never contain the display spelling. */
export function replaceBrandPath(value) {
  return replaceTechnicalTokens(value)
    .split(IDENTIFIER_BRAND).join(PACKAGE_BRAND)
    .split(DISPLAY_BRAND).join(PACKAGE_BRAND);
}

function replaceDisplaySurface(value) {
  return String(value)
    .replace(new RegExp(`${IDENTIFIER_BRAND}(?=[/.])`, 'g'), PACKAGE_BRAND)
    .replace(new RegExp(`(^|[^A-Za-z0-9_$@./-])${IDENTIFIER_BRAND}(?=$|[^A-Za-z0-9_$@./-])`, 'g'), `$1${DISPLAY_BRAND}`);
}

function replaceQuotedSegment(value) {
  // Module/file references must follow the renamed, no-space paths.
  if (/[\\/]/.test(value) || /\.[A-Za-z0-9]+$/.test(value)) {
    return value.split(IDENTIFIER_BRAND).join(PACKAGE_BRAND);
  }
  return replaceDisplaySurface(value);
}

/** Rewrite quoted user copy and comments but keep executable identifiers valid. */
function replaceCodeDisplayTokens(text) {
  let result = '';
  let index = 0;
  while (index < text.length) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '/' && next === '/') {
      const end = text.indexOf('\n', index);
      const stop = end < 0 ? text.length : end;
      result += replaceDisplaySurface(text.slice(index, stop));
      index = stop;
      continue;
    }
    if (char === '/' && next === '*') {
      const end = text.indexOf('*/', index + 2);
      const stop = end < 0 ? text.length : end + 2;
      result += replaceDisplaySurface(text.slice(index, stop));
      index = stop;
      continue;
    }
    if (char === '#') {
      const end = text.indexOf('\n', index);
      const stop = end < 0 ? text.length : end;
      result += replaceDisplaySurface(text.slice(index, stop));
      index = stop;
      continue;
    }
    if (char === '"' || char === "'") {
      let cursor = index + 1;
      while (cursor < text.length) {
        if (text[cursor] === '\\') { cursor += 2; continue; }
        if (text[cursor] === char) break;
        cursor += 1;
      }
      if (cursor < text.length) {
        result += char + replaceQuotedSegment(text.slice(index + 1, cursor)) + char;
        index = cursor + 1;
        continue;
      }
    }
    result += char;
    index += 1;
  }
  // JSX text nodes are not quoted JavaScript strings.
  return result.replace(/>([^<{]*)</g, (_, content) => `>${replaceDisplaySurface(content)}<`);
}

export function replaceBrandContent(repoPath, value) {
  const technical = replaceTechnicalTokens(value);
  if (isCodePath(repoPath)) return replaceCodeDisplayTokens(technical);
  return replaceDisplaySurface(technical);
}

function parentDirectories(repoPath) {
  const result = [];
  let current = dirnamePath(repoPath);
  while (current && current !== '.') {
    result.push(current);
    current = dirnamePath(current);
  }
  return result;
}

function depth(repoPath) {
  return repoPath.split('/').length;
}

function moveLockedAppContents(source, destination) {
  if (!existsSync(destination)) mkdirSync(destination);
  const blocked = [];
  for (const entry of readdirSync(source)) {
    const from = join(source, entry);
    const to = join(destination, entry);
    if (existsSync(to)) {
      if (entry === 'node_modules') continue;
      throw new Error(`路径续跑冲突：${from} -> ${to}`);
    }
    try {
      renameSync(from, to);
    } catch (error) {
      if (entry === 'node_modules' && error?.code === 'EPERM') blocked.push(entry);
      else throw error;
    }
  }
  return blocked;
}

function renameTrackedPaths(paths) {
  const changes = [];
  const directories = new Set(paths.flatMap(parentDirectories));
  for (const oldPath of [...directories]
    .filter((entry) => replaceBrandPath(basename(entry)) !== basename(entry))
    .sort((left, right) => depth(left) - depth(right))) {
    const oldName = basename(oldPath);
    const parent = replaceBrandPath(dirnamePath(oldPath));
    const source = join(toFsPath(parent), oldName);
    const nextPath = replaceBrandPath(oldPath);
    const destination = toFsPath(nextPath);
    if (!existsSync(source)) continue;
    if (existsSync(destination)) {
      if (oldPath === LEGACY_APP_DIR) {
        moveLockedAppContents(source, destination);
        if (readdirSync(source).every((entry) => entry === 'node_modules')) continue;
      }
      throw new Error(`目录重命名冲突：${oldPath} -> ${nextPath}`);
    }
    try {
      renameSync(source, destination);
      changes.push(`${oldPath}/ -> ${nextPath}/`);
    } catch (error) {
      if (error?.code !== 'EPERM' || oldPath !== LEGACY_APP_DIR) throw error;
      const blocked = moveLockedAppContents(source, destination);
      changes.push(`${oldPath}/ -> ${nextPath}/（${blocked.length ? '依赖缓存待重建' : '已迁移'}）`);
    }
  }

  for (const oldPath of paths) {
    const oldName = basename(oldPath);
    const newName = replaceBrandPath(oldName);
    if (oldName === newName) continue;
    const source = join(toFsPath(replaceBrandPath(dirnamePath(oldPath))), oldName);
    const destination = toFsPath(replaceBrandPath(oldPath));
    if (!existsSync(source)) continue;
    if (existsSync(destination)) throw new Error(`文件重命名冲突：${oldPath}`);
    renameSync(source, destination);
    changes.push(`${oldPath} -> ${replaceBrandPath(oldPath)}`);
  }
  return changes;
}

function writeWithRetry(file, content) {
  const delays = [0, 60, 180, 500, 1200];
  let lastError;
  for (const delay of delays) {
    if (delay) Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, delay);
    try {
      writeFileSync(file, content, 'utf8');
      return;
    } catch (error) {
      lastError = error;
      if (!['EBUSY', 'EPERM', 'UNKNOWN'].includes(error?.code)) throw error;
    }
  }
  throw lastError;
}

function rewriteTrackedFiles(paths) {
  const changes = [];
  for (const path of new Set(paths.map(replaceBrandPath))) {
    if (!isTextPath(path)) continue;
    const file = toFsPath(path);
    if (!existsSync(file) || !lstatSync(file).isFile()) continue;
    const raw = readFileSync(file);
    if (isBinary(raw)) continue;
    const next = replaceBrandContent(path, raw.toString('utf8'));
    if (next === raw.toString('utf8')) continue;
    writeWithRetry(file, next);
    changes.push(path);
  }
  return changes;
}

function containsLegacyToken(value) {
  LEGACY_TOKEN_RE.lastIndex = 0;
  return value.includes(LEGACY_PUNCTUATED) || LEGACY_TOKEN_RE.test(value);
}

export function check() {
  const problems = [];
  for (const indexedPath of trackedPaths()) {
    const path = replaceBrandPath(indexedPath);
    const file = toFsPath(path);
    if (!existsSync(file) || !lstatSync(file).isFile()) {
      problems.push(`缺少迁移后的文件：${path}`);
      continue;
    }
    if (!isTextPath(path)) continue;
    const raw = readFileSync(file);
    if (!isBinary(raw) && containsLegacyToken(raw.toString('utf8'))) problems.push(`仍有旧名称：${path}`);
  }
  return problems;
}

function main(mode) {
  if (!['apply', 'check'].includes(mode)) {
    console.error('用法：node scripts/magicclass-migrate.mjs <apply|check>');
    return 2;
  }
  if (mode === 'apply') {
    const paths = trackedPaths();
    const renamed = renameTrackedPaths(paths);
    const rewritten = rewriteTrackedFiles(paths);
    console.log(`已重命名 ${renamed.length} 个路径，重写 ${rewritten.length} 个文本文件`);
  }
  const problems = check();
  if (problems.length === 0) {
    console.log('magic class 迁移自检通过');
    return 0;
  }
  console.error(`迁移未完成（${problems.length} 项）：`);
  for (const problem of problems.slice(0, 30)) console.error(`  - ${problem}`);
  return 1;
}

if (process.argv[1]?.endsWith('magicclass-migrate.mjs')) process.exitCode = main(process.argv[2]);
