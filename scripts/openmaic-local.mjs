#!/usr/bin/env node
/**
 * CampusMate 本地受管 OpenMAIC 的启动与诊断入口（从仓库根目录执行）。
 *
 *   node scripts/openmaic-local.mjs env      生成/补齐本地 .env（幂等，不改你已有的项）
 *   node scripts/openmaic-local.mjs doctor   体检：依赖、配置、端口、健康端点
 *   node scripts/openmaic-local.mjs start    依次拉起三服务，全部就绪后才打印入口
 *
 * 三个进程的边界必须分清，混用会得到"看起来在跑但永远 503"：
 *
 *   Vite 5174  →  FastAPI 8000  →  openmaic-service 4010
 *
 * 注意 `OPENMAIC_BASE_URL`（旧互动课堂适配层，本机运行副本常在 3000）与
 * `OPENMAIC_SERVICE_URL`（仓库内受管服务，默认 4010）是**两套东西**，
 * 融合链路只看后者。
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
const SERVICE_DIR = path.join(REPO, 'openmaic-service');
const WEB_DIR = path.join(REPO, 'webreact');

const BACKEND_ENV = path.join(BACKEND_DIR, '.env');
const SERVICE_ENV = path.join(SERVICE_DIR, '.env');
const SERVICE_ENV_EXAMPLE = path.join(SERVICE_DIR, '.env.example');

const BACKEND_PORT = Number(process.env.CAMPUSMATE_BACKEND_PORT || 8000);
const SERVICE_PORT = Number(process.env.CAMPUSMATE_OPENMAIC_PORT || 4010);
const WEB_PORT = Number(process.env.CAMPUSMATE_WEB_PORT || 5174);
const MIN_NODE = [22, 19, 0];

/** 融合链路必需的四个键。缺任何一个，workspaces 路由都会诚实地回 503。 */
const REQUIRED_BACKEND_KEYS = [
  'OPENMAIC_FUSION_ENABLED',
  'OPENMAIC_SERVICE_URL',
  'OPENMAIC_INTERNAL_SECRET',
];

const log = (message) => console.log(message);
const ok = (message) => console.log(`  \u2713 ${message}`);
const warn = (message) => console.log(`  ! ${message}`);
const bad = (message) => console.log(`  \u2717 ${message}`);

// ===== .env 读写 =====

function parseEnv(text) {
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

function upsertEnv(envPath, entries, header) {
  const original = readEnvFile(envPath);
  const present = parseEnv(original);
  const missing = entries.filter(([key]) => !present.has(key));
  if (!missing.length) return [];

  const base = original && !original.endsWith('\n') ? `${original}\n` : original;
  const block = `\n# --- ${header}（仅本机开发；该文件被 .gitignore 忽略）---\n`
    + missing.map(([key, value]) => `${key}=${value}`).join('\n')
    + '\n';
  writeFileSync(envPath, base + block, 'utf8');
  return missing.map(([key]) => key);
}

/** 复用已存在的本地密钥：换掉它会让正在跑的服务立刻验签失败。 */
function existingSecret() {
  const values = parseEnv(readEnvFile(BACKEND_ENV));
  const value = values.get('OPENMAIC_INTERNAL_SECRET');
  return value ? value : '';
}

function commandEnv() {
  const backendSecret = existingSecret() || randomBytes(36).toString('base64url');
  return {
    backendSecret,
    backend: {
      OPENMAIC_FUSION_ENABLED: 'true',
      OPENMAIC_SERVICE_URL: `http://127.0.0.1:${SERVICE_PORT}`,
      OPENMAIC_INTERNAL_SECRET: backendSecret,
      OPENMAIC_SERVICE_TIMEOUT_SECONDS: '5',
    },
  };
}

function cmdEnv() {
  const { backendSecret, backend } = commandEnv();
  log('生成本地配置（幂等：只补缺失项，不覆盖你已有的值）');

  const addedBackend = upsertEnv(
    BACKEND_ENV,
    Object.entries(backend),
    '本地受管 OpenMAIC 融合服务',
  );
  if (addedBackend.length) ok(`backend/.env 补充了 ${addedBackend.join(', ')}`);
  else ok('backend/.env 已包含融合配置，未改动');

  if (!existsSync(SERVICE_ENV)) {
    if (!existsSync(SERVICE_ENV_EXAMPLE)) {
      bad('缺少 openmaic-service/.env.example，无法生成模板');
      return 2;
    }
    const template = readFileSync(SERVICE_ENV_EXAMPLE, 'utf8')
      .replace('OPENMAIC_INTERNAL_SECRET=\n', `OPENMAIC_INTERNAL_SECRET=${backendSecret}\n`);
    writeFileSync(SERVICE_ENV, template, 'utf8');
    ok('openmaic-service/.env 已从模板生成（密钥与后端一致）');
  } else {
    const values = parseEnv(readEnvFile(SERVICE_ENV));
    const serviceSecret = values.get('OPENMAIC_INTERNAL_SECRET') || '';
    if (!serviceSecret) {
      const text = readEnvFile(SERVICE_ENV);
      writeFileSync(SERVICE_ENV, `${text}${text.endsWith('\n') ? '' : '\n'}OPENMAIC_INTERNAL_SECRET=${backendSecret}\n`, 'utf8');
      ok('openmaic-service/.env 补齐了 OPENMAIC_INTERNAL_SECRET');
    } else if (serviceSecret !== backendSecret) {
      bad('两个 .env 的内部密钥不一致 —— 网关签的断言会被服务拒绝（assertion_rejected）');
      warn('请把 backend/.env 与 openmaic-service/.env 的 OPENMAIC_INTERNAL_SECRET 改成同一个值');
      return 1;
    } else {
      ok('openmaic-service/.env 已存在，密钥与后端一致');
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
  else { bad(`node ${process.versions.node} 过低，openmaic-service 需要 >= ${MIN_NODE.join('.')}`); problems += 1; }

  const python = resolvePython();
  if (python) ok(`后端解释器 ${path.relative(REPO, python)}`);
  else { bad('缺少 backend/.venv，先按 docs/openmaic-deployment.md 创建'); problems += 1; }

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
    bad('缺少 openmaic-service/.env（先跑 `env` 子命令）');
    problems += 1;
  } else if (!serviceValues.get('OPENMAIC_INTERNAL_SECRET')) {
    bad('openmaic-service/.env 缺少 OPENMAIC_INTERNAL_SECRET');
    problems += 1;
  } else if (serviceValues.get('OPENMAIC_INTERNAL_SECRET') !== backendValues.get('OPENMAIC_INTERNAL_SECRET')) {
    bad('两侧内部密钥不一致 —— 断言会被拒（assertion_rejected）');
    problems += 1;
  } else {
    ok('两侧内部密钥一致');
  }
  if (backendValues.get('OPENMAIC_SERVICE_URL') === `http://127.0.0.1:${SERVICE_PORT}`) {
    ok(`OPENMAIC_SERVICE_URL 指向仓库内受管服务 :${SERVICE_PORT}`);
  } else {
    warn(`OPENMAIC_SERVICE_URL=${backendValues.get('OPENMAIC_SERVICE_URL') || '(未设置)'}，与 :${SERVICE_PORT} 不同`);
  }
  if (backendValues.get('OPENMAIC_BASE_URL')) {
    warn(`OPENMAIC_BASE_URL=${backendValues.get('OPENMAIC_BASE_URL')} 是旧互动课堂适配层，融合链路不使用它`);
  }

  log('\n进程与健康');
  const serviceLive = await probe(`http://127.0.0.1:${SERVICE_PORT}/internal/health/live`);
  if (serviceLive === 200) ok(`openmaic-service :${SERVICE_PORT} live`);
  else warn(`openmaic-service :${SERVICE_PORT} 未监听（liveness=${serviceLive ?? 'unreachable'}）`);

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

  const fusion = await probe(`http://127.0.0.1:${BACKEND_PORT}/api/v1/openmaic/fusion/status`);
  if (fusion === 401) ok('fusion/status 需要登录，401 说明路由已挂载');
  else if (fusion === 200) ok('fusion/status 可达（带 token 时读 state 字段）');
  else warn(`fusion/status=${fusion ?? 'unreachable'}`);

  const web = await probe(`http://127.0.0.1:${WEB_PORT}/`);
  if (web === 200) ok(`Vite :${WEB_PORT} 可访问`);
  else warn(`Vite :${WEB_PORT} 未就绪（status=${web ?? 'unreachable'}）`);

  log('\n端口占用');
  for (const [label, port] of [['openmaic-service', SERVICE_PORT], ['FastAPI', BACKEND_PORT], ['Vite', WEB_PORT]]) {
    const state = await portState(port);
    log(`  ${label.padEnd(16)} :${port} ${state === 'listening' ? '已被占用（服务在跑）' : '空闲'}`);
  }

  log('');
  if (problems) {
    bad(`发现 ${problems} 个阻塞项，先修掉再启动`);
    return 1;
  }
  ok('体检通过：可以执行 `node scripts/openmaic-local.mjs start`');
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
    bad('缺少 openmaic-service/.env，先跑 `node scripts/openmaic-local.mjs env`');
    return 2;
  }

  log('按顺序启动：openmaic-service → FastAPI → Vite\n');
  const service = spawnService(
    [process.execPath, '--experimental-strip-types', 'src/main.ts'],
    SERVICE_DIR,
    { OPENMAIC_PORT: String(SERVICE_PORT) },
  );
  const children = [service];
  try {
    await waitFor(`http://127.0.0.1:${SERVICE_PORT}/internal/health/live`, 'openmaic-service', 45000);
    ok(`openmaic-service :${SERVICE_PORT}`);

    const backend = spawnService(
      [python, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
      BACKEND_DIR,
      {},
    );
    children.push(backend);
    await waitFor(`http://127.0.0.1:${BACKEND_PORT}/api/v1/health`, 'FastAPI', 90000);
    ok(`FastAPI :${BACKEND_PORT}`);

    const vite = spawnService(
      [process.execPath, path.join(WEB_DIR, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', String(WEB_PORT), '--strictPort'],
      WEB_DIR,
      { VITE_BACKEND_PORT: String(BACKEND_PORT) },
    );
    children.push(vite);
    await waitFor(`http://127.0.0.1:${WEB_PORT}/`, 'Vite', 90000);
    ok(`Vite :${WEB_PORT}`);

    log(`\n全部就绪。入口：http://127.0.0.1:${WEB_PORT}/courses`);
    log('按 Ctrl+C 停止（三个进程一起退出）。');
  } catch (error) {
    console.error(`\n启动失败：${error.message}`);
    return 1;
  } finally {
    const shutdown = () => children.forEach((child) => child.kill());
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

main().then((code) => { process.exitCode = code; }).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
