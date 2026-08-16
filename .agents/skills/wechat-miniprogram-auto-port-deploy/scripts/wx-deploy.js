#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const childProcess = require("child_process");

const root = process.cwd();
const scriptDir = __dirname;
const artifactsDir = path.join(root, "artifacts");
const reportPath = path.join(artifactsDir, "wechat-deploy-report.json");

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    return null;
  }
}

function writeJson(file, data) {
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

function detectPackageManager() {
  if (fs.existsSync(path.join(root, "pnpm-lock.yaml"))) return "pnpm";
  if (fs.existsSync(path.join(root, "yarn.lock"))) return "yarn";
  if (fs.existsSync(path.join(root, "bun.lockb"))) return "bun";
  return "npm";
}

function runStep(report, name, command, args, options = {}) {
  const startedAt = new Date().toISOString();
  const entry = { name, command: [command].concat(args).join(" "), startedAt, finishedAt: "", status: "running", error: "" };
  report.steps.push(entry);
  console.log(`\n[wx-deploy] ${name}: ${entry.command}`);
  const result = childProcess.spawnSync(command, args, {
    cwd: root,
    stdio: options.capture ? ["ignore", "pipe", "pipe"] : "inherit",
    encoding: "utf8",
    env: process.env
  });
  entry.finishedAt = new Date().toISOString();
  if (result.status === 0) {
    entry.status = "ok";
  } else {
    entry.status = "failed";
    entry.error = (result.stderr || result.stdout || `exit code ${result.status}`).toString().slice(0, 2000);
    throw new Error(`${name} failed`);
  }
  return result;
}

function runExperience(commandArgs, quiet) {
  const ledgerScript = path.join(scriptDir, "wechat-experience-ledger.js");
  if (!fs.existsSync(ledgerScript)) return;
  childProcess.spawnSync(process.execPath, [ledgerScript].concat(commandArgs), {
    cwd: root,
    stdio: quiet ? "ignore" : "inherit",
    env: Object.assign({}, process.env, { WX_EXPERIENCE_DISABLE: "1" })
  });
}

function runUpdateGuardian(report) {
  if (process.env.WX_SKIP_UPDATE_GUARDIAN === "1") {
    report.notes.push("Skipped Update Guardian because WX_SKIP_UPDATE_GUARDIAN=1.");
    return;
  }
  runStep(report, "update guardian health check", process.execPath, [path.join(scriptDir, "skill-health-check.js")]);
}

function installDependenciesIfNeeded(report, pkg, packageManager) {
  if (!pkg) return;
  if (process.env.WX_SKIP_INSTALL === "1") {
    report.notes.push("Skipped dependency install because WX_SKIP_INSTALL=1.");
    return;
  }
  if (fs.existsSync(path.join(root, "node_modules"))) {
    report.notes.push("Skipped dependency install because node_modules exists.");
    return;
  }
  const commands = {
    pnpm: ["pnpm", ["install", "--frozen-lockfile"]],
    yarn: ["yarn", ["install", "--frozen-lockfile"]],
    bun: ["bun", ["install"]],
    npm: ["npm", ["install"]]
  };
  const selected = commands[packageManager] || commands.npm;
  runStep(report, "install dependencies", selected[0], selected[1]);
}

function runExistingScript(report, pkg, name, packageManager) {
  if (!pkg || !pkg.scripts || !pkg.scripts[name]) return;
  const command = packageManager === "pnpm" ? "pnpm" : packageManager === "yarn" ? "yarn" : packageManager === "bun" ? "bun" : "npm";
  const args = command === "npm" ? ["run", name] : ["run", name];
  runStep(report, `run ${name}`, command, args);
}

function deployMode(config) {
  return process.env.WECHAT_DEPLOY_MODE || config.deployMode || "preview";
}

function main() {
  ensureDir(artifactsDir);
  const report = {
    startedAt: new Date().toISOString(),
    finishedAt: "",
    status: "pending",
    mode: "",
    packageManager: "",
    steps: [],
    blockers: [],
    suggestions: [],
    notes: [],
    docs: [
      "https://developers.weixin.qq.com/miniprogram/dev/devtools/ci.html",
      "https://www.npmjs.com/package/miniprogram-ci"
    ]
  };

  try {
    const config = readJson(path.join(root, ".codex", "wechat-miniprogram.config.json")) || {};
    const pkg = readJson(path.join(root, "package.json"));
    const packageManager = config.packageManager && config.packageManager !== "auto" ? config.packageManager : detectPackageManager();
    const mode = deployMode(config);
    report.mode = mode;
    report.packageManager = packageManager;

    runExperience(["preflight", `deploy ${mode} ${packageManager} wechat miniprogram`], false);
    runUpdateGuardian(report);
    runStep(report, "inspect", process.execPath, [path.join(scriptDir, "inspect-project.js")]);
    runStep(report, "validate", process.execPath, [path.join(scriptDir, "validate-miniprogram.js")]);
    installDependenciesIfNeeded(report, pkg, packageManager);
    runExistingScript(report, pkg, "build", packageManager);
    runStep(report, "validate again", process.execPath, [path.join(scriptDir, "validate-miniprogram.js")]);

    if (mode === "preview") {
      runStep(report, "preview", process.execPath, [path.join(scriptDir, "wx-preview.js")]);
    } else if (mode === "upload") {
      runStep(report, "upload", process.execPath, [path.join(scriptDir, "wx-upload.js")]);
    } else if (mode === "both") {
      runStep(report, "preview", process.execPath, [path.join(scriptDir, "wx-preview.js")]);
      runStep(report, "upload", process.execPath, [path.join(scriptDir, "wx-upload.js")]);
    } else {
      throw new Error(`Unsupported deploy mode: ${mode}`);
    }

    report.status = "ok";
  } catch (error) {
    report.status = "blocked";
    report.blockers.push(error.message);
    report.suggestions.push("Open artifacts/wechat-validation-report.json and fix blockers first.");
    report.suggestions.push("Confirm official docs, AppID, project path, miniprogram-ci dependency, private key, developer permission, and upload IP whitelist.");
    runExperience([
      "record",
      "--kind", "error",
      "--task-type", "deploy-miniprogram",
      "--stage", "deploy",
      "--area", "miniprogram-ci",
      "--capability", "upload",
      "--experience", "deploy-pipeline-failure",
      "--severity", "blocker",
      "--framework", "wechat-miniprogram",
      "--task", "deploy Mini Program",
      "--command", "npm run wx:deploy",
      "--summary", "Deploy failed",
      "--error", error.message,
      "--source", "artifacts/wechat-deploy-report.json"
    ], true);
    process.exitCode = 1;
    console.error(`[wx-deploy] blocked: ${error.message}`);
  } finally {
    report.finishedAt = new Date().toISOString();
    writeJson(reportPath, report);
    console.log(`WeChat deploy report written: ${path.relative(root, reportPath)}`);
  }
}

main();
