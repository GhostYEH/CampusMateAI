#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const childProcess = require("child_process");

const root = process.cwd();
const installedSkillRoot = path.join(root, ".codex/skills/wechat-miniprogram-auto-port-deploy");
const repoSkillRoot = fs.existsSync(path.join(root, "SKILL.md")) && fs.existsSync(path.join(root, "assets"))
  ? root
  : installedSkillRoot;
const skillRoot = repoSkillRoot;
const templatePath = path.join(skillRoot, "assets/env.example");
const envLocalPath = path.join(root, ".env.local");
const privateDir = path.join(root, ".wechat-private");
const artifactsDir = path.join(root, "artifacts");
const reportPath = path.join(artifactsDir, "wechat-secrets-init-report.json");

const requiredGitignoreEntries = [
  "private.*.key",
  "*.pem",
  ".env",
  ".env.*",
  "artifacts/",
  ".codex/wechat-miniprogram.secrets.json",
  ".codex/wechat-miniprogram-experience-ledger.json",
  ".codex/wechat-miniprogram-experience-index.json",
  ".wechat-private/",
  "*.secret.json"
];

function ensureDir(dir, mode) {
  fs.mkdirSync(dir, { recursive: true, mode });
  if (mode && process.platform !== "win32") {
    try {
      fs.chmodSync(dir, mode);
    } catch (error) {
      // Permission hardening is best effort on non-POSIX filesystems.
    }
  }
}

function writeFilePrivate(file, content) {
  fs.writeFileSync(file, content, { mode: 0o600 });
  if (process.platform !== "win32") {
    try {
      fs.chmodSync(file, 0o600);
    } catch (error) {
      // Permission hardening is best effort on non-POSIX filesystems.
    }
  }
}

function readText(file) {
  try {
    return fs.readFileSync(file, "utf8");
  } catch (error) {
    return "";
  }
}

function appendMissingGitignore(report) {
  const gitignorePath = path.join(root, ".gitignore");
  const before = readText(gitignorePath);
  const existing = new Set(before.split(/\r?\n/).map((line) => line.trim()).filter(Boolean));
  const missing = requiredGitignoreEntries.filter((entry) => !existing.has(entry));
  if (!missing.length) {
    report.actions.push({ action: "gitignore-check", status: "ok", detail: ".gitignore already contains required secret ignore rules." });
    return;
  }

  const prefix = before && !before.endsWith("\n") ? "\n" : "";
  fs.appendFileSync(gitignorePath, `${prefix}${missing.join("\n")}\n`);
  report.actions.push({ action: "gitignore-update", status: "updated", detail: `Added ${missing.length} secret ignore rule(s).`, entries: missing });
}

function envTemplate() {
  const source = readText(templatePath);
  const base = source || [
    "WECHAT_APPID=",
    "WECHAT_PRIVATE_KEY_PATH=",
    "WECHAT_PRIVATE_KEY=",
    "WECHAT_PROJECT_PATH=",
    "WECHAT_VERSION=",
    "WECHAT_DESC=",
    "WECHAT_ROBOT=1",
    "WECHAT_DEPLOY_MODE=preview",
    "TCB_ENV_ID=",
    "CLOUD_BASE_ENV_ID="
  ].join("\n");

  return [
    "# Local WeChat Mini Program secret placeholders.",
    "# This file is ignored by git. Do not paste secrets into committed files.",
    "# Prefer WECHAT_PRIVATE_KEY_PATH for local upload keys. Prefer CI Secrets for CI.",
    "# Do not put AppSecret, payment merchant keys, session_key, database passwords, or user data here unless the runtime truly needs them.",
    "",
    base.trim(),
    ""
  ].join("\n");
}

function createEnvLocal(report) {
  if (fs.existsSync(envLocalPath)) {
    if (process.platform !== "win32") {
      try {
        fs.chmodSync(envLocalPath, 0o600);
      } catch (error) {
        report.warnings.push({ id: "chmod-env-local-failed", message: ".env.local exists but chmod 0600 failed; verify file permissions manually." });
      }
    }
    report.actions.push({ action: "env-local", status: "exists", detail: ".env.local already exists; left contents unchanged." });
    return;
  }

  writeFilePrivate(envLocalPath, envTemplate());
  report.actions.push({ action: "env-local", status: "created", detail: "Created ignored .env.local placeholder with 0600 permissions when supported." });
}

function createPrivateDir(report) {
  ensureDir(privateDir, 0o700);
  const readmePath = path.join(privateDir, "README.txt");
  if (!fs.existsSync(readmePath)) {
    writeFilePrivate(readmePath, [
      "This directory is ignored by git.",
      "Use it only for local WeChat upload keys or local-only secret files.",
      "Do not commit files from this directory.",
      "Prefer CI Secrets for automation runners.",
      ""
    ].join("\n"));
  }
  report.actions.push({ action: "private-dir", status: "ready", detail: "Prepared ignored .wechat-private/ directory with local-only guidance." });
}

function gitTrackedFiles() {
  try {
    const output = childProcess.execFileSync("git", ["ls-files"], { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    return output.split("\n").filter(Boolean);
  } catch (error) {
    return [];
  }
}

function listCandidateFiles() {
  const candidates = [];
  const names = fs.readdirSync(root, { withFileTypes: true });
  for (const entry of names) {
    if (!entry.isFile()) continue;
    if (/^\.env(\.|$)/.test(entry.name) || /\.pem$/i.test(entry.name) || /\.key$/i.test(entry.name) || /\.secret\.json$/i.test(entry.name)) {
      candidates.push(entry.name);
    }
  }
  if (fs.existsSync(privateDir)) {
    for (const entry of fs.readdirSync(privateDir, { withFileTypes: true })) {
      if (entry.isFile()) candidates.push(path.join(".wechat-private", entry.name));
    }
  }
  return candidates;
}

function scanSecretRisk(report) {
  const tracked = new Set(gitTrackedFiles());
  const candidates = listCandidateFiles();
  const secretPatterns = [
    { id: "private-key-content", severity: "blocker", regex: /-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/ },
    { id: "wechat-private-key-env", severity: "blocker", regex: /WECHAT_PRIVATE_KEY\s*=\s*['"]?-----BEGIN/ },
    { id: "app-secret", severity: "blocker", regex: /\b(AppSecret|appsecret|app_secret|APP_SECRET)\s*[:=]\s*['"]?[A-Za-z0-9_-]{12,}/ },
    { id: "payment-key", severity: "blocker", regex: /\b(mchKey|apiV3Key|merchantKey|paymentSecret|paySecret)\s*[:=]\s*['"]?[A-Za-z0-9_-]{12,}/i },
    { id: "session-key", severity: "warn", regex: /\bsession_key\s*[:=]\s*['"]?[A-Za-z0-9_+/=-]{12,}/i },
    { id: "generic-env-secret", severity: "warn", regex: /^(?!#)[^\S\r\n]*[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD|PRIVATE_KEY|ACCESS_KEY|SECRET_KEY)[A-Z0-9_]*[^\S\r\n]*=[^\S\r\n]*['"]?[^'"\s#]{12,}/mi }
  ];

  for (const relative of candidates) {
    const full = path.join(root, relative);
    const base = path.basename(relative);
    const isTracked = tracked.has(relative);
    if (isTracked) {
      report.blockers.push({
        id: "tracked-secret-file",
        file: relative,
        message: "Secret-like file is tracked by git. Remove it from git history/index and rotate credentials if real secrets were committed."
      });
    }

    if (/^\.env(\.|$)/.test(base) && relative !== ".env.local") {
      report.warnings.push({ id: "extra-env-file", file: relative, message: "Extra .env file exists; confirm it is ignored and contains no real secrets." });
    }

    let text = "";
    try {
      const stat = fs.statSync(full);
      if (stat.size > 256 * 1024) continue;
      text = fs.readFileSync(full, "utf8");
    } catch (error) {
      continue;
    }

    for (const pattern of secretPatterns) {
      if (pattern.regex.test(text)) {
        const item = {
          id: pattern.id,
          file: relative,
          message: "Potential sensitive material detected. Value was not printed. Move it to CI Secret or a local-only key file outside tracked files."
        };
        if (pattern.severity === "blocker" || isTracked) report.blockers.push(item);
        else report.warnings.push(item);
      }
    }
  }
}

function main() {
  const report = {
    generatedAt: new Date().toISOString(),
    envFile: ".env.local",
    privateDir: ".wechat-private/",
    actions: [],
    warnings: [],
    blockers: [],
    nextSteps: [
      "Fill .env.local locally only, or export the same variables in your shell.",
      "Prefer WECHAT_PRIVATE_KEY_PATH pointing to a local key file under .wechat-private/ for local preview/upload.",
      "Use GitHub Secrets or CI provider secrets for WECHAT_PRIVATE_KEY in CI.",
      "Never put AppSecret, payment merchant keys, session_key, database passwords, or user privacy data in Mini Program frontend code.",
      "Run npm run wx:validate before preview/upload."
    ]
  };

  ensureDir(artifactsDir);
  appendMissingGitignore(report);
  createEnvLocal(report);
  createPrivateDir(report);
  scanSecretRisk(report);

  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

  console.log(`WeChat secrets init report written: ${path.relative(root, reportPath)}`);
  console.log(`Actions: ${report.actions.length}. Warnings: ${report.warnings.length}. Blockers: ${report.blockers.length}.`);
  if (report.blockers.length) {
    console.log("Secret setup blocked. Open the report for exact file names; secret values were not printed.");
    process.exit(1);
  }
}

main();
