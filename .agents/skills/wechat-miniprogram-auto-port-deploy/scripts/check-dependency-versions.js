#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const childProcess = require("child_process");

const root = process.cwd();
const artifactsDir = path.join(root, "artifacts");
const jsonReportPath = path.join(artifactsDir, "dependency-version-report.json");
const mdReportPath = path.join(artifactsDir, "dependency-version-report.md");
const officialReportPath = path.join(artifactsDir, "official-update-report.json");
const guardianJsonPath = path.join(artifactsDir, "update-guardian-report.json");
const guardianMdPath = path.join(artifactsDir, "update-guardian-report.md");

const packages = [
  { name: "miniprogram-ci", risk: "high", autoUpdateAllowed: false },
  { name: "@tarojs/cli", risk: "high", autoUpdateAllowed: false },
  { name: "@tarojs/taro", risk: "high", autoUpdateAllowed: false },
  { name: "@dcloudio/uni-app", risk: "high", autoUpdateAllowed: false },
  { name: "@vue/runtime-core", risk: "medium", autoUpdateAllowed: false },
  { name: "react", risk: "medium", autoUpdateAllowed: false },
  { name: "typescript", risk: "medium", autoUpdateAllowed: false },
  { name: "weui-miniprogram", risk: "medium", autoUpdateAllowed: false },
  { name: "tdesign-miniprogram", risk: "medium", autoUpdateAllowed: false },
  { name: "@cloudbase/cli", risk: "high", autoUpdateAllowed: false },
  { name: "@cloudbase/framework-plugin-mp", risk: "high", autoUpdateAllowed: false }
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

function normalizeVersion(version) {
  return String(version || "").replace(/^[~^<>=\s]+/, "").trim();
}

function semverParts(version) {
  const match = normalizeVersion(version).match(/^(\d+)\.(\d+)\.(\d+)/);
  return match ? match.slice(1).map(Number) : null;
}

function compareSemver(a, b) {
  const pa = semverParts(a);
  const pb = semverParts(b);
  if (!pa || !pb) return 0;
  for (let i = 0; i < 3; i += 1) {
    if (pa[i] > pb[i]) return 1;
    if (pa[i] < pb[i]) return -1;
  }
  return 0;
}

function versionChangeType(current, latest) {
  const a = semverParts(current);
  const b = semverParts(latest);
  if (!a || !b) return "unknown";
  if (b[0] > a[0]) return "major";
  if (b[1] > a[1]) return "minor";
  if (b[2] > a[2]) return "patch";
  return "none";
}

function npmViewLatest(pkgName) {
  try {
    return childProcess.execFileSync("npm", ["view", pkgName, "version"], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 20000
    }).trim();
  } catch (error) {
    return "";
  }
}

function getCurrent(pkg, packageName) {
  const sections = ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"];
  for (const section of sections) {
    if (pkg[section] && pkg[section][packageName]) {
      return { version: pkg[section][packageName], section };
    }
  }
  return { version: "", section: "" };
}

function recommendedAction(item) {
  if (item.status === "missing") return "No action unless this package is required by the selected framework or workflow.";
  if (item.status === "unknown") return "Retry with network access; do not make dependency conclusions from this result.";
  if (item.status === "up-to-date") return "No action.";
  if (item.changeType === "major") return "Manual confirmation required before upgrade.";
  return "Review changelog and consider upgrade; do not auto-upgrade.";
}

function writeReports(report) {
  ensureDir(artifactsDir);
  fs.writeFileSync(jsonReportPath, JSON.stringify(report, null, 2));
  const lines = [
    "# Dependency Version Report",
    "",
    `Generated at: ${report.generatedAt}`,
    `Package.json exists: ${report.packageJsonExists ? "yes" : "no"}`,
    "",
    "| Package | Current | Latest | Status | Change | Risk | Recommended Action |",
    "|---|---:|---:|---|---|---|---|"
  ];
  for (const item of report.packages) {
    lines.push(`| \`${item.package}\` | ${item.current || "-"} | ${item.latest || "-"} | ${item.status} | ${item.changeType || "-"} | ${item.risk} | ${item.recommendedAction} |`);
  }
  fs.writeFileSync(mdReportPath, lines.join("\n") + "\n");
}

function writeGuardianAggregate(dependencyReport) {
  const official = readJson(officialReportPath);
  const officialSummary = official && official.summary ? official.summary : { total: 0, reachable: 0, unreachable: 0, changed: 0, highRiskChanges: 0 };
  const dependencySummary = {
    total: dependencyReport.packages.length,
    outdated: dependencyReport.packages.filter((item) => item.status === "outdated").length,
    unknown: dependencyReport.packages.filter((item) => item.status === "unknown").length,
    majorChanges: dependencyReport.packages.filter((item) => item.changeType === "major").length
  };
  const manualConfirmations = [];
  if (officialSummary.highRiskChanges > 0) manualConfirmations.push("High-risk official documentation changes detected.");
  for (const item of dependencyReport.packages) {
    if (item.changeType === "major") manualConfirmations.push(`Major version change requires confirmation: ${item.package}`);
    if (item.package === "miniprogram-ci" && item.status === "unknown") manualConfirmations.push("miniprogram-ci latest version is unknown; retry before deploy/upload.");
  }
  const aggregate = {
    generatedAt: new Date().toISOString(),
    officialUpdateSummary: officialSummary,
    dependencySummary,
    conservativeMode: Boolean(official && official.conservativeMode),
    manualConfirmations,
    reports: {
      official: "artifacts/official-update-report.json",
      dependency: "artifacts/dependency-version-report.json"
    }
  };
  fs.writeFileSync(guardianJsonPath, JSON.stringify(aggregate, null, 2));
  fs.writeFileSync(guardianMdPath, [
    "# Update Guardian Report",
    "",
    `Generated at: ${aggregate.generatedAt}`,
    "",
    "## Official Updates",
    "",
    `- Reachable: ${officialSummary.reachable}/${officialSummary.total}`,
    `- Changed: ${officialSummary.changed}`,
    `- High-risk changes: ${officialSummary.highRiskChanges}`,
    "",
    "## Dependency Versions",
    "",
    `- Watchlisted packages: ${dependencySummary.total}`,
    `- Outdated: ${dependencySummary.outdated}`,
    `- Unknown: ${dependencySummary.unknown}`,
    `- Major changes: ${dependencySummary.majorChanges}`,
    "",
    "## Manual Confirmations",
    "",
    manualConfirmations.length ? manualConfirmations.map((item) => `- ${item}`).join("\n") : "- None.",
    ""
  ].join("\n"));
}

function main() {
  const pkg = readJson(path.join(root, "package.json")) || {};
  const report = {
    generatedAt: new Date().toISOString(),
    packageJsonExists: Boolean(Object.keys(pkg).length),
    packages: []
  };

  for (const meta of packages) {
    const current = getCurrent(pkg, meta.name);
    let latest = "";
    let status = "missing";
    let changeType = "";
    if (current.version) {
      latest = npmViewLatest(meta.name);
      if (!latest) {
        status = "unknown";
        changeType = "unknown";
      } else if (compareSemver(current.version, latest) < 0) {
        status = "outdated";
        changeType = versionChangeType(current.version, latest);
      } else {
        status = "up-to-date";
        changeType = "none";
      }
    }
    const item = {
      package: meta.name,
      current: current.version,
      dependencySection: current.section,
      latest,
      status,
      changeType,
      risk: meta.risk,
      autoUpdateAllowed: meta.autoUpdateAllowed,
      recommendedAction: ""
    };
    item.recommendedAction = recommendedAction(item);
    report.packages.push(item);
  }

  writeReports(report);
  writeGuardianAggregate(report);
  const outdated = report.packages.filter((item) => item.status === "outdated").length;
  const unknown = report.packages.filter((item) => item.status === "unknown").length;
  console.log(`Dependency version report written: ${path.relative(root, jsonReportPath)}`);
  console.log(`Outdated: ${outdated}. Unknown: ${unknown}.`);
}

main();
