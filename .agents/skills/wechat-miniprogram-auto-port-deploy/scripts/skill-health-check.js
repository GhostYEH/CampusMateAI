#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const childProcess = require("child_process");

const root = process.cwd();
const installedSkillRoot = path.join(root, ".codex", "skills", "wechat-miniprogram-auto-port-deploy");
const repoSkillRoot = fs.existsSync(path.join(root, "SKILL.md")) && fs.existsSync(path.join(root, "scripts"))
  ? root
  : installedSkillRoot;
const skillRoot = repoSkillRoot;
const scriptDir = path.join(skillRoot, "scripts");
const artifactsDir = path.join(root, "artifacts");
const jsonReportPath = path.join(artifactsDir, "wechat-skill-health-report.json");
const mdReportPath = path.join(artifactsDir, "wechat-skill-health-report.md");
const guardianJsonPath = path.join(artifactsDir, "update-guardian-report.json");
const guardianMdPath = path.join(artifactsDir, "update-guardian-report.md");

const requiredSkillFiles = [
  "SKILL.md",
  "references/update-guardian-policy.md",
  "references/official-update-sources.md",
  "references/version-watchlist.md",
  "scripts/check-official-updates.js",
  "scripts/check-dependency-versions.js",
  "scripts/setup-wechat-secrets.js",
  "scripts/update-skill-references.js",
  "scripts/skill-health-check.js",
  "assets/github-actions.wechat-skill-update-check.yml"
];

const requiredScripts = [
  "wx:setup",
  "wx:secrets-init",
  "wx:inspect",
  "wx:validate",
  "wx:preview",
  "wx:upload",
  "wx:deploy",
  "wx:review",
  "wx:experience-audit",
  "wx:update-check",
  "wx:health-check"
];

const requiredGitignore = [
  "private.*.key",
  "*.pem",
  ".env",
  ".env.*",
  "artifacts/",
  "official-docs-snapshot.local.json",
  "*.local-snapshot.json",
  ".codex/wechat-miniprogram.secrets.json",
  ".codex/wechat-miniprogram-experience-ledger.json",
  ".codex/wechat-miniprogram-experience-index.json",
  ".wechat-private/",
  "*.secret.json"
];

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

function readText(file) {
  try {
    return fs.readFileSync(file, "utf8");
  } catch (error) {
    return "";
  }
}

function runNodeScript(file) {
  const result = childProcess.spawnSync(process.execPath, [file], {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    env: process.env
  });
  return {
    file: path.relative(root, file),
    status: result.status === 0 ? "ok" : "failed",
    stdout: (result.stdout || "").slice(0, 4000),
    stderr: (result.stderr || "").slice(0, 4000)
  };
}

function issue(severity, id, message, file, recommendedAction) {
  return { severity, id, message, file: file || "", recommendedAction: recommendedAction || "" };
}

function checkStructure(issues) {
  for (const file of requiredSkillFiles) {
    const full = path.join(skillRoot, file);
    if (!fs.existsSync(full)) {
      issues.push(issue(file === "SKILL.md" ? "blocker" : "warn", "missing-skill-file", `Missing ${file}`, file, "Restore required Update Guardian file."));
    }
  }
}

function checkSkillMd(issues) {
  const text = readText(path.join(skillRoot, "SKILL.md"));
  if (!text) {
    issues.push(issue("blocker", "missing-skill-md", "SKILL.md is missing or unreadable.", "SKILL.md", "Restore SKILL.md."));
    return;
  }
  if (!text.includes("## Update Guardian")) {
    issues.push(issue("blocker", "missing-update-guardian-section", "SKILL.md lacks Update Guardian section.", "SKILL.md", "Append Update Guardian policy."));
  }
}

function checkAgents(issues) {
  const text = readText(path.join(root, "AGENTS.md"));
  if (!text.includes("WeChat Mini Program Rules")) {
    issues.push(issue("warn", "missing-wechat-agents-rules", "AGENTS.md lacks WeChat Mini Program Rules.", "AGENTS.md", "Append WeChat Mini Program Rules."));
  }
  if (!text.includes("Update Guardian Rules")) {
    issues.push(issue("warn", "missing-update-guardian-agents-rules", "AGENTS.md lacks Update Guardian Rules.", "AGENTS.md", "Append Update Guardian Rules."));
  }
}

function checkPackageScripts(issues) {
  const pkg = readJson(path.join(root, "package.json"));
  if (!pkg) {
    issues.push(issue("blocker", "missing-package-json", "package.json missing or invalid.", "package.json", "Create package.json with wx scripts."));
    return;
  }
  for (const name of requiredScripts) {
    if (!pkg.scripts || !pkg.scripts[name]) {
      issues.push(issue("warn", "missing-package-script", `Missing package script ${name}.`, "package.json", "Append missing wx script."));
    }
  }
}

function checkGitignore(issues) {
  const text = readText(path.join(root, ".gitignore"));
  for (const entry of requiredGitignore) {
    if (!text.includes(entry)) {
      issues.push(issue("warn", "missing-gitignore-entry", `.gitignore missing ${entry}.`, ".gitignore", "Append missing ignore rule."));
    }
  }
}

function checkSecretRisk(issues) {
  const suspicious = [];
  const scanFiles = ["AGENTS.md", "package.json", ".codex/wechat-miniprogram.config.json"];
  for (const file of scanFiles) {
    const text = readText(path.join(root, file));
    if (/-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/.test(text)) suspicious.push(file);
    if (/(mchKey|apiV3Key|merchantKey|paymentSecret|paySecret)\s*[:=]\s*['"][^'"]+/i.test(text)) suspicious.push(file);
  }
  for (const file of suspicious) {
    issues.push(issue("blocker", "secret-plaintext-risk", `Possible secret material in ${file}.`, file, "Remove secret material and rotate if committed."));
  }
}

function summarizeStatus(issues, official, dependency) {
  if (issues.some((item) => item.severity === "blocker")) return "blocked";
  if (official && official.summary && official.summary.total > 0 && official.summary.reachable === 0) return "blocked";
  const deployTask = process.env.WECHAT_DEPLOY_MODE || process.env.WX_HEALTH_TASK || "";
  const mini = dependency && dependency.packages && dependency.packages.find((item) => item.package === "miniprogram-ci");
  if (/deploy|upload|preview/.test(deployTask) && mini && mini.status === "unknown") return "blocked";
  if (issues.length) return "needs-attention";
  if (official && official.summary && official.summary.highRiskChanges > 0) return "needs-attention";
  if (dependency && dependency.packages && dependency.packages.some((item) => item.status === "outdated" || item.status === "unknown")) return "needs-attention";
  return "healthy";
}

function writeReports(report) {
  ensureDir(artifactsDir);
  fs.writeFileSync(jsonReportPath, JSON.stringify(report, null, 2));
  fs.writeFileSync(guardianJsonPath, JSON.stringify(report.updateGuardian, null, 2));
  const lines = [
    "# WeChat Skill Health Report",
    "",
    `Generated at: ${report.generatedAt}`,
    `Health status: ${report.healthStatus}`,
    "",
    "## Script Runs",
    ""
  ];
  for (const run of report.scriptRuns) lines.push(`- ${run.file}: ${run.status}`);
  lines.push("", "## Issues", "");
  if (!report.issues.length) lines.push("- None.");
  for (const item of report.issues) lines.push(`- [${item.severity}] ${item.id}: ${item.message} ${item.recommendedAction}`);
  lines.push("", "## Update Guardian Summary", "");
  lines.push(`- Official sources reachable: ${report.officialUpdateSummary.reachable}/${report.officialUpdateSummary.total}`);
  lines.push(`- Official changed sources: ${report.officialUpdateSummary.changed}`);
  lines.push(`- High-risk official changes: ${report.officialUpdateSummary.highRiskChanges}`);
  lines.push(`- Dependency outdated/unknown: ${report.dependencySummary.outdatedOrUnknown}`);
  fs.writeFileSync(mdReportPath, lines.join("\n") + "\n");
  fs.writeFileSync(guardianMdPath, [
    "# Update Guardian Report",
    "",
    `Generated at: ${report.generatedAt}`,
    `Health status: ${report.healthStatus}`,
    "",
    `Official reachable: ${report.officialUpdateSummary.reachable}/${report.officialUpdateSummary.total}`,
    `Official changes: ${report.officialUpdateSummary.changed}`,
    `High-risk changes: ${report.officialUpdateSummary.highRiskChanges}`,
    `Dependency outdated/unknown: ${report.dependencySummary.outdatedOrUnknown}`,
    ""
  ].join("\n"));
}

function main() {
  ensureDir(artifactsDir);
  const scriptRuns = [
    runNodeScript(path.join(scriptDir, "check-dependency-versions.js")),
    runNodeScript(path.join(scriptDir, "check-official-updates.js"))
  ];
  const dependency = readJson(path.join(artifactsDir, "dependency-version-report.json"));
  const official = readJson(path.join(artifactsDir, "official-update-report.json"));
  const issues = [];
  checkStructure(issues);
  checkSkillMd(issues);
  checkAgents(issues);
  checkPackageScripts(issues);
  checkGitignore(issues);
  checkSecretRisk(issues);

  for (const run of scriptRuns) {
    if (run.status !== "ok") issues.push(issue("warn", "health-subcheck-failed", `${run.file} failed.`, run.file, "Inspect stderr and rerun."));
  }

  const officialSummary = official && official.summary ? official.summary : { total: 0, reachable: 0, changed: 0, highRiskChanges: 0 };
  const dependencyItems = dependency && dependency.packages ? dependency.packages : [];
  const dependencySummary = {
    total: dependencyItems.length,
    outdatedOrUnknown: dependencyItems.filter((item) => item.status === "outdated" || item.status === "unknown").length,
    majorChanges: dependencyItems.filter((item) => item.changeType === "major").length
  };

  const report = {
    generatedAt: new Date().toISOString(),
    healthStatus: summarizeStatus(issues, official, dependency),
    issues,
    scriptRuns,
    officialUpdateSummary: officialSummary,
    dependencySummary,
    updateGuardian: {
      generatedAt: new Date().toISOString(),
      officialUpdateSummary: officialSummary,
      dependencySummary,
      issues
    }
  };
  writeReports(report);
  console.log(`WeChat skill health report written: ${path.relative(root, jsonReportPath)}`);
  console.log(`Health status: ${report.healthStatus}`);
  if (report.healthStatus === "blocked") process.exitCode = 1;
}

main();
