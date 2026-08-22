#!/usr/bin/env node
// scripts/probe.mjs
// 用法：node probe.mjs --project <path> --plan <plan.json> [options]
//
// 默认 --mode auto：自动 cli open → cli auto → 端口检查 → connect，失败自动重试 3 轮

import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import {
  parseArgs,
  detectDefaultCliPath,
  isPortInUse,
  runProbePlan,
  summarize,
  DEFAULT_AUTO_PORT,
} from "./probe-lib.mjs";

const DEFAULT_MAX_RETRIES = 3;
const OPEN_WAIT_MS = 10_000;
const AUTO_WAIT_MS = 5_000;

/** 运行 CLI 命令，返回 { code, stdout, stderr } */
function runCliCommand(cliPath, args, timeoutMs = 30_000) {
  return new Promise((res) => {
    const proc = spawn(cliPath, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "", stderr = "";
    proc.stdout.on("data", (d) => (stdout += d));
    proc.stderr.on("data", (d) => (stderr += d));
    const timer = setTimeout(() => {
      try { proc.kill("SIGTERM"); } catch {}
    }, timeoutMs);
    proc.on("close", (code) => {
      clearTimeout(timer);
      res({ code, stdout, stderr });
    });
    proc.on("error", (err) => {
      clearTimeout(timer);
      res({ code: -1, stdout, stderr: err.message });
    });
  });
}

/** auto 模式：自动 cli open → cli auto → 端口检查 → probe connect，失败重试 */
async function runAutoMode({ projectPath, plan, autoPort, cliPath, maxRetries, outputPath }) {
  let lastError = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    console.log(`\n========== 第 ${attempt}/${maxRetries} 轮 ==========`);

    // Step 1: cli open（预热）
    console.log(`[probe] 步骤 1/4: cli open --project ...`);
    const openResult = await runCliCommand(cliPath, ["open", "--project", projectPath], 30_000);
    if (openResult.code !== 0) {
      console.error(`[probe] cli open 失败 (exit ${openResult.code}): ${(openResult.stderr || "").slice(0, 300)}`);
      lastError = `cli open 失败: exit ${openResult.code}`;
      if (attempt < maxRetries) { console.log("[probe] 等待 5s 后重试..."); await delay(5_000); }
      continue;
    }
    console.log(`[probe] cli open 成功，等待 ${OPEN_WAIT_MS / 1000}s 预热...`);
    await delay(OPEN_WAIT_MS);

    // Step 2: cli auto（拉起自动化端口）
    console.log(`[probe] 步骤 2/4: cli auto --auto-port ${autoPort} --project ...`);
    const autoResult = await runCliCommand(
      cliPath,
      ["auto", "--auto-port", String(autoPort), "--project", projectPath, "--trust-project"],
      30_000,
    );
    if (autoResult.code !== 0) {
      console.error(`[probe] cli auto 失败 (exit ${autoResult.code}): ${(autoResult.stderr || "").slice(0, 300)}`);
      lastError = `cli auto 失败: exit ${autoResult.code}`;
      if (attempt < maxRetries) {
        console.log("[probe] 尝试 cli quit 后重试...");
        await runCliCommand(cliPath, ["quit"], 10_000).catch(() => {});
        await delay(3_000);
      }
      continue;
    }
    console.log(`[probe] cli auto 成功，等待 ${AUTO_WAIT_MS / 1000}s 端口就绪...`);
    await delay(AUTO_WAIT_MS);

    // Step 3: 检查端口
    console.log(`[probe] 步骤 3/4: 检查端口 ${autoPort} ...`);
    const portOpen = await isPortInUse(autoPort);
    if (!portOpen) {
      console.error(`[probe] 端口 ${autoPort} 未开放`);
      lastError = `端口 ${autoPort} 未开放`;
      if (attempt < maxRetries) { console.log("[probe] 等待 5s 后重试..."); await delay(5_000); }
      continue;
    }
    console.log(`[probe] 端口 ${autoPort} 已开放`);

    // Step 4: probe --mode connect
    console.log(`[probe] 步骤 4/4: probe --mode connect ...`);
    try {
      const payload = await runProbePlan({
        projectPath,
        plan,
        autoPort,
        cliPath,
        mode: "connect",
        outputPath,
      });

      const sum = summarize(payload);
      const skipMsg = sum.skippedDestructive ? `，跳过敏感 ${sum.skippedDestructive}` : "";
      console.log(`\n[probe] ✅ 完成：成功 ${sum.ok}/${sum.total}，失败 ${sum.failed}${skipMsg}（runId=${payload.runId}）`);
      console.log(`[probe] 结果文件: ${projectPath}/.ai-mode-skills/probe/${payload.runId}.json`);

      if (sum.failures.length) {
        for (const f of sum.failures) {
          console.error(`  - ${f.api_name}: ${f.status} (${f.error || "未知"})`);
        }
      }

      process.exit(sum.failures.length > 0 ? 1 : 0);
    } catch (err) {
      console.error(`[probe] 执行失败：${err.message}`);
      lastError = err.message;
      if (attempt < maxRetries) {
        console.log("[probe] 尝试 cli quit 后重试...");
        await runCliCommand(cliPath, ["quit"], 10_000).catch(() => {});
        await delay(3_000);
      }
    }
  }

  // 全部重试失败
  console.error(`\n[probe] ❌ ${maxRetries} 轮重试全部失败。`);
  console.error(`[probe] 最后错误: ${lastError}`);
  console.error(`[probe] 请排查：`);
  console.error(`  1. 微信开发者工具是否已安装并登录`);
  console.error(`  2. 设置 → 安全设置 → 服务端口 是否开启`);
  console.error(`  3. 端口 ${autoPort} 是否被其他进程占用（cli quit 后重试）`);
  console.error(`  4. 源项目能否在开发者工具中正常打开（无白屏）`);
  console.error(`[probe] probe 未执行，接口响应结构未经真机验证。请协助排查环境后重跑。`);
  process.exit(2);
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));

  if (opts.help) {
    console.log(`用法: node probe.mjs --project <path> --plan <plan.json> [options]`);
    console.log("");
    console.log(`选项:`);
    console.log(`  --mode auto       自动 cli open → cli auto → 端口检查 → connect（默认，失败重试 3 轮）`);
    console.log(`  --mode connect    跳过 cli open/auto，直接连接已开放的 ${DEFAULT_AUTO_PORT}（需预先 cli auto）`);
    console.log(`  --mode launch     automator 自启动 IDE（不推荐，connect 更稳定）`);
    console.log(`  --auto-port <n>   WebSocket 端口（默认 ${DEFAULT_AUTO_PORT}）`);
    console.log(`  --cli-path <path> CLI 路径（默认自动探测）`);
    console.log(`  --output <path>   输出文件路径（默认 <project>/.ai-mode-skills/probe/<runId>.json）`);
    console.log(`  --max-retries <n> auto 模式重试轮数（默认 ${DEFAULT_MAX_RETRIES}）`);
    console.log(`  --ws-endpoint <url>  connect/launch 模式的 WS 地址`);
    process.exit(0);
  }

  if (!opts.project || !opts.plan) {
    console.error("错误：必须提供 --project 和 --plan");
    process.exit(2);
  }

  const projectPath = resolve(opts.project);
  const planPath = resolve(opts.plan);
  const autoPort = Number(opts["auto-port"]) || DEFAULT_AUTO_PORT;
  const mode = opts.mode || "auto";

  let plan;
  try {
    plan = JSON.parse(await readFile(planPath, "utf8"));
  } catch (err) {
    console.error(`错误：读取 plan 失败：${err.message}`);
    process.exit(2);
  }
  if (!Array.isArray(plan) || !plan.length) {
    console.error("错误：plan 必须是非空数组");
    process.exit(2);
  }

  // --- auto 模式：完整流水线 + 重试 ---
  if (mode === "auto") {
    const cliPath = opts["cli-path"] || detectDefaultCliPath();
    if (!cliPath) {
      console.error("错误：未找到微信开发者工具 CLI，请通过 --cli-path 指定或设置 WX_CLI_PATH 环境变量");
      process.exit(2);
    }
    if (!existsSync(cliPath)) {
      console.error(`错误：CLI 路径不存在：${cliPath}`);
      process.exit(2);
    }
    const maxRetries = Number(opts["max-retries"]) || DEFAULT_MAX_RETRIES;

    console.log(`[probe] 模式: auto（cli open → cli auto → 端口检查 → connect，重试 ${maxRetries} 轮）`);
    console.log(`[probe] CLI: ${cliPath}`);
    console.log(`[probe] 项目: ${projectPath}`);
    console.log(`[probe] plan: ${planPath} (${plan.length} 个接口)`);
    console.log(`[probe] 端口: ${autoPort}`);

    await runAutoMode({ projectPath, plan, autoPort, cliPath, maxRetries, outputPath: opts.output ? resolve(opts.output) : null });
    return; // runAutoMode 内部 process.exit
  }

  // --- connect / launch 模式：直接 probe（需预先 cli auto） ---
  const cliPath = opts["cli-path"] || detectDefaultCliPath();
  if (!cliPath && mode !== "connect") {
    console.error("错误：未找到微信开发者工具 CLI，请通过 --cli-path 指定或设置 WX_CLI_PATH 环境变量");
    process.exit(2);
  }

  if (cliPath) console.log(`[probe] CLI: ${cliPath}`);
  console.log(`[probe] 模式: ${mode}`);

  let payload;
  try {
    payload = await runProbePlan({
      projectPath,
      plan,
      autoPort,
      cliPath,
      launchTimeoutMs: Number(opts["launch-timeout"]) || undefined,
      interactionTimeoutMs: Number(opts["interaction-timeout"]) || undefined,
      outputPath: opts.output ? resolve(opts.output) : null,
      mode: mode === "connect" ? "connect" : "launch",
      wsEndpoint: opts["ws-endpoint"],
    });
  } catch (err) {
    console.error(`[probe] 执行失败：${err.message}`);
    process.exit(2);
  }

  const sum = summarize(payload);
  const skipMsg = sum.skippedDestructive ? `，跳过敏感 ${sum.skippedDestructive}` : "";
  console.log(`[probe] 汇总：成功 ${sum.ok}/${sum.total}，失败 ${sum.failed}${skipMsg}（runId=${payload.runId}）`);

  if (sum.failures.length) {
    for (const f of sum.failures) {
      console.error(`  - ${f.api_name}: ${f.status} (${f.error || "未知"})`);
    }
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(`[probe] 未处理异常：${err?.stack || err}`);
  process.exit(2);
});
