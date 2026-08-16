#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const childProcess = require("child_process");

const root = process.cwd();
const artifactsDir = path.join(root, "artifacts");
const reportPath = path.join(artifactsDir, "wechat-inspect-report.json");
const ignoredDirs = new Set([
  ".git",
  "node_modules",
  ".next",
  ".nuxt",
  "dist",
  "build",
  "coverage",
  "artifacts",
  ".turbo",
  ".cache",
  ".venv",
  "vendor"
]);

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

function exists(relativePath) {
  return fs.existsSync(path.join(root, relativePath));
}

function listFiles(dir, options = {}) {
  const maxFiles = options.maxFiles || 6000;
  const maxDepth = options.maxDepth || 8;
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
      const relativePath = path.relative(root, fullPath);
      if (entry.isDirectory()) {
        if (!ignoredDirs.has(entry.name) && !entry.name.startsWith(".venv")) walk(fullPath, depth + 1);
      } else if (entry.isFile()) {
        files.push(relativePath);
      }
    }
  }

  walk(dir, 0);
  return files;
}

function detectPackageManager() {
  if (exists("pnpm-lock.yaml")) return "pnpm";
  if (exists("yarn.lock")) return "yarn";
  if (exists("package-lock.json")) return "npm";
  if (exists("bun.lockb")) return "bun";
  return "npm";
}

function dependencyNames(pkg) {
  return new Set([
    ...Object.keys((pkg && pkg.dependencies) || {}),
    ...Object.keys((pkg && pkg.devDependencies) || {}),
    ...Object.keys((pkg && pkg.peerDependencies) || {})
  ]);
}

function hasAny(deps, names) {
  return names.some((name) => deps.has(name));
}

function findFilesByName(name) {
  return listFiles(root).filter((file) => path.basename(file) === name);
}

function detectFramework(pkg, allFiles) {
  const deps = dependencyNames(pkg);
  const hasProjectConfig = allFiles.some((file) => path.basename(file) === "project.config.json");
  const hasAppJson = allFiles.some((file) => path.basename(file) === "app.json");
  const hasPagesJson = allFiles.some((file) => path.basename(file) === "pages.json");
  const frameworks = [];

  if (hasAny(deps, ["@tarojs/taro", "@tarojs/cli", "@tarojs/components"]) || allFiles.some((file) => file.includes("config/index."))) {
    frameworks.push("Taro");
  }
  if (hasAny(deps, ["@dcloudio/uni-app", "@dcloudio/vite-plugin-uni"]) || hasPagesJson || exists("manifest.json")) {
    frameworks.push("uni-app");
  }
  if ((hasProjectConfig && hasAppJson) || allFiles.some((file) => file.endsWith("app.wxss"))) {
    frameworks.push("wechat-native-miniprogram");
  }
  if (hasAny(deps, ["next"])) frameworks.push("Next.js");
  if (hasAny(deps, ["nuxt"])) frameworks.push("Nuxt");
  if (hasAny(deps, ["react", "react-dom"])) frameworks.push("React");
  if (hasAny(deps, ["vue"])) frameworks.push("Vue");
  if (hasAny(deps, ["vite"])) frameworks.push("Vite");
  if (!frameworks.length && allFiles.some((file) => /\.(html|htm)$/.test(file))) frameworks.push("H5");

  return frameworks.length ? frameworks : ["unknown"];
}

function detectMiniprogramRoots(allFiles) {
  const projectConfigs = findFilesByName("project.config.json");
  const appJsons = findFilesByName("app.json");
  const pagesJsons = findFilesByName("pages.json");
  const roots = [];

  for (const configFile of projectConfigs) {
    const fullConfig = path.join(root, configFile);
    const config = readJson(fullConfig);
    if (!config) continue;
    const configDir = path.dirname(fullConfig);
    const miniprogramRoot = config.miniprogramRoot || config.setting && config.setting.miniprogramRoot;
    roots.push({
      source: configFile,
      miniprogramRoot: miniprogramRoot || "",
      resolvedPath: miniprogramRoot ? path.resolve(configDir, miniprogramRoot) : configDir,
      appidPresent: Boolean(config.appid)
    });
  }

  for (const appJson of appJsons) {
    roots.push({
      source: appJson,
      miniprogramRoot: path.dirname(appJson),
      resolvedPath: path.join(root, path.dirname(appJson)),
      appidPresent: false
    });
  }

  const distCandidates = ["dist", "build", "dist/build", "dist/weapp", "dist/mp-weixin", "unpackage/dist/dev/mp-weixin", "unpackage/dist/build/mp-weixin"]
    .filter((dir) => fs.existsSync(path.join(root, dir)));

  return {
    projectConfigs,
    appJsons,
    pagesJsons,
    roots,
    distCandidates,
    hasAppConfig: appJsons.length > 0 || pagesJsons.length > 0,
    allConfigFiles: allFiles.filter((file) => /(^|\/)(app|pages|project\.config)\.json$/.test(file))
  };
}

function detectCloudBase(allFiles) {
  const configFiles = ["cloudbase.json", "cloudbaserc.json", "tcb.json"].filter((file) => exists(file));
  const dirs = ["cloudfunctions", "functions"].filter((dir) => fs.existsSync(path.join(root, dir)));
  return {
    detected: configFiles.length > 0 || dirs.length > 0,
    configFiles,
    directories: dirs
  };
}

function detectCi() {
  const workflowsDir = path.join(root, ".github", "workflows");
  let workflows = [];
  if (fs.existsSync(workflowsDir)) {
    workflows = fs.readdirSync(workflowsDir).filter((file) => /\.(ya?ml)$/.test(file));
  }
  return {
    detected: workflows.length > 0,
    workflows
  };
}

function detectScripts(pkg) {
  const scripts = (pkg && pkg.scripts) || {};
  const names = ["build", "dev", "lint", "test", "typecheck"];
  return Object.fromEntries(names.map((name) => [name, Boolean(scripts[name])]));
}

function isTextFile(file) {
  return /\.(js|jsx|ts|tsx|vue|svelte|json|wxml|wxss|wxs|css|scss|less|html|md|yml|yaml|env|config|txt)$/i.test(file);
}

function isSkillImplementationFile(file) {
  return file.startsWith(".codex/skills/wechat-miniprogram-auto-port-deploy/");
}

function scanRiskFiles(allFiles) {
  const patterns = [
    { id: "dom-window", severity: "warn", regex: /\bwindow\b/, message: "DOM-only API window found." },
    { id: "dom-document", severity: "warn", regex: /\bdocument\b/, message: "DOM-only API document found." },
    { id: "dom-navigator", severity: "warn", regex: /\bnavigator\b/, message: "Browser navigator API found." },
    { id: "location-href", severity: "warn", regex: /\blocation\.href\b/, message: "Browser navigation API location.href found." },
    { id: "history-push-state", severity: "warn", regex: /\bhistory\.pushState\b/, message: "Browser history.pushState found." },
    { id: "browser-storage", severity: "warn", regex: /\b(localStorage|sessionStorage)\b/, message: "Browser storage found; use wx/Taro/uni storage adapter." },
    { id: "event-listener", severity: "warn", regex: /\baddEventListener\b/, message: "DOM event listener found." },
    { id: "query-selector", severity: "warn", regex: /\bquerySelector(All)?\b/, message: "DOM querySelector usage found." },
    { id: "fetch", severity: "warn", regex: /\bfetch\s*\(/, message: "Direct fetch found; use wx/Taro/uni request adapter." },
    { id: "xhr", severity: "warn", regex: /\bXMLHttpRequest\b/, message: "XMLHttpRequest found; use wx/Taro/uni request adapter." },
    { id: "process-env", severity: "warn", regex: /\bprocess\.env\b/, message: "process.env usage found; ensure no frontend secret exposure." },
    { id: "app-secret", severity: "warn", regex: /\b(AppSecret|appsecret|app_secret|APP_SECRET)\b/, message: "AppSecret keyword found; confirm it is documentation or backend-only and not a real secret." },
    { id: "private-key-content", severity: "blocker", regex: /-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/, message: "Private key content found." },
    { id: "payment-key", severity: "blocker", regex: /\b(mchKey|apiV3Key|merchantKey|paymentSecret|paySecret)\b/i, message: "Payment key keyword found." },
    { id: "hardcoded-domain", severity: "info", regex: /https?:\/\/[A-Za-z0-9.-]+\.[A-Za-z]{2,}/, message: "Hardcoded domain found; verify WeChat legal domain settings." }
  ];
  const risks = [];
  const textFiles = allFiles.filter((file) => isTextFile(file) && !isSkillImplementationFile(file)).slice(0, 2500);

  for (const relativeFile of textFiles) {
    const fullFile = path.join(root, relativeFile);
    let stat;
    try {
      stat = fs.statSync(fullFile);
      if (stat.size > 512 * 1024) continue;
    } catch (error) {
      continue;
    }
    let text;
    try {
      text = fs.readFileSync(fullFile, "utf8");
    } catch (error) {
      continue;
    }
    for (const pattern of patterns) {
      if (pattern.regex.test(text)) {
        risks.push({
          id: pattern.id,
          severity: pattern.severity,
          file: relativeFile,
          message: pattern.message
        });
      }
    }
  }

  for (const file of allFiles) {
    if (isSkillImplementationFile(file)) continue;
    const base = path.basename(file);
    if (/^private\..*\.key$/i.test(base) || /\.key$/i.test(base)) {
      risks.push({
        id: "private-key-file",
        severity: "blocker",
        file,
        message: "Private key-like file exists in repository tree; confirm it is ignored and not committed."
      });
    }
    if (/\.pem$/i.test(base)) {
      risks.push({
        id: "pem-file",
        severity: "warn",
        file,
        message: "PEM file exists; confirm it is not a private key and is not committed when sensitive."
      });
    }
    if (/^\.env(\.|$)/.test(base)) {
      risks.push({
        id: "env-file",
        severity: "warn",
        file,
        message: ".env file exists; confirm it is ignored and contains no committed secrets."
      });
    }
  }

  return risks;
}

function gitStatusSummary() {
  try {
    const output = childProcess.execFileSync("git", ["status", "--short"], { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    return output.trim().split("\n").filter(Boolean).slice(0, 200);
  } catch (error) {
    return [];
  }
}

function main() {
  ensureDir(artifactsDir);
  const packageJsonPath = path.join(root, "package.json");
  const pkg = readJson(packageJsonPath);
  const allFiles = listFiles(root);
  const report = {
    generatedAt: new Date().toISOString(),
    root,
    packageManager: detectPackageManager(),
    packageJson: {
      exists: Boolean(pkg),
      name: pkg && pkg.name || "",
      version: pkg && pkg.version || "",
      scripts: pkg && pkg.scripts || {}
    },
    frameworks: detectFramework(pkg, allFiles),
    miniprogram: detectMiniprogramRoots(allFiles),
    cloudBase: detectCloudBase(allFiles),
    ci: detectCi(),
    scripts: detectScripts(pkg),
    risks: scanRiskFiles(allFiles),
    gitStatus: gitStatusSummary()
  };

  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  const blockers = report.risks.filter((risk) => risk.severity === "blocker").length;
  console.log(`WeChat inspect report written: ${path.relative(root, reportPath)}`);
  console.log(`Detected frameworks: ${report.frameworks.join(", ")}`);
  console.log(`Risks: ${report.risks.length} total, ${blockers} blocker(s)`);
}

main();
