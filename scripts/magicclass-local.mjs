#!/usr/bin/env node
/**
 * CampusMate 本地受管 magic class 的启动与诊断入口（从仓库根目录执行）。
 *
 *   node scripts/magicclass-local.mjs env      生成/补齐本地 .env（幂等，不改你已有的项）
 *   node scripts/magicclass-local.mjs doctor   体检：依赖、配置、端口、健康端点
 *   node scripts/magicclass-local.mjs start    依次拉起四服务，全部就绪后才打印入口
 *
 * 四个进程的边界必须分清，混用会得到"看起来在跑但永远 503"：
 *
 *   Vite 5174  →  FastAPI 8000  →  magicclass-service 4010
 *   magicclass-app 3000（导航栏「学习空间」承载的上游应用，独立 Origin）
 *
 * 注意三套地址是**三套东西**，不要互相顶替：
 * - `MAGICCLASS_SERVICE_URL`（默认 4010）是仓库内自研受管服务，融合链路只看它；
 * - `MAGICCLASS_BASE_URL`（默认 3000）是上游应用的**内部**地址，只有服务端可见；
 * - `MAGICCLASS_EMBED_ORIGIN`（默认 3000）是同一个上游应用的**浏览器公开**地址，
 *   经「学习空间」页做跨源内嵌。生产部署下后两者必然不同。
 *
 * 本脚本不写入任何密钥到版本库：密钥只落在被 .gitignore 忽略的 .env 里。
 */
import { spawn } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const BACKEND_DIR = path.join(REPO, 'backend');
const SERVICE_DIR = path.join(REPO, 'magicclass-service');
const APP_DIR = path.join(REPO, 'magicclass-app');
const WEB_DIR = path.join(REPO, 'webreact');

const BACKEND_ENV = path.join(BACKEND_DIR, '.env');
const SERVICE_ENV = path.join(SERVICE_DIR, '.env');
const SERVICE_ENV_EXAMPLE = path.join(SERVICE_DIR, '.env.example');

const BACKEND_PORT = Number(process.env.CAMPUSMATE_BACKEND_PORT || 8000);
const SERVICE_PORT = Number(process.env.CAMPUSMATE_MAGICCLASS_PORT || 4010);
const APP_PORT = Number(process.env.CAMPUSMATE_LEARNING_SPACE_PORT || 3000);
const WEB_PORT = Number(process.env.CAMPUSMATE_WEB_PORT || 5174);
// `start_all.bat` is a local development entry point and its login screen
// advertises the seeded student account. Keep both sides truthful by seeding
// that account unless the caller explicitly opts out for a real-user database.
const AUTO_SEED_DEMO_USERS = process.env.CAMPUSMATE_AUTO_SEED_DEMO_USERS ?? 'true';
const MIN_NODE = [22, 19, 0];
const LEGACY_ENV_PREFIX = `${['OPEN', 'MAIC'].join('')}_`;
const CURRENT_ENV_PREFIX = 'MAGICCLASS_';

/**
 * 允许把上游应用放进 iframe 的父页面 Origin，喂给上游的 ALLOWED_FRAME_ANCESTORS。
 *
 * 上游默认发 `X-Frame-Options: SAMEORIGIN` + `frame-ancestors 'self'`，而「学习空间」
 * 恰恰是**跨源**内嵌：不放行的话浏览器会直接拒掉 iframe，页面一片空白且没有报错。
 * 列两个 Origin，是因为 Vite 只绑 127.0.0.1，而用户完全可能用 localhost 打开本站
 * ——`http://127.0.0.1:5174` 与 `http://localhost:5174` 在浏览器眼里是两个 Origin。
 */
const APP_FRAME_ANCESTORS = `http://127.0.0.1:${WEB_PORT} http://localhost:${WEB_PORT}`;

/**
 * 入库应用的版本号，来自它自己的 package.json。
 *
 * 上游 `/api/health` 用 `process.env.npm_package_version || '0.1.0'` 自报版本，
 * 而 `npm_package_version` 只有经 npm/pnpm 启动才存在。我们直接用 node 调 next
 * 二进制，所以必须自己补上：否则健康端点回 `0.1.0`，落在后端
 * `magicclass_allowed_versions`（默认 `>=1.0.0 <2.0.0`）之外，「学习空间」会以
 * "版本不一致"为由拒绝加载——页面报错，但原因和真实问题（少了一个环境变量）无关。
 */
function appVersion() {
  const manifest = path.join(APP_DIR, 'package.json');
  if (!existsSync(manifest)) return '';
  return JSON.parse(readFileSync(manifest, 'utf8')).version || '';
}

/** 融合链路必需的三个键。缺任何一个，workspaces 路由都会诚实地回 503。 */
const REQUIRED_BACKEND_KEYS = [
  'MAGICCLASS_FUSION_ENABLED',
  'MAGICCLASS_SERVICE_URL',
  'MAGICCLASS_INTERNAL_SECRET',
];

/** 「学习空间」必需的三个键。缺任何一个，导航栏入口只会显示"尚未启用"。 */
const REQUIRED_LEARNING_SPACE_KEYS = [
  'MAGICCLASS_ENABLED',
  'MAGICCLASS_BASE_URL',
  'MAGICCLASS_EMBED_ORIGIN',
];

const log = (message) => console.log(message);
const ok = (message) => console.log(`  \u2713 ${message}`);
const warn = (message) => console.log(`  ! ${message}`);
const bad = (message) => console.log(`  \u2717 ${message}`);

// ===== .env 读写 =====

export function parseEnv(text) {
  const values = new Map();
  for (const line of text.split(/\r?\n/)) {
    const match = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$/.exec(line);
    if (match) values.set(match[1], match[2].trim());
  }
  return values;
}

function readEnvFile(file) {
  return existsSync(file) ? readFileSync(file, 'utf8') : '';
}

/** Preserve ignored local values while moving them onto the new env contract. */
export function migrateLegacyEnvPrefix(envPath) {
  const original = readEnvFile(envPath);
  if (!original) return [];
  const existing = parseEnv(original);
  const migrated = [];
  const lines = original.split(/\r?\n/).flatMap((line) => {
    const match = /^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=.*)$/.exec(line);
    if (!match || !match[2].startsWith(LEGACY_ENV_PREFIX)) return [line];
    const key = `${CURRENT_ENV_PREFIX}${match[2].slice(LEGACY_ENV_PREFIX.length)}`;
    migrated.push(key);
    if (existing.has(key)) return [];
    existing.set(key, true);
    return [`${match[1]}${key}${match[3]}`];
  });
  if (migrated.length) writeFileSync(envPath, lines.join('\n'), 'utf8');
  return migrated;
}

export function upsertEnv(envPath, entries, header) {
  const original = readEnvFile(envPath);
  const present = parseEnv(original);
  const lines = original ? original.split(/\r?\n/) : [];
  const filled = [];
  const missing = [];

  for (const [key, value] of entries) {
    const lineIndex = lines.findIndex((line) => new RegExp(`^\\s*${key}\\s*=`).test(line));
    if (lineIndex < 0) {
      missing.push([key, value]);
      continue;
    }
    // `.env.example` intentionally keeps secrets blank. Treat a blank value as
    // missing so `env` can bootstrap a clean local checkout without appending a
    // duplicate key (dotenv implementations disagree about duplicate entries).
    if (!String(present.get(key) || '').trim() && String(value || '').trim()) {
      lines[lineIndex] = `${key}=${value}`;
      filled.push(key);
    }
  }

  if (!missing.length && !filled.length) return [];

  const base = original && !original.endsWith('\n') ? `${original}\n` : original;
  const block = `\n# --- ${header}（仅本机开发；该文件被 .gitignore 忽略）---\n`
    + missing.map(([key, value]) => `${key}=${value}`).join('\n')
    + '\n';
  const updated = filled.length ? `${lines.join('\n')}${original.endsWith('\n') ? '' : '\n'}` : base;
  writeFileSync(envPath, updated + (missing.length ? block : ''), 'utf8');
  return [...filled, ...missing.map(([key]) => key)];
}

/** 复用已存在的本地密钥：换掉它会让正在跑的服务立刻验签失败。 */
function existingSecret() {
  const backendValue = parseEnv(readEnvFile(BACKEND_ENV)).get('MAGICCLASS_INTERNAL_SECRET');
  if (backendValue) return backendValue;
  // If a service env already exists, reuse its local secret to repair a backend
  // template copied with an empty value instead of creating a mismatched pair.
  return parseEnv(readEnvFile(SERVICE_ENV)).get('MAGICCLASS_INTERNAL_SECRET') || '';
}

function commandEnv() {
  const backendSecret = existingSecret() || randomBytes(36).toString('base64url');
  const appOrigin = `http://127.0.0.1:${APP_PORT}`;
  return {
    backendSecret,
    backend: {
      MAGICCLASS_FUSION_ENABLED: 'true',
      MAGICCLASS_SERVICE_URL: `http://127.0.0.1:${SERVICE_PORT}`,
      MAGICCLASS_INTERNAL_SECRET: backendSecret,
      MAGICCLASS_SERVICE_TIMEOUT_SECONDS: '5',
      // 「学习空间」：magicclass-app 既是服务端内部地址，也是浏览器公开 Origin。
      // 本地开发同机同端口，所以两者取同一个值；生产部署下必须拆开
      // （内部走容器网络名，公开走对外子域），届时手工改这两个键即可。
      MAGICCLASS_ENABLED: 'true',
      MAGICCLASS_BASE_URL: appOrigin,
      MAGICCLASS_EMBED_ORIGIN: appOrigin,
    },
  };
}

function cmdEnv() {
  const migratedBackend = migrateLegacyEnvPrefix(BACKEND_ENV);
  const migratedService = migrateLegacyEnvPrefix(SERVICE_ENV);
  const { backendSecret, backend } = commandEnv();
  log('生成本地配置（幂等：只补缺失项，不覆盖你已有的值）');
  if (migratedBackend.length) ok(`backend/.env 已迁移 ${migratedBackend.join(', ')}`);
  if (migratedService.length) ok(`magicclass-service/.env 已迁移 ${migratedService.join(', ')}`);

  const addedBackend = upsertEnv(
    BACKEND_ENV,
    Object.entries(backend),
    '本地受管 magic class（融合链路与「学习空间」）',
  );
  if (addedBackend.length) ok(`backend/.env 补充了 ${addedBackend.join(', ')}`);
  else ok('backend/.env 已包含本地 magicclass 配置，未改动');

  if (!existsSync(SERVICE_ENV)) {
    if (!existsSync(SERVICE_ENV_EXAMPLE)) {
      bad('缺少 magicclass-service/.env.example，无法生成模板');
      return 2;
    }
    const template = readFileSync(SERVICE_ENV_EXAMPLE, 'utf8')
      .replace(/MAGICCLASS_INTERNAL_SECRET=\r?\n/, `MAGICCLASS_INTERNAL_SECRET=${backendSecret}\n`);
    writeFileSync(SERVICE_ENV, template, 'utf8');
    ok('magicclass-service/.env 已从模板生成（密钥与后端一致）');
  } else {
    const serviceEnvText = readEnvFile(SERVICE_ENV);
    const values = parseEnv(serviceEnvText);
    const serviceSecret = values.get('MAGICCLASS_INTERNAL_SECRET') || '';
    const secretLines = serviceEnvText.match(/^\s*MAGICCLASS_INTERNAL_SECRET\s*=.*$/gm) || [];
    if (!serviceSecret || secretLines.length !== 1) {
      const withoutSecrets = serviceEnvText
        .split(/\r?\n/)
        .filter((line) => !/^\s*MAGICCLASS_INTERNAL_SECRET\s*=.*$/.test(line));
      const updated = `${withoutSecrets.join('\n').replace(/\n*$/, '\n')}MAGICCLASS_INTERNAL_SECRET=${backendSecret}\n`;
      writeFileSync(SERVICE_ENV, updated, 'utf8');
      ok('magicclass-service/.env 补齐了 MAGICCLASS_INTERNAL_SECRET');
    } else if (serviceSecret !== backendSecret) {
      bad('两个 .env 的内部密钥不一致 —— 网关签的断言会被服务拒绝（assertion_rejected）');
      warn('请把 backend/.env 与 magicclass-service/.env 的 MAGICCLASS_INTERNAL_SECRET 改成同一个值');
      return 1;
    } else {
      ok('magicclass-service/.env 已存在，密钥与后端一致');
    }
  }
  return 0;
}

// ===== 体检 =====

function portState(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port });
    const done = (state) => { socket.destroy(); resolve(state); };
    socket.setTimeout(1200);
    socket.on('connect', () => done('listening'));
    socket.on('timeout', () => done('free'));
    socket.on('error', () => done('free'));
  });
}

async function probe(url) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(2500) });
    return response.status;
  } catch {
    return null;
  }
}

/**
 * 上游 /api/health 自报的版本号；拿不到（没起、超时、不是 magic class）回 null。
 *
 * 它比"HTTP 200"更能说明端口上到底是谁：同一台机器上很容易有另一份 magic class
 * 正在别的目录里开发（本仓库自己也留过一份运行副本）。只看状态码的话，
 * `start` 会把别人的 200 当成自己的第四个进程，"学习空间"内嵌的也就成了别人的界面。
 */
async function appHealthVersion() {
  try {
    const response = await fetch(`http://127.0.0.1:${APP_PORT}/api/health`, {
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) return null;
    const body = await response.json();
    return typeof body.version === 'string' ? body.version : null;
  } catch {
    return null;
  }
}

/**
 * 上游首页响应里的 `frame-ancestors` 指令；读不到回 null。
 *
 * 这条头是"能不能嵌"的唯一权威判据：站点能访问、健康检查通过，都不代表浏览器
 * 肯把 iframe 画出来。dev 模式下取首页要先现编译，慢是正常的。
 */
async function frameAncestorsDirective() {
  try {
    const response = await fetch(`http://127.0.0.1:${APP_PORT}/`, {
      signal: AbortSignal.timeout(120000),
    });
    const policy = response.headers.get('content-security-policy') || '';
    const match = policy.match(/frame-ancestors([^;]*)/i);
    return match ? match[1].trim() : null;
  } catch {
    return null;
  }
}

function nodeVersionOk() {
  const current = process.versions.node.split('.').map(Number);
  for (let i = 0; i < MIN_NODE.length; i += 1) {
    if (current[i] > MIN_NODE[i]) return true;
    if (current[i] < MIN_NODE[i]) return false;
  }
  return true;
}

function resolvePython() {
  const candidates = [
    path.join(BACKEND_DIR, '.venv', 'Scripts', 'python.exe'),
    path.join(BACKEND_DIR, '.venv', 'bin', 'python'),
  ];
  return candidates.find((candidate) => existsSync(candidate)) || null;
}

async function cmdDoctor() {
  log(`体检仓库：${REPO}\n`);
  let problems = 0;

  log('依赖');
  if (nodeVersionOk()) ok(`node ${process.versions.node}`);
  else { bad(`node ${process.versions.node} 过低，magicclass-service 需要 >= ${MIN_NODE.join('.')}`); problems += 1; }

  const python = resolvePython();
  if (python) ok(`后端解释器 ${path.relative(REPO, python)}`);
  else { bad('缺少 backend/.venv，先按 docs/magicclass-deployment.md 创建'); problems += 1; }

  if (existsSync(path.join(WEB_DIR, 'node_modules', 'vite'))) ok('webreact 依赖已安装');
  else { bad('缺少 webreact/node_modules，先在 webreact 执行 npm install'); problems += 1; }

  log('\n配置');
  const backendValues = parseEnv(readEnvFile(BACKEND_ENV));
  for (const key of REQUIRED_BACKEND_KEYS) {
    if (backendValues.get(key)) ok(`backend/.env ${key}`);
    else { bad(`backend/.env 缺少 ${key} —— 快速询问会得到 503（reason=fusion_disabled / service_unconfigured）`); problems += 1; }
  }
  const serviceValues = parseEnv(readEnvFile(SERVICE_ENV));
  if (!existsSync(SERVICE_ENV)) {
    bad('缺少 magicclass-service/.env（先跑 `env` 子命令）');
    problems += 1;
  } else if (!serviceValues.get('MAGICCLASS_INTERNAL_SECRET')) {
    bad('magicclass-service/.env 缺少 MAGICCLASS_INTERNAL_SECRET');
    problems += 1;
  } else if (serviceValues.get('MAGICCLASS_INTERNAL_SECRET') !== backendValues.get('MAGICCLASS_INTERNAL_SECRET')) {
    bad('两侧内部密钥不一致 —— 断言会被拒（assertion_rejected）');
    problems += 1;
  } else {
    ok('两侧内部密钥一致');
  }
  if (backendValues.get('MAGICCLASS_SERVICE_URL') === `http://127.0.0.1:${SERVICE_PORT}`) {
    ok(`MAGICCLASS_SERVICE_URL 指向仓库内受管服务 :${SERVICE_PORT}`);
  } else {
    warn(`MAGICCLASS_SERVICE_URL=${backendValues.get('MAGICCLASS_SERVICE_URL') || '(未设置)'}，与 :${SERVICE_PORT} 不同`);
  }
  log('\n学习空间（导航栏入口）');
  // 依赖没装不会让 doctor 之外的任何东西"看起来正常"——Next 二进制缺失时
  // start 只能报出一句无信息量的 spawn 错误，所以在这里就拦下来。
  if (existsSync(path.join(APP_DIR, 'node_modules', 'next'))) ok('magicclass-app 依赖已安装');
  else { bad('缺少 magicclass-app/node_modules，先在 magicclass-app 执行 pnpm install'); problems += 1; }

  for (const key of REQUIRED_LEARNING_SPACE_KEYS) {
    const value = backendValues.get(key);
    if (value) ok(`backend/.env ${key}=${value}`);
    else { bad(`backend/.env 缺少 ${key} —— 导航栏「学习空间」只会显示"尚未启用"`); problems += 1; }
  }
  const expectedOrigin = `http://127.0.0.1:${APP_PORT}`;
  const embedOrigin = backendValues.get('MAGICCLASS_EMBED_ORIGIN');
  if (embedOrigin && embedOrigin !== expectedOrigin) {
    warn(`MAGICCLASS_EMBED_ORIGIN 指向 ${embedOrigin}，与本机 :${APP_PORT} 不同`);
  }
  // 跨源内嵌要求两端 Origin 严格不等：同源时前端会 fail-closed 拒绝渲染，
  // 表现为导航栏点进去是空白页而不是报错。
  const webOrigin = `http://127.0.0.1:${WEB_PORT}`;
  if (embedOrigin === webOrigin) {
    bad(`MAGICCLASS_EMBED_ORIGIN 不能等于站点自身的 ${webOrigin}（跨源内嵌要求两端不同）`);
    problems += 1;
  }

  log('\n进程与健康');
  const serviceLive = await probe(`http://127.0.0.1:${SERVICE_PORT}/internal/health/live`);
  if (serviceLive === 200) ok(`magicclass-service :${SERVICE_PORT} live`);
  else warn(`magicclass-service :${SERVICE_PORT} 未监听（liveness=${serviceLive ?? 'unreachable'}）`);

  const serviceReady = await probe(`http://127.0.0.1:${SERVICE_PORT}/internal/health/ready`);
  if (serviceReady === 401 || serviceReady === 403) ok('readiness 需要断言，匿名被拒是预期行为');
  else if (serviceReady === 200) warn('readiness 匿名返回 200 —— 断言强制可能没生效');
  else warn(`readiness=${serviceReady ?? 'unreachable'}`);

  // 站点的健康路由挂在 /api/v1 前缀下（见 backend/app/api/routes/health.py）。
  // 探 /health 只会拿到 404，把"服务已起来"误报成"未就绪"——这个坑在浏览器
  // 验收脚本里踩过一次，这里保持一致。
  const backendHealth = await probe(`http://127.0.0.1:${BACKEND_PORT}/api/v1/health`);
  if (backendHealth === 200) ok(`FastAPI :${BACKEND_PORT} 健康`);
  else warn(`FastAPI :${BACKEND_PORT} 未就绪（status=${backendHealth ?? 'unreachable'}）`);

  const fusion = await probe(`http://127.0.0.1:${BACKEND_PORT}/api/v1/magicclass/fusion/status`);
  if (fusion === 401) ok('fusion/status 需要登录，401 说明路由已挂载');
  else if (fusion === 200) ok('fusion/status 可达（带 token 时读 state 字段）');
  else warn(`fusion/status=${fusion ?? 'unreachable'}`);

  const web = await probe(`http://127.0.0.1:${WEB_PORT}/`);
  if (web === 200) ok(`Vite :${WEB_PORT} 可访问`);
  else warn(`Vite :${WEB_PORT} 未就绪（status=${web ?? 'unreachable'}）`);

  // 上游应用的健康路由；dev 模式下首次请求要现编译，慢是正常的。
  // 比对自报版本，是因为这个端口上完全可能是**另一份** magic class：那样 start 会
  // 以为自己的第四个进程起来了，而「学习空间」内嵌的是别人的界面。
  const appHealth = await appHealthVersion();
  const expectedAppVersion = appVersion();
  if (appHealth === null) warn(`magicclass-app :${APP_PORT} 未就绪（没在跑，或不是 MagicClass）`);
  else if (appHealth === expectedAppVersion) ok(`magicclass-app :${APP_PORT} 健康（v${appHealth}）`);
  else {
    bad(`:${APP_PORT} 自报版本是 v${appHealth}，不是入库的 v${expectedAppVersion} —— 端口被另一份 MagicClass 占用`);
    problems += 1;
  }

  // 只有应用在跑时才看得到这条头；它决定浏览器肯不肯把 iframe 画出来。
  if (appHealth === expectedAppVersion) {
    const ancestors = await frameAncestorsDirective();
    if (ancestors === null) {
      warn('读不到应用的 frame-ancestors 头，无法确认是否放行本站内嵌');
    } else if (!ancestors.includes(`http://127.0.0.1:${WEB_PORT}`)) {
      bad(`应用 frame-ancestors 是「${ancestors}」，没放行 http://127.0.0.1:${WEB_PORT} —— 「学习空间」会一片空白`);
      problems += 1;
    } else {
      ok('应用已放行本站 Origin 内嵌');
    }
  }

  log('\n端口占用');
  for (const [label, port] of [['magicclass-service', SERVICE_PORT], ['FastAPI', BACKEND_PORT], ['Vite', WEB_PORT], ['magicclass-app', APP_PORT]]) {
    const state = await portState(port);
    log(`  ${label.padEnd(16)} :${port} ${state === 'listening' ? '已被占用（服务在跑）' : '空闲'}`);
  }

  log('');
  if (problems) {
    bad(`发现 ${problems} 个阻塞项，先修掉再启动`);
    return 1;
  }
  ok('体检通过：可以执行 `node scripts/magicclass-local.mjs start`');
  return 0;
}

// ===== 启动 =====

function spawnService(argv, cwd, env) {
  const child = spawn(argv[0], argv.slice(1), {
    cwd,
    env: { ...process.env, NO_PROXY: '127.0.0.1,localhost', no_proxy: '127.0.0.1,localhost', ...env },
    stdio: 'inherit',
    windowsHide: false,
  });
  return child;
}

async function waitFor(url, label, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const status = await probe(url);
    if (status === 200) return true;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${label} 在 ${Math.round(timeoutMs / 1000)}s 内未就绪（${url}）`);
}

async function cmdStart() {
  const python = resolvePython();
  if (!python) {
    bad('缺少 backend/.venv，先跑 `env` 与安装依赖');
    return 2;
  }
  if (!existsSync(SERVICE_ENV)) {
    bad('缺少 magicclass-service/.env，先跑 `node scripts/magicclass-local.mjs env`');
    return 2;
  }
  const nextBin = path.join(APP_DIR, 'node_modules', 'next', 'dist', 'bin', 'next');
  if (!existsSync(nextBin)) {
    bad('缺少 magicclass-app/node_modules，先在 magicclass-app 执行 pnpm install');
    return 2;
  }

  log('按顺序启动：magicclass-service → FastAPI → magicclass-app → Vite\n');
  const service = spawnService(
    [process.execPath, '--experimental-strip-types', 'src/main.ts'],
    SERVICE_DIR,
    { MAGICCLASS_PORT: String(SERVICE_PORT) },
  );
  const children = [service];
  // 提到 try 外面，是因为失败路径也要用它：next dev 在端口被占时会自己换一个
  // 端口活下去，只抛错不杀进程的话，脚本会抱着四个进程一直等在那里。
  const shutdown = () => children.forEach((child) => child.kill());
  try {
    await waitFor(`http://127.0.0.1:${SERVICE_PORT}/internal/health/live`, 'magicclass-service', 45000);
    ok(`magicclass-service :${SERVICE_PORT}`);

    const backend = spawnService(
      [python, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
      BACKEND_DIR,
      { AUTO_SEED_DEMO_USERS },
    );
    children.push(backend);
    await waitFor(`http://127.0.0.1:${BACKEND_PORT}/api/v1/health`, 'FastAPI', 90000);
    ok(`FastAPI :${BACKEND_PORT}`);

    // next dev：直接用 node 调 node_modules 里的二进制，不依赖 pnpm / next 在 PATH 上。
    // npm_package_version 见 appVersion()：缺了它健康端点会自报 0.1.0。
    // ALLOWED_FRAME_ANCESTORS 见 APP_FRAME_ANCESTORS：缺了它 iframe 会被浏览器拒掉。
    const app = spawnService(
      [process.execPath, nextBin, 'dev', '--port', String(APP_PORT), '--hostname', '127.0.0.1'],
      APP_DIR,
      { npm_package_version: appVersion(), ALLOWED_FRAME_ANCESTORS: APP_FRAME_ANCESTORS },
    );
    children.push(app);
    // dev 模式首请求要现编译整条路由链，冷启动一分钟以上属正常。
    await waitFor(`http://127.0.0.1:${APP_PORT}/api/health`, 'magicclass-app', 180000);
    // 200 不等于"我们自己的那份起来了"：端口上可能是别人正在开发的另一份
    // magic class，此时 next dev 根本没绑上，而健康检查照样通过。
    const servedVersion = await appHealthVersion();
    if (servedVersion !== appVersion()) {
      bad(`:${APP_PORT} 上响应的是另一份 MagicClass（自报 v${servedVersion ?? '未知'}，期望 v${appVersion()}），入库应用并没有起来`);
      bad(`请先停掉占用 :${APP_PORT} 的那个开发服务器；或换 CAMPUSMATE_LEARNING_SPACE_PORT 并同步 backend/.env 里 MAGICCLASS_BASE_URL / MAGICCLASS_EMBED_ORIGIN`);
      throw new Error('端口被另一份 magic class 占用');
    }
    ok(`magicclass-app :${APP_PORT}（v${servedVersion}）`);

    const vite = spawnService(
      [process.execPath, path.join(WEB_DIR, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', String(WEB_PORT), '--strictPort'],
      WEB_DIR,
      { VITE_BACKEND_PORT: String(BACKEND_PORT) },
    );
    children.push(vite);
    await waitFor(`http://127.0.0.1:${WEB_PORT}/`, 'Vite', 90000);
    ok(`Vite :${WEB_PORT}`);

    log(`\n全部就绪。入口：http://127.0.0.1:${WEB_PORT}/courses`);
    log(`学习空间：http://127.0.0.1:${WEB_PORT}/learning-space（内嵌 :${APP_PORT}，首次打开较慢）`);
    log('按 Ctrl+C 停止（四个进程一起退出）。');
  } catch (error) {
    console.error(`\n启动失败：${error.message}`);
    shutdown();
    return 1;
  } finally {
    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
    await new Promise((resolve) => {
      process.on('SIGINT', resolve);
      process.on('SIGTERM', resolve);
      children.forEach((child) => child.on('exit', resolve));
    });
    shutdown();
  }
  return 0;
}

// ===== 入口 =====

const COMMANDS = { env: cmdEnv, doctor: cmdDoctor, start: cmdStart };

async function main() {
  const command = process.argv[2] || 'doctor';
  const handler = COMMANDS[command];
  if (!handler) {
    console.error(`未知子命令：${command}`);
    console.error(`可用：${Object.keys(COMMANDS).join(' | ')}`);
    return 2;
  }
  return handler();
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))) {
  main().then((code) => { process.exitCode = code; }).catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
