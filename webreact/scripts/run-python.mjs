#!/usr/bin/env node
/**
 * 跨平台 Python 解释器解析器（E2E 脚本入口）。
 *
 * 为什么需要它
 * ------------
 * `npm run test:e2e:*` 原先直接调用裸 `python`。在 Windows 上这不成立：
 * 本仓库的开发机没有系统级 `python`（只有 `backend/.venv`），`python` 会解析失败
 * 或落到 Microsoft Store 的占位程序；CI 上常见的又是 `python3`。
 * 结果就是"文档里写着能跑，本地跑不起来"。
 *
 * 解析优先级（不硬编码任何机器绝对路径，一切从本文件位置与仓库结构推导）
 * --------------------------------------------------------------------
 *   1. 环境变量 `PYTHON` / `PYTHON_BIN`（显式覆盖，CI 用）
 *   2. 仓库内 `backend/.venv`
 *      - Windows: `Scripts/python.exe`
 *      - POSIX:   `bin/python`
 *   3. PATH 上的 `python3` → `python` → `py -3`（Windows launcher）
 *
 * 解析失败时打印清晰的排查指引并以退出码 127 结束，不静默吞掉。
 *
 * 用法：
 *   node scripts/run-python.mjs tests/e2e/learner-state-closed-loop.py [args...]
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { delimiter, dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..", "..");

function whichAll(command) {
  const pathValue = process.env.PATH || "";
  const extensions = process.platform === "win32"
    ? (process.env.PATHEXT || ".EXE;.CMD;.BAT").split(";").filter(Boolean)
    : [""];
  const found = [];
  for (const dir of pathValue.split(delimiter)) {
    if (!dir) continue;
    for (const ext of extensions) {
      const candidate = join(dir, command + ext);
      if (existsSync(candidate)) found.push(candidate);
    }
  }
  return found;
}

function venvInterpreters() {
  const venv = join(REPO_ROOT, "backend", ".venv");
  return process.platform === "win32"
    ? [join(venv, "Scripts", "python.exe")]
    : [join(venv, "bin", "python3"), join(venv, "bin", "python")];
}

/** @returns {{command: string, prefixArgs: string[], source: string} | null} */
function resolvePython() {
  const explicit = process.env.PYTHON || process.env.PYTHON_BIN;
  if (explicit) {
    if (isAbsolute(explicit) && !existsSync(explicit)) {
      console.error(`[run-python] PYTHON 指向的解释器不存在: ${explicit}`);
      process.exit(127);
    }
    return { command: explicit, prefixArgs: [], source: "环境变量 PYTHON/PYTHON_BIN" };
  }

  for (const candidate of venvInterpreters()) {
    if (existsSync(candidate)) {
      return { command: candidate, prefixArgs: [], source: "backend/.venv" };
    }
  }

  for (const name of ["python3", "python"]) {
    const hits = whichAll(name);
    if (hits.length > 0) {
      return { command: hits[0], prefixArgs: [], source: `PATH 上的 ${name}` };
    }
  }
  const launcher = whichAll("py");
  if (launcher.length > 0) {
    return { command: launcher[0], prefixArgs: ["-3"], source: "Windows py launcher" };
  }
  return null;
}

const [script, ...rest] = process.argv.slice(2);
if (!script) {
  console.error("用法: node scripts/run-python.mjs <python-script> [args...]");
  process.exit(2);
}

const scriptPath = isAbsolute(script) ? script : resolve(process.cwd(), script);
if (!existsSync(scriptPath)) {
  console.error(`[run-python] 找不到脚本: ${scriptPath}`);
  process.exit(2);
}

const resolved = resolvePython();
if (!resolved) {
  console.error(
    [
      "[run-python] 找不到可用的 Python 解释器。请任选一种方式：",
      "  1) 创建后端虚拟环境: python -m venv backend/.venv 后安装依赖",
      "  2) 显式指定: PYTHON=/path/to/python npm run test:e2e:learner-state",
    ].join("\n"),
  );
  process.exit(127);
}

console.error(`[run-python] 使用 ${resolved.source}: ${resolved.command}`);

const result = spawnSync(
  resolved.command,
  [...resolved.prefixArgs, scriptPath, ...rest],
  { stdio: "inherit", cwd: process.cwd(), env: process.env },
);

if (result.error) {
  console.error(`[run-python] 启动解释器失败: ${result.error.message}`);
  process.exit(127);
}
process.exit(result.status === null ? 1 : result.status);
