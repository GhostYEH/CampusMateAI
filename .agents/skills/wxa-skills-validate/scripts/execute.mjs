#!/usr/bin/env node
import {
  DEFAULT_CLI_PATH, DEFAULT_AUTO_PORT, DEFAULT_TIMEOUT_MS,
  callAgentTool, normalizeCliResult, writeJson, parseArgs, isDestructiveApi,
} from "./lib.mjs";

const SPEC = {
  project: "string",
  name: "string",
  args: "string",
  output: "string",
  "auto-port": "number",
  "cli-path": "string",
  skill: "string",
  timeout: "number",
  "confirm-destructive": "boolean",
  help: "boolean",
};

const USAGE = `用法: node execute.mjs --project <path> --name <api-name> [options]

必需参数:
  --project <path>         项目根目录（含 project.config.json）
  --name <name>            原子接口名（对应 mcp.json 中 apis[].name）

可选参数:
  --args <json>            JSON 参数字符串，例如 '{"query":"手机"}'
  --output <path>          落盘路径；缺省时把结果打印到 stdout
  --auto-port <port>       auto WebSocket 端口（默认 ${DEFAULT_AUTO_PORT}）
  --cli-path <path>        CLI 可执行文件路径（默认 ${DEFAULT_CLI_PATH}）
  --skill <name|path>      skill 名称或路径（CLI 自动按 name 匹配，必要时显式指定）
  --timeout <ms>           请求超时（默认 ${DEFAULT_TIMEOUT_MS}，仅在非默认值时下发给 CLI）
  --confirm-destructive    显式确认执行敏感接口，未带此参数时,敏感接口会被拒绝执行(退出码 3)。

说明:
  toolCallId / sessionId / auto 相关票据全部由 CLI 内部自动处理，脚本不再暴露也不下发。
  敏感接口(会产生不可逆副作用)默认拒绝执行,须由用户明确指定单个接口 + --confirm-destructive 才放行。判定来源: 优先读 cli-agent-run/destructive-manifest.json(V019 初筛+模型判断),manifest 中 destructive=true 拦截/false 放行/null 拦截(待判断);manifest 不存在时回退关键词。
`;

async function main() {
  const opts = parseArgs(process.argv.slice(2), SPEC);

  if (opts.help) { console.log(USAGE); process.exit(0); }
  if (!opts.project || !opts.name) {
    console.error(USAGE);
    console.error("\n错误: --project 和 --name 必需。");
    process.exit(2);
  }

  // 会产生不可逆副作用的接口默认拒绝执行。
  const verdict = isDestructiveApi({ project: opts.project, apiName: opts.name });
  if (verdict.destructive) {
    if (!opts["confirm-destructive"]) {
      console.error(`\n🛑 拒绝执行敏感接口: ${opts.name}`);
      console.error(`   原因: ${verdict.reason}(来源: ${verdict.source})`);
      console.error(`   此接口会产生不可逆副作用。如确需执行,请由用户明确指定该接口并追加 --confirm-destructive。`);
      console.error(`   全量自检/loop 排查绝不应执行此类接口。\n`);
      process.exit(3);
    }
    console.error(`\n⚠️  已确认执行敏感接口: ${opts.name}(${verdict.reason})。继续...\n`);
  }

  let raw;
  try {
    raw = await callAgentTool({
      project: opts.project,
      name: opts.name,
      args: opts.args,
      autoPort: opts["auto-port"] ?? DEFAULT_AUTO_PORT,
      cliPath: opts["cli-path"] ?? DEFAULT_CLI_PATH,
      skill: opts.skill,
      timeout: opts.timeout ?? DEFAULT_TIMEOUT_MS,
    });
  } catch (err) {
    console.error(`[execute] 调用 CLI 失败: ${err.message}`);
    process.exit(2);
  }

  const { ok, result, error, diag } = normalizeCliResult(raw);

  const payload = result ?? {
    status: "error",
    error: { message: error || "unknown" },
    consoleMessages: [],
  };
  payload._meta = {
    ...payload._meta,
    project: opts.project,
    cliStderr: raw.stderr || undefined,
    cliExitCode: raw.code,
  };

  if (diag) {
    payload._meta.diagnosis = diag;
  }

  if (opts.output) {
    const outPath = await writeJson(opts.output, payload);
    console.log(`[execute] ${opts.name}  saved -> ${outPath}`);
  } else {
    console.log(JSON.stringify(payload, null, 2));
  }

  if (diag) {
    console.error(`\n⚠️  ${diag.hint}\n`);
  }

  const invokeError = payload?.invokeResult?.isError === true;
  if (ok && !invokeError) {
    console.log(`[execute] ${opts.name}  RESULT: PASS`);
    process.exit(0);
  }

  console.error(`[execute] ${opts.name}  RESULT: FAIL`);
  if (error) console.error(`  error: ${error}`);
  if (invokeError) {
    const content = payload?.invokeResult?.content;
    if (Array.isArray(content) && content.length) {
      console.error(`  invokeResult.content: ${JSON.stringify(content, null, 2)}`);
    }
  }
  process.exit(1);
}

main().catch((err) => {
  console.error(`[execute] 未处理异常: ${err?.stack || err?.message || err}`);
  process.exit(2);
});
