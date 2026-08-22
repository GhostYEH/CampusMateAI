#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const childProcess = require("child_process");

const root = process.cwd();
const artifactsDir = path.join(root, "artifacts");
const reportPath = path.join(artifactsDir, "wechat-upload-report.json");

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

function packageHasMiniProgramCi() {
  const pkg = readJson(path.join(root, "package.json"));
  if (!pkg) return false;
  const deps = Object.assign({}, pkg.dependencies || {}, pkg.devDependencies || {});
  return Boolean(deps["miniprogram-ci"]);
}

function loadMiniProgramCi() {
  if (!packageHasMiniProgramCi()) {
    throw new Error("Missing dependency miniprogram-ci. Install with: npm install -D miniprogram-ci");
  }
  try {
    return require("miniprogram-ci");
  } catch (error) {
    throw new Error("Cannot require miniprogram-ci. Run dependency install first, for example: npm install");
  }
}

function resolveProjectPath(config) {
  const candidate = process.env.WECHAT_PROJECT_PATH || config.distRoot || config.miniprogramRoot || config.sourceRoot || "";
  return candidate ? path.resolve(root, candidate) : root;
}

function resolveAppId(config) {
  return process.env.WECHAT_APPID || config.appid || "";
}

function resolveRobot(config) {
  return Number(process.env.WECHAT_ROBOT || config.robot || 1);
}

function gitOutput(args) {
  try {
    return childProcess.execFileSync("git", args, { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch (error) {
    return "";
  }
}

function resolveVersion(config) {
  if (process.env.WECHAT_VERSION) return process.env.WECHAT_VERSION;
  if (config.versionStrategy === "git-tag") {
    const tag = gitOutput(["describe", "--tags", "--abbrev=0"]);
    if (tag) return tag.replace(/^v/, "");
  }
  if (config.versionStrategy === "datetime") {
    return new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  }
  const pkg = readJson(path.join(root, "package.json"));
  if (config.versionStrategy === "manual") return config.version || "0.0.0-manual";
  return pkg && pkg.version || "0.0.0";
}

function resolveDesc(config) {
  if (process.env.WECHAT_DESC) return process.env.WECHAT_DESC;
  if (config.descStrategy === "manual" && config.uploadDesc) return config.uploadDesc;
  if (config.descStrategy === "default") return "Uploaded by Codex WeChat Mini Program automation";
  const commit = gitOutput(["log", "-1", "--pretty=%s"]);
  return commit || "Uploaded by Codex WeChat Mini Program automation";
}

function createPrivateKeyFile(config) {
  if (process.env.WECHAT_PRIVATE_KEY) {
    const tempPath = path.join(os.tmpdir(), `wechat-private-${process.pid}-${crypto.randomBytes(8).toString("hex")}.key`);
    fs.writeFileSync(tempPath, process.env.WECHAT_PRIVATE_KEY, { mode: 0o600 });
    return { privateKeyPath: tempPath, temporary: true };
  }

  const configuredPath = process.env.WECHAT_PRIVATE_KEY_PATH || config.privateKeyPath || "";
  if (!configuredPath) {
    throw new Error("Missing upload private key. Set WECHAT_PRIVATE_KEY_PATH or WECHAT_PRIVATE_KEY.");
  }
  const privateKeyPath = path.resolve(root, configuredPath);
  if (!fs.existsSync(privateKeyPath)) {
    throw new Error(`privateKeyPath does not exist: ${privateKeyPath}`);
  }
  return { privateKeyPath, temporary: false };
}

function runUpdateGuardian() {
  if (process.env.WX_SKIP_UPDATE_GUARDIAN === "1") return;
  const healthScript = path.join(__dirname, "skill-health-check.js");
  if (!fs.existsSync(healthScript)) return;
  const result = childProcess.spawnSync(process.execPath, [healthScript], {
    cwd: root,
    stdio: "inherit",
    env: Object.assign({}, process.env, { WX_HEALTH_TASK: "upload" })
  });
  if (result.status !== 0) {
    throw new Error("Update Guardian health check blocked upload. Review artifacts/wechat-skill-health-report.md.");
  }
}

function recordExperience(summary, error) {
  if (process.env.WX_EXPERIENCE_DISABLE === "1") return;
  const ledgerScript = path.join(__dirname, "wechat-experience-ledger.js");
  if (!fs.existsSync(ledgerScript)) return;
  try {
    childProcess.spawnSync(process.execPath, [
      ledgerScript,
      "record",
      "--kind", "error",
      "--task-type", "deploy-miniprogram",
      "--stage", "upload",
      "--area", "miniprogram-ci",
      "--capability", "upload",
      "--experience", error.includes("private") ? "missing-private-key" : "upload-failure",
      "--severity", "blocker",
      "--framework", "wechat-miniprogram",
      "--task", "upload Mini Program",
      "--command", "npm run wx:upload",
      "--summary", summary,
      "--error", error,
      "--source", "artifacts/wechat-upload-report.json"
    ], { cwd: root, stdio: "ignore", env: Object.assign({}, process.env, { WX_EXPERIENCE_DISABLE: "1" }) });
  } catch (ignore) {
    // Do not mask the original upload error.
  }
}

async function main() {
  ensureDir(artifactsDir);
  const report = {
    startedAt: new Date().toISOString(),
    finishedAt: "",
    status: "pending",
    projectPath: "",
    appidPresent: false,
    robot: null,
    version: "",
    desc: "",
    blockers: [],
    suggestions: [],
    docs: [
      "https://developers.weixin.qq.com/miniprogram/dev/devtools/ci.html",
      "https://www.npmjs.com/package/miniprogram-ci"
    ]
  };
  let tempKeyPath = "";

  try {
    const config = readJson(path.join(root, ".codex", "wechat-miniprogram.config.json")) || {};
    runUpdateGuardian();
    const appid = resolveAppId(config);
    const projectPath = resolveProjectPath(config);
    const robot = resolveRobot(config);
    const version = resolveVersion(config);
    const desc = resolveDesc(config);
    report.projectPath = path.relative(root, projectPath) || ".";
    report.appidPresent = Boolean(appid);
    report.robot = robot;
    report.version = version;
    report.desc = desc;

    if (!appid) throw new Error("Missing AppID. Set appid in .codex/wechat-miniprogram.config.json or WECHAT_APPID.");
    if (!fs.existsSync(projectPath)) throw new Error(`Project path does not exist: ${projectPath}`);

    const key = createPrivateKeyFile(config);
    tempKeyPath = key.temporary ? key.privateKeyPath : "";
    const ci = loadMiniProgramCi();
    const project = new ci.Project({
      appid,
      type: "miniProgram",
      projectPath,
      privateKeyPath: key.privateKeyPath,
      ignores: ["node_modules/**/*", ".git/**/*"]
    });

    const result = await ci.upload({
      project,
      version,
      desc,
      robot,
      setting: {},
      onProgressUpdate: (event) => {
        if (event && event.message) console.log(event.message);
      }
    });

    report.status = "ok";
    report.result = result || {};
  } catch (error) {
    report.status = "blocked";
    report.blockers.push(error.message);
    report.suggestions.push("Run npm run wx:inspect and npm run wx:validate before upload.");
    report.suggestions.push("Confirm AppID, private key, developer permission, IP whitelist, robot number, version, desc, miniprogram-ci dependency, and project path.");
    recordExperience("Upload failed", error.message);
    process.exitCode = 1;
    console.error(`WeChat upload failed: ${error.message}`);
  } finally {
    if (tempKeyPath) {
      try {
        fs.rmSync(tempKeyPath, { force: true });
      } catch (error) {
        report.suggestions.push("Temporary private key cleanup failed; check OS temp directory permissions.");
      }
    }
    report.finishedAt = new Date().toISOString();
    writeJson(reportPath, report);
    console.log(`WeChat upload report written: ${path.relative(root, reportPath)}`);
  }
}

main();
