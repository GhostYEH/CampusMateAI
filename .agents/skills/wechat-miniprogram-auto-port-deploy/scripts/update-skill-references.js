#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const root = process.cwd();
const skillRoot = path.join(root, ".codex", "skills", "wechat-miniprogram-auto-port-deploy");
const artifactsDir = path.join(root, "artifacts");
const officialReportPath = path.join(artifactsDir, "official-update-report.json");
const dependencyReportPath = path.join(artifactsDir, "dependency-version-report.json");
const suggestionsPath = path.join(artifactsDir, "skill-reference-update-suggestions.md");
const guardianNotesPath = path.join(skillRoot, "references", "update-guardian-notes.md");

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

function appendIfMissing(file, text, marker) {
  const existing = fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
  if (existing.includes(marker)) return false;
  fs.appendFileSync(file, `${existing.endsWith("\n") || !existing ? "" : "\n"}${text.trim()}\n`);
  return true;
}

function buildSuggestions(official, dependency) {
  const lines = [
    "# Skill Reference Update Suggestions",
    "",
    `Generated at: ${new Date().toISOString()}`,
    "",
    "## Official Documentation Changes",
    ""
  ];
  const changed = ((official && official.items) || []).filter((item) => item.changedSinceLastCheck);
  const unknown = ((official && official.items) || []).filter((item) => !item.reachable);
  if (!changed.length) lines.push("- No changed official sources detected from stored snapshot.");
  for (const item of changed) {
    lines.push(`- ${item.risk}: ${item.url}`);
    lines.push(`  - Recommended action: ${item.recommendedAction}`);
  }
  if (unknown.length) {
    lines.push("");
    lines.push("## Unknown Or Unreachable Sources");
    for (const item of unknown) lines.push(`- ${item.url}: ${item.error || "unreachable"}`);
  }

  lines.push("");
  lines.push("## Dependency Changes");
  const outdated = ((dependency && dependency.packages) || []).filter((item) => item.status === "outdated" || item.status === "unknown");
  if (!outdated.length) lines.push("- No outdated or unknown watchlisted dependencies detected.");
  for (const item of outdated) {
    lines.push(`- \`${item.package}\`: ${item.current || "-"} -> ${item.latest || "-"} (${item.status}, ${item.changeType || "unknown"}, risk=${item.risk})`);
    lines.push(`  - Recommended action: ${item.recommendedAction}`);
  }

  lines.push("");
  lines.push("## Human Confirmation Items");
  const humanItems = [];
  for (const item of changed) {
    if (item.risk === "high-risk-change" || item.risk === "medium-risk-change") humanItems.push(`Confirm official source change: ${item.url}`);
  }
  for (const item of outdated) {
    if (item.changeType === "major" || item.status === "unknown") humanItems.push(`Confirm dependency state: ${item.package}`);
  }
  if (!humanItems.length) lines.push("- None generated.");
  for (const item of humanItems) lines.push(`- ${item}`);
  return lines.join("\n") + "\n";
}

function maybePatchNotes(suggestions) {
  if (process.env.ALLOW_SKILL_REFERENCE_PATCH !== "true") return { applied: false, file: "" };
  ensureDir(path.dirname(guardianNotesPath));
  const marker = `Update Guardian run ${new Date().toISOString().slice(0, 10)}`;
  const text = [
    "",
    `## ${marker}`,
    "",
    "The following update suggestions were generated automatically. They require human review before changing sensitive rules.",
    "",
    suggestions
  ].join("\n");
  appendIfMissing(guardianNotesPath, text, marker);
  return { applied: true, file: path.relative(root, guardianNotesPath) };
}

function main() {
  ensureDir(artifactsDir);
  const official = readJson(officialReportPath);
  const dependency = readJson(dependencyReportPath);
  const suggestions = buildSuggestions(official, dependency);
  fs.writeFileSync(suggestionsPath, suggestions);
  const patch = maybePatchNotes(suggestions);
  console.log(`Skill reference suggestions written: ${path.relative(root, suggestionsPath)}`);
  if (patch.applied) console.log(`Appended guarded notes: ${patch.file}`);
  else console.log("No Skill references were patched. Set ALLOW_SKILL_REFERENCE_PATCH=true to append guarded notes.");
}

main();
