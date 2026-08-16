#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const http = require("http");
const https = require("https");
const crypto = require("crypto");

const root = process.cwd();
const installedSkillRoot = path.join(root, ".codex", "skills", "wechat-miniprogram-auto-port-deploy");
const repoSkillRoot = fs.existsSync(path.join(root, "SKILL.md")) && fs.existsSync(path.join(root, "references"))
  ? root
  : installedSkillRoot;
const skillRoot = repoSkillRoot;
const sourcesPath = path.join(skillRoot, "references", "official-update-sources.md");
const artifactsDir = path.join(root, "artifacts");
const snapshotPath = path.join(artifactsDir, "official-docs-snapshot.json");
const jsonReportPath = path.join(artifactsDir, "official-update-report.json");
const mdReportPath = path.join(artifactsDir, "official-update-report.md");

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

function hash(text) {
  return crypto.createHash("sha256").update(text || "").digest("hex").slice(0, 16);
}

function extractUrls(text) {
  const matches = text.match(/https?:\/\/[^\s|)]+/g) || [];
  return Array.from(new Set(matches.map((url) => url.replace(/[>,.]$/, ""))));
}

function riskForUrl(url) {
  const lower = url.toLowerCase();
  if (/ci\.html|miniprogram-ci|api|framework|cloudbase|framework-plugin-mp/.test(lower)) return "high-risk-change";
  if (/codex|agents-md|customization/.test(lower)) return "medium-risk-change";
  if (/github\.com\/wechat-miniprogram|tdesign/.test(lower)) return "medium-risk-change";
  return "low-risk-change";
}

function recommendedAction(item) {
  if (!item.reachable) return "Network/source unavailable. Enter Conservative Mode for dependent tasks and retry later.";
  if (!item.changedSinceLastCheck) return "No change detected from stored snapshot.";
  if (item.risk === "high-risk-change") return "Human confirmation required before changing API, privacy, upload, review, CloudBase, or miniprogram-ci logic.";
  if (item.risk === "medium-risk-change") return "Review change before updating Skill or AGENTS rules.";
  return "Review when touching related examples or optional guidance.";
}

function fetchUrl(url, method) {
  return new Promise((resolve) => {
    const lib = url.startsWith("https:") ? https : http;
    let settled = false;
    let received = 0;
    const req = lib.request(url, {
      method,
      headers: {
        "user-agent": "Codex-WeChat-Update-Guardian/1.0"
      }
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => {
        if (method === "GET" && received < 512 * 1024) {
          chunks.push(chunk);
          received += chunk.length;
        }
      });
      res.on("end", () => {
        if (settled) return;
        settled = true;
        const body = Buffer.concat(chunks).toString("utf8");
        resolve({
          reachable: res.statusCode >= 200 && res.statusCode < 400,
          statusCode: res.statusCode,
          etag: res.headers.etag || "",
          lastModified: res.headers["last-modified"] || "",
          contentHash: method === "GET" ? hash(body) : "",
          error: ""
        });
      });
    });
    req.setTimeout(8000, () => req.destroy(new Error("timeout")));
    req.on("error", (error) => {
      if (settled) return;
      settled = true;
      resolve({ reachable: false, statusCode: 0, etag: "", lastModified: "", contentHash: "", error: error.message });
    });
    req.end();
  });
}

function withHardTimeout(promise, ms, url, method) {
  return Promise.race([
    promise,
    new Promise((resolve) => {
      setTimeout(() => resolve({ reachable: false, statusCode: 0, etag: "", lastModified: "", contentHash: "", error: `${method} hard-timeout ${ms}ms`, url }), ms);
    })
  ]);
}

async function checkUrl(url) {
  let result = await withHardTimeout(fetchUrl(url, "HEAD"), 10000, url, "HEAD");
  if (!result.reachable || (!result.etag && !result.lastModified)) {
    const getResult = await withHardTimeout(fetchUrl(url, "GET"), 12000, url, "GET");
    result = Object.assign({}, result, getResult, {
      etag: getResult.etag || result.etag,
      lastModified: getResult.lastModified || result.lastModified,
      contentHash: getResult.contentHash || result.contentHash
    });
  }
  return Object.assign({ url, risk: riskForUrl(url) }, result);
}

async function mapLimit(items, limit, worker) {
  const results = new Array(items.length);
  let nextIndex = 0;
  async function run() {
    while (nextIndex < items.length) {
      const index = nextIndex;
      nextIndex += 1;
      results[index] = await worker(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, run));
  return results;
}

function compareWithPrevious(items, previous) {
  const previousByUrl = new Map(((previous && previous.items) || []).map((item) => [item.url, item]));
  return items.map((item) => {
    const old = previousByUrl.get(item.url);
    let changed = false;
    if (old && item.reachable) {
      changed = Boolean(
        (item.etag && old.etag && item.etag !== old.etag) ||
        (item.lastModified && old.lastModified && item.lastModified !== old.lastModified) ||
        (item.contentHash && old.contentHash && item.contentHash !== old.contentHash)
      );
    }
    const merged = Object.assign({}, item, {
      changedSinceLastCheck: old ? changed : false,
      firstSeen: !old,
      recommendedAction: ""
    });
    merged.recommendedAction = recommendedAction(merged);
    return merged;
  });
}

function writeReports(report) {
  ensureDir(artifactsDir);
  fs.writeFileSync(jsonReportPath, JSON.stringify(report, null, 2));
  fs.writeFileSync(snapshotPath, JSON.stringify({ generatedAt: report.generatedAt, items: report.items }, null, 2));

  const lines = [
    "# Official Update Report",
    "",
    `Generated at: ${report.generatedAt}`,
    `Reachable: ${report.summary.reachable}/${report.summary.total}`,
    `Changed: ${report.summary.changed}`,
    `Unknown/unreachable: ${report.summary.unreachable}`,
    "",
    "| URL | Reachable | Status | ETag | Last Modified | Hash | Changed | Risk | Recommended Action |",
    "|---|---|---:|---|---|---|---|---|---|"
  ];
  for (const item of report.items) {
    lines.push(`| ${item.url} | ${item.reachable ? "yes" : "no"} | ${item.statusCode || "-"} | ${item.etag || "-"} | ${item.lastModified || "-"} | ${item.contentHash || "-"} | ${item.changedSinceLastCheck ? "yes" : "no"} | ${item.risk} | ${item.recommendedAction} |`);
  }
  fs.writeFileSync(mdReportPath, lines.join("\n") + "\n");
}

async function main() {
  const sourceText = fs.existsSync(sourcesPath) ? fs.readFileSync(sourcesPath, "utf8") : "";
  const urls = extractUrls(sourceText);
  const previous = readJson(snapshotPath);
  const checked = await mapLimit(urls, Number(process.env.WX_UPDATE_GUARDIAN_CONCURRENCY || 4), checkUrl);
  const items = compareWithPrevious(checked, previous);
  const report = {
    generatedAt: new Date().toISOString(),
    sourceFile: path.relative(root, sourcesPath),
    snapshotFile: path.relative(root, snapshotPath),
    summary: {
      total: items.length,
      reachable: items.filter((item) => item.reachable).length,
      unreachable: items.filter((item) => !item.reachable).length,
      changed: items.filter((item) => item.changedSinceLastCheck).length,
      highRiskChanges: items.filter((item) => item.changedSinceLastCheck && item.risk === "high-risk-change").length
    },
    conservativeMode: items.length > 0 && items.every((item) => !item.reachable),
    items
  };
  writeReports(report);
  console.log(`Official update report written: ${path.relative(root, jsonReportPath)}`);
  console.log(`Reachable: ${report.summary.reachable}/${report.summary.total}. Changed: ${report.summary.changed}.`);
}

main().catch((error) => {
  console.error(`Official update check failed: ${error.message}`);
  process.exit(1);
});
