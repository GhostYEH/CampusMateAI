#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const childProcess = require("child_process");

const root = process.cwd();
const skillScriptPrefix = ".codex/skills/wechat-miniprogram-auto-port-deploy/scripts";
const artifactsDir = path.join(root, "artifacts");
const reportPath = path.join(artifactsDir, "wechat-validation-report.json");

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

function addIssue(report, severity, id, message, file, suggestion, docs) {
  report.issues.push({ severity, id, message, file: file || "", suggestion: suggestion || "", docs: docs || [] });
}

function listFiles(startDir, options = {}) {
  const maxFiles = options.maxFiles || 7000;
  const maxDepth = options.maxDepth || 9;
  const ignored = new Set([".git", "node_modules", ".next", ".nuxt", "coverage", ".cache", ".turbo", "artifacts", ".venv", "vendor"]);
  const files = [];

  function walk(current, depth) {
    if (files.length >= maxFiles || depth > maxDepth) return;
    let entries;
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch (error) {
      return;
    }
    for (const entry of entries) {
      if (files.length >= maxFiles) return;
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (!ignored.has(entry.name) && !entry.name.startsWith(".venv")) walk(fullPath, depth + 1);
      } else if (entry.isFile()) {
        files.push(path.relative(root, fullPath));
      }
    }
  }

  walk(startDir, 0);
  return files;
}

function findUpFile(names) {
  for (const name of names) {
    const file = path.join(root, name);
    if (fs.existsSync(file)) return file;
  }
  return "";
}

function findProjectConfig(allFiles) {
  const direct = path.join(root, "project.config.json");
  if (fs.existsSync(direct)) return direct;
  const found = allFiles.find((file) => path.basename(file) === "project.config.json");
  return found ? path.join(root, found) : "";
}

function resolveMiniRoot(projectConfigPath, config) {
  const stored = process.env.WECHAT_PROJECT_PATH || "";
  if (stored) return path.resolve(root, stored);
  if (config && config.miniprogramRoot) return path.resolve(path.dirname(projectConfigPath), config.miniprogramRoot);
  return projectConfigPath ? path.dirname(projectConfigPath) : root;
}

function pageFileExists(miniRoot, pagePath) {
  const candidates = [".js", ".ts", ".wxml", ".vue", ".tsx", ".jsx"].map((ext) => path.join(miniRoot, `${pagePath}${ext}`));
  return candidates.some((file) => fs.existsSync(file));
}

function validateAppConfig(report, miniRoot) {
  const appJsonPath = path.join(miniRoot, "app.json");
  const pagesJsonPath = path.join(miniRoot, "pages.json");
  const appJson = readJson(appJsonPath);
  const pagesJson = readJson(pagesJsonPath);

  if (!appJson && !pagesJson) {
    addIssue(report, "blocker", "missing-app-or-pages-config", "Neither app.json nor pages.json exists in the resolved Mini Program root.", path.relative(root, miniRoot), "Create app.json for native/Taro output or pages.json for uni-app output.");
    return;
  }

  const configFile = appJson ? appJsonPath : pagesJsonPath;
  const config = appJson || pagesJson;
  const pages = Array.isArray(config.pages)
    ? config.pages.map((entry) => typeof entry === "string" ? entry : entry && entry.path).filter(Boolean)
    : [];

  if (!pages.length) {
    addIssue(report, "blocker", "missing-pages", "No pages were declared.", path.relative(root, configFile), "Add at least one page path.");
  }

  for (const page of pages) {
    if (!pageFileExists(miniRoot, page)) {
      addIssue(report, "blocker", "missing-page-file", `Declared page does not have a matching page file: ${page}`, path.relative(root, configFile), "Create the page file or remove the config entry.");
    }
  }

  const tabList = config.tabBar && Array.isArray(config.tabBar.list) ? config.tabBar.list : [];
  for (const item of tabList) {
    if (!item || !item.pagePath) continue;
    if (!pages.includes(item.pagePath)) {
      addIssue(report, "blocker", "tabbar-page-not-declared", `tabBar page is not listed in pages: ${item.pagePath}`, path.relative(root, configFile), "Add the tabBar page to pages or correct pagePath.");
    }
    if (!pageFileExists(miniRoot, item.pagePath)) {
      addIssue(report, "blocker", "tabbar-page-missing", `tabBar page file is missing: ${item.pagePath}`, path.relative(root, configFile), "Create the tabBar page file.");
    }
  }
}

function validatePackageScripts(report) {
  const packageJsonPath = path.join(root, "package.json");
  const pkg = readJson(packageJsonPath);
  const required = {
    "wx:setup": `node ${skillScriptPrefix}/setup-wechat-config.js`,
    "wx:secrets-init": `node ${skillScriptPrefix}/setup-wechat-secrets.js`,
    "wx:inspect": `node ${skillScriptPrefix}/inspect-project.js`,
    "wx:validate": `node ${skillScriptPrefix}/validate-miniprogram.js`,
    "wx:preview": `node ${skillScriptPrefix}/wx-preview.js`,
    "wx:upload": `node ${skillScriptPrefix}/wx-upload.js`,
    "wx:deploy": `node ${skillScriptPrefix}/wx-deploy.js`,
    "wx:review": `node ${skillScriptPrefix}/generate-review-materials.js`
  };

  if (!pkg) {
    addIssue(report, "warn", "missing-package-json", "package.json is missing; npm scripts are unavailable.", "package.json", "Create package.json or run wx:setup from node directly.");
    return;
  }

  const missing = Object.keys(required).filter((name) => !pkg.scripts || !pkg.scripts[name]);
  if (missing.length) {
    addIssue(report, "warn", "missing-wx-scripts", `Missing package scripts: ${missing.join(", ")}`, "package.json", "Add the generated wx:* scripts.");
    if (process.env.WX_VALIDATE_AUTO_FIX !== "0") {
      pkg.scripts = pkg.scripts || {};
      for (const name of missing) pkg.scripts[name] = required[name];
      writeJson(packageJsonPath, pkg);
      report.autoFixes.push({ file: "package.json", message: `Added missing wx scripts: ${missing.join(", ")}` });
    }
  }
}

function gitTrackedFiles() {
  try {
    const output = childProcess.execFileSync("git", ["ls-files"], { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    return output.split("\n").filter(Boolean);
  } catch (error) {
    return [];
  }
}

function isTextFile(file) {
  return /\.(js|jsx|ts|tsx|vue|wxml|wxss|wxs|css|scss|less|json|html|md|yml|yaml|env|txt)$/i.test(file);
}

function isSkillImplementationFile(file) {
  return file.startsWith(".codex/skills/wechat-miniprogram-auto-port-deploy/");
}

function scanCompatibility(report, allFiles) {
  const patterns = [
    { id: "window", severity: "warn", regex: /\bwindow\b/, message: "window is browser-only; use a platform adapter." },
    { id: "document", severity: "warn", regex: /\bdocument\b/, message: "document is browser-only; use Mini Program APIs/components." },
    { id: "navigator", severity: "warn", regex: /\bnavigator\b/, message: "navigator is browser-only in most Mini Program contexts." },
    { id: "location-href", severity: "warn", regex: /\blocation\.href\b/, message: "location.href is browser-only; use Mini Program navigation." },
    { id: "history-push-state", severity: "warn", regex: /\bhistory\.pushState\b/, message: "history.pushState is browser-only; use Mini Program routing." },
    { id: "local-storage", severity: "warn", regex: /\blocalStorage\b/, message: "localStorage is browser-only; use wx/Taro/uni storage." },
    { id: "session-storage", severity: "warn", regex: /\bsessionStorage\b/, message: "sessionStorage is browser-only; use wx/Taro/uni storage and avoid sensitive data." },
    { id: "add-event-listener", severity: "warn", regex: /\baddEventListener\b/, message: "DOM addEventListener usage may not work in Mini Program." },
    { id: "query-selector", severity: "warn", regex: /\bquerySelector(All)?\b/, message: "DOM querySelector usage may not work; use selector query APIs when confirmed." },
    { id: "canvas-dom", severity: "warn", regex: /\b(canvas\.getContext|HTMLCanvasElement)\b/, message: "Canvas DOM usage needs Mini Program canvas adaptation." },
    { id: "fetch", severity: "warn", regex: /\bfetch\s*\(/, message: "Direct fetch should be wrapped with wx/Taro/uni request." },
    { id: "xhr", severity: "warn", regex: /\bXMLHttpRequest\b/, message: "XMLHttpRequest should be wrapped with wx/Taro/uni request." },
    { id: "web-sdk", severity: "warn", regex: /\b(firebase|supabase|amplitude|gtag|google\.maps|mapboxgl)\b/i, message: "Web-only SDK may be incompatible with Mini Program." },
    { id: "app-secret", severity: "warn", regex: /\b(AppSecret|appsecret|app_secret|APP_SECRET)\b/, message: "AppSecret keyword found; verify it is documentation or backend-only and never a real secret." },
    { id: "sensitive-session-key", severity: "warn", regex: /\bsession_key\b/, message: "session_key keyword found; verify it is backend-only and never stored in frontend." },
    { id: "payment-key", severity: "blocker", regex: /\b(mchKey|apiV3Key|merchantKey|paymentSecret|paySecret)\b/i, message: "Payment key keyword found; payment keys must stay backend-only." },
    { id: "private-key-content", severity: "blocker", regex: /-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/, message: "Private key content found; never commit private key content." },
    { id: "wechat-private-key-env", severity: "blocker", regex: /WECHAT_PRIVATE_KEY\s*=\s*['"]?-----BEGIN/, message: "WECHAT_PRIVATE_KEY appears written to disk; use CI secret/env only." }
  ];

  for (const relativeFile of allFiles.filter((file) => isTextFile(file) && !isSkillImplementationFile(file)).slice(0, 3000)) {
    const fullPath = path.join(root, relativeFile);
    let stat;
    try {
      stat = fs.statSync(fullPath);
      if (stat.size > 512 * 1024) continue;
    } catch (error) {
      continue;
    }
    let text;
    try {
      text = fs.readFileSync(fullPath, "utf8");
    } catch (error) {
      continue;
    }
    for (const pattern of patterns) {
      if (pattern.regex.test(text)) {
        addIssue(report, pattern.severity, pattern.id, pattern.message, relativeFile, "Replace with a Mini Program-safe adapter or move sensitive logic to backend/cloud.");
      }
    }
  }
}

function scanSecurityFiles(report, allFiles) {
  const tracked = new Set(gitTrackedFiles());
  for (const file of allFiles) {
    if (isSkillImplementationFile(file)) continue;
    const base = path.basename(file);
    if (/^private\..*\.key$/i.test(base) || /\.key$/i.test(base)) {
      const severity = tracked.has(file) ? "blocker" : "warn";
      addIssue(report, severity, "private-key-file-risk", `Private key-like file ${tracked.has(file) ? "is tracked" : "exists"}: ${file}`, file, "Remove from git history if tracked, store outside repo or in CI secret.");
    }
    if (/\.pem$/i.test(base)) {
      const severity = tracked.has(file) ? "warn" : "info";
      addIssue(report, severity, "pem-file-risk", `PEM file ${tracked.has(file) ? "is tracked" : "exists"}: ${file}`, file, "Confirm it is not a private key or payment certificate before committing.");
    }
    if (/^\.env(\.|$)/.test(base)) {
      const severity = tracked.has(file) ? "blocker" : "warn";
      addIssue(report, severity, "env-file-risk", `.env file ${tracked.has(file) ? "is tracked" : "exists"}: ${file}`, file, "Ensure .env files are ignored and do not contain committed secrets.");
    }
  }
}

function checkPackageSize(report, miniRoot) {
  let total = 0;
  for (const relativeFile of listFiles(miniRoot, { maxFiles: 12000, maxDepth: 10 })) {
    try {
      total += fs.statSync(path.join(root, relativeFile)).size;
    } catch (error) {
      continue;
    }
  }
  report.packageSize = {
    miniRoot: path.relative(root, miniRoot),
    bytes: total,
    megabytes: Number((total / 1024 / 1024).toFixed(2))
  };
  if (total > 1.8 * 1024 * 1024) {
    addIssue(report, "warn", "package-size-risk", `Mini Program root is about ${report.packageSize.megabytes} MB before official packaging.`, path.relative(root, miniRoot), "Check official package limits and consider subpackages, asset compression, and lazy loading.");
  }
}

function platformReminders(report, config) {
  const features = config.features || {};
  addIssue(report, "info", "request-domain-reminder", "Verify request legal domains in WeChat backend.", "", "Configure request domains before preview/upload testing.", ["https://developers.weixin.qq.com/miniprogram/dev/framework/ability/network.html"]);
  if (features.file) {
    addIssue(report, "info", "upload-download-domain-reminder", "Verify uploadFile and downloadFile legal domains separately.", "", "Configure upload/download domains and validate file privacy scope.");
  }
  if (features.websocket) {
    addIssue(report, "info", "socket-domain-reminder", "Verify WebSocket legal domain.", "", "Configure socket domain and reconnect behavior.");
  }
  if (features.location || features.phoneNumber || features.subscribeMessage || features.payment || (config.privacy && config.privacy.collectsUserData)) {
    addIssue(report, "warn", "privacy-permission-reminder", "Capability requires current official permission/privacy checks.", "", "Run Runtime Documentation Lookup and update privacy/review materials.");
  }
  if (features.map) {
    addIssue(report, "info", "map-reminder", "Map capability may require location permission and domain checks.", "", "Confirm component/API docs and privacy disclosure.");
  }
}

function inheritedAutoFixes() {
  if (!process.env.WX_VALIDATE_PREVIOUS_FIXES) return [];
  try {
    const parsed = JSON.parse(process.env.WX_VALIDATE_PREVIOUS_FIXES);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

function recordExperience(stage, area, summary, error, source) {
  if (process.env.WX_EXPERIENCE_DISABLE === "1") return;
  const ledgerScript = path.join(__dirname, "wechat-experience-ledger.js");
  if (!fs.existsSync(ledgerScript)) return;
  childProcess.spawnSync(process.execPath, [
    ledgerScript,
    "record",
    "--kind", "validation",
    "--task-type", "debug",
    "--stage", stage,
    "--area", area,
    "--capability", "unknown",
    "--experience", "missing-miniprogram-config",
    "--severity", "blocker",
    "--framework", "wechat-miniprogram",
    "--task", "validate-miniprogram",
    "--command", "npm run wx:validate",
    "--summary", summary,
    "--error", error,
    "--source", source || "artifacts/wechat-validation-report.json"
  ], { cwd: root, stdio: "ignore", env: Object.assign({}, process.env, { WX_EXPERIENCE_DISABLE: "1" }) });
}

function runExperienceAudit() {
  if (process.env.WX_EXPERIENCE_AUTO_AUDIT === "0") return;
  const ledgerScript = path.join(__dirname, "wechat-experience-ledger.js");
  if (!fs.existsSync(ledgerScript)) return;
  childProcess.spawnSync(process.execPath, [ledgerScript, "audit"], {
    cwd: root,
    stdio: "ignore",
    env: Object.assign({}, process.env, { WX_EXPERIENCE_AUTO_AUDIT: "0" })
  });
}

function main() {
  ensureDir(artifactsDir);
  const initialAutoFixes = inheritedAutoFixes();
  const report = {
    generatedAt: new Date().toISOString(),
    root,
    status: "ok",
    miniProgramRoot: "",
    packageSize: null,
    autoFixes: initialAutoFixes.slice(),
    issues: []
  };
  const allFiles = listFiles(root);
  const persistentConfig = readJson(path.join(root, ".codex", "wechat-miniprogram.config.json")) || {};
  const projectConfigPath = findProjectConfig(allFiles);
  const projectConfig = projectConfigPath ? readJson(projectConfigPath) : null;

  if (!projectConfigPath) {
    addIssue(report, "blocker", "missing-project-config", "project.config.json is missing.", "project.config.json", "Create project.config.json or configure the framework build output path.");
  } else if (!projectConfig) {
    addIssue(report, "blocker", "invalid-project-config", "project.config.json is not valid JSON.", path.relative(root, projectConfigPath), "Fix JSON syntax.");
  }

  const miniRoot = projectConfigPath ? resolveMiniRoot(projectConfigPath, projectConfig) : path.resolve(root, persistentConfig.miniprogramRoot || persistentConfig.distRoot || "");
  report.miniProgramRoot = path.relative(root, miniRoot) || ".";
  if (!fs.existsSync(miniRoot)) {
    addIssue(report, "blocker", "missing-miniprogram-root", "Resolved Mini Program root does not exist.", report.miniProgramRoot, "Run build or set miniprogramRoot/distRoot/WECHAT_PROJECT_PATH correctly.");
  } else {
    validateAppConfig(report, miniRoot);
    checkPackageSize(report, miniRoot);
  }

  validatePackageScripts(report);
  scanSecurityFiles(report, allFiles);
  scanCompatibility(report, allFiles);
  platformReminders(report, persistentConfig);

  const blockerCount = report.issues.filter((issue) => issue.severity === "blocker").length;
  const warningCount = report.issues.filter((issue) => issue.severity === "warn").length;
  report.status = blockerCount ? "blocked" : warningCount ? "warning" : "ok";
  writeJson(reportPath, report);

  if (report.autoFixes.length > initialAutoFixes.length && process.env.WX_VALIDATE_RERUN !== "1") {
    console.log("Auto-fixes applied; re-running validation once.");
    const rerun = childProcess.spawnSync(process.execPath, [__filename], {
      cwd: root,
      stdio: "inherit",
      env: Object.assign({}, process.env, {
        WX_VALIDATE_RERUN: "1",
        WX_VALIDATE_PREVIOUS_FIXES: JSON.stringify(report.autoFixes)
      })
    });
    process.exit(rerun.status === null ? 1 : rerun.status);
  }

  console.log(`WeChat validation report written: ${path.relative(root, reportPath)}`);
  console.log(`Status: ${report.status}. Blockers: ${blockerCount}. Warnings: ${warningCount}. Auto-fixes: ${report.autoFixes.length}.`);
  if (blockerCount) {
    const blockerSummary = report.issues
      .filter((issue) => issue.severity === "blocker")
      .slice(0, 5)
      .map((issue) => `${issue.id}: ${issue.message}`)
      .join("; ");
    recordExperience("validate", "config", `Validation blocked with ${blockerCount} blocker(s)`, blockerSummary, "artifacts/wechat-validation-report.json");
    process.exitCode = 1;
  }
  runExperienceAudit();
}

main();
