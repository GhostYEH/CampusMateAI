#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const root = process.cwd();
const artifactsDir = path.join(root, "artifacts");
const defaultStorePath = path.join(root, ".codex", "wechat-miniprogram-experience-ledger.json");
function expandHome(inputPath) {
  if (!inputPath) return inputPath;
  if (inputPath === "~") return process.env.HOME || inputPath;
  if (inputPath.startsWith("~/")) return path.join(process.env.HOME || "~", inputPath.slice(2));
  return inputPath;
}
const storePath = process.env.WX_EXPERIENCE_LEDGER_PATH
  ? path.resolve(root, expandHome(process.env.WX_EXPERIENCE_LEDGER_PATH))
  : defaultStorePath;
const preflightReportPath = path.join(artifactsDir, "wechat-experience-preflight.json");
const auditJsonPath = path.join(artifactsDir, "wechat-experience-audit.json");
const auditMdPath = path.join(artifactsDir, "wechat-experience-audit.md");
const defaultIndexPath = path.join(root, ".codex", "wechat-miniprogram-experience-index.json");

const allowedScopes = new Set([
  "project",
  "global",
  "family",
  "account"
]);

const allowedTaskTypes = new Set([
  "create-new-miniprogram",
  "migrate-existing-project",
  "maintain-existing-miniprogram",
  "integrate-wechat-capability",
  "integrate-cloudbase",
  "deploy-miniprogram",
  "prepare-review",
  "debug",
  "unknown"
]);

const allowedSeverities = new Set([
  "info",
  "warn",
  "blocker",
  "critical"
]);

const allowedStages = new Set([
  "setup",
  "inspect",
  "create",
  "migrate",
  "develop",
  "validate",
  "build",
  "preview",
  "upload",
  "deploy",
  "review",
  "cloudbase",
  "security",
  "docs",
  "ci",
  "unknown"
]);

const allowedAreas = new Set([
  "config",
  "routing",
  "request",
  "storage",
  "auth",
  "login",
  "phone",
  "payment",
  "subscribe-message",
  "location",
  "map",
  "file",
  "media",
  "websocket",
  "cloudbase",
  "cloud-functions",
  "cloud-run",
  "privacy",
  "legal-domain",
  "package-size",
  "performance",
  "miniprogram-ci",
  "devtools",
  "github-actions",
  "migration",
  "security",
  "unknown"
]);

const knownCapabilities = new Set([
  "config",
  "login",
  "phone-number",
  "payment",
  "subscribe-message",
  "location",
  "map",
  "file",
  "media",
  "websocket",
  "cloudbase",
  "cloud-functions",
  "cloud-run",
  "privacy",
  "legal-domain",
  "package-size",
  "performance",
  "preview",
  "upload",
  "review",
  "unknown"
]);

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function now() {
  return new Date().toISOString();
}

function shortHash(value) {
  return crypto.createHash("sha256").update(String(value || "")).digest("hex").slice(0, 12);
}

function slugify(value, fallback) {
  const text = sanitize(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return text || fallback || "unknown";
}

function splitList(value) {
  return sanitize(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function currentProjectProfile() {
  const config = readJson(path.join(root, ".codex", "wechat-miniprogram.config.json")) || {};
  const pkg = readJson(path.join(root, "package.json")) || {};
  const rawName = config.projectName || pkg.name || path.basename(root) || "wechat-miniprogram";
  const appid = process.env.WECHAT_APPID || config.appid || "";
  const projectId = config.projectId || slugify(rawName, "wechat-project");
  const profile = {
    projectId,
    projectName: rawName,
    projectType: config.projectType || "auto",
    sourceFramework: config.projectType || "auto",
    targetFramework: config.targetFramework || "auto",
    packageManager: config.packageManager || "auto",
    miniprogramRoot: config.miniprogramRoot || config.distRoot || config.sourceRoot || "",
    appidHash: appid ? shortHash(appid) : "",
    rootHash: shortHash(root)
  };
  return profile;
}

function emptyStore() {
  return {
    schemaVersion: 2,
    createdAt: now(),
    updatedAt: now(),
    projectProfiles: {},
    nextId: 1,
    records: []
  };
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    return null;
  }
}

function loadStore() {
  const existing = readJson(storePath);
  if (!existing || !Array.isArray(existing.records)) return emptyStore();
  existing.schemaVersion = 2;
  existing.projectProfiles = existing.projectProfiles || {};
  existing.nextId = existing.nextId || nextIdFromRecords(existing.records);
  const profile = currentProjectProfile();
  existing.projectProfiles[profile.projectId] = profile;
  existing.records = existing.records.map((record) => normalizeRecord(record, profile));
  return existing;
}

function saveStore(store) {
  store.updatedAt = now();
  ensureDir(path.dirname(storePath));
  fs.writeFileSync(storePath, JSON.stringify(store, null, 2));
}

function nextIdFromRecords(records) {
  const maxId = records.reduce((max, record) => Math.max(max, Number(record.id) || 0), 0);
  return maxId + 1;
}

function sanitize(value) {
  if (value === undefined || value === null) return "";
  let text = String(value);
  const replacements = [
    [/-----BEGIN[\s\S]{0,80}PRIVATE KEY-----[\s\S]*?-----END[\s\S]{0,80}PRIVATE KEY-----/g, "[REDACTED_PRIVATE_KEY]"],
    [/(WECHAT_PRIVATE_KEY\s*=\s*)[^\s]+/gi, "$1[REDACTED]"],
    [/(AppSecret|appsecret|app_secret|APP_SECRET)\s*[:=]\s*['"]?[^'",\s]+/g, "$1=[REDACTED]"],
    [/(mchKey|apiV3Key|merchantKey|paymentSecret|paySecret)\s*[:=]\s*['"]?[^'",\s]+/gi, "$1=[REDACTED]"],
    [/(token|password|secret|session_key)\s*[:=]\s*['"]?[^'",\s]+/gi, "$1=[REDACTED]"]
  ];
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, replacement);
  }
  return text.length > 4000 ? `${text.slice(0, 4000)}... [truncated]` : text;
}

function normalizeWords(text) {
  return sanitize(text)
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5:/._-]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function inferTaskType(text) {
  const lower = sanitize(text).toLowerCase();
  if (/create|new|初始化|新建/.test(lower)) return "create-new-miniprogram";
  if (/migrate|port|迁移|转换|react|vue|h5/.test(lower)) return "migrate-existing-project";
  if (/cloudbase|tcb|云开发|云函数|云托管/.test(lower)) return "integrate-cloudbase";
  if (/preview|upload|deploy|ci|预览|上传|部署/.test(lower)) return "deploy-miniprogram";
  if (/review|release|audit|审核|发布/.test(lower)) return "prepare-review";
  if (/login|payment|phone|subscribe|location|map|websocket|登录|支付|手机号|订阅|定位|地图/.test(lower)) return "integrate-wechat-capability";
  if (/fix|debug|validate|修复|排查|验证/.test(lower)) return "debug";
  return "unknown";
}

function inferCapability(text) {
  const lower = sanitize(text).toLowerCase();
  const checks = [
    ["config", /project\.config|app\.json|pages\.json|config|配置/],
    ["phone-number", /phone|手机号|获取手机号/],
    ["subscribe-message", /subscribe|订阅/],
    ["legal-domain", /domain|合法域名/],
    ["package-size", /package size|包体积/],
    ["cloud-functions", /cloud function|云函数/],
    ["cloud-run", /cloud run|云托管/],
    ["login", /login|wx\.login|登录/],
    ["payment", /payment|requestpayment|支付/],
    ["location", /location|定位|位置/],
    ["map", /map|地图/],
    ["file", /uploadfile|downloadfile|文件/],
    ["media", /media|image|video|audio|图片|视频|音频/],
    ["websocket", /websocket|socket/],
    ["cloudbase", /cloudbase|tcb|云开发/],
    ["privacy", /privacy|隐私|授权/],
    ["preview", /preview|预览/],
    ["upload", /upload|上传/],
    ["review", /review|审核/],
    ["performance", /performance|性能/]
  ];
  const found = checks.find(([, pattern]) => pattern.test(lower));
  return found ? found[0] : "unknown";
}

function inferArea(text) {
  const capability = inferCapability(text);
  if (capability !== "unknown" && allowedAreas.has(capability)) return capability;
  const lower = sanitize(text).toLowerCase();
  if (/project\.config|app\.json|pages\.json|config|配置/.test(lower)) return "config";
  if (/route|router|routing|路由/.test(lower)) return "routing";
  if (/request|axios|fetch|请求/.test(lower)) return "request";
  if (/storage|localstorage|sessionstorage|存储/.test(lower)) return "storage";
  if (/github|actions|ci/.test(lower)) return "github-actions";
  if (/miniprogram-ci|privatekey|robot|ip whitelist|预览|上传/.test(lower)) return "miniprogram-ci";
  if (/migrate|迁移/.test(lower)) return "migration";
  if (/secret|key|token|安全|密钥/.test(lower)) return "security";
  return "unknown";
}

function inferExperience(text) {
  const lower = sanitize(text).toLowerCase();
  const checks = [
    ["missing-project-config", /missing-project-config|project\.config\.json.*missing|缺.*project\.config/],
    ["missing-app-or-pages-config", /missing-app-or-pages|app\.json|pages\.json/],
    ["missing-appid", /missing appid|appid.*missing|缺.*appid/],
    ["missing-private-key", /private key|privatekeypath|上传密钥|私钥/],
    ["ip-whitelist", /ip whitelist|ip白名单|白名单/],
    ["legal-domain", /legal domain|合法域名/],
    ["frontend-secret-boundary", /appsecret|session_key|mchkey|apiv3key|密钥.*前端/],
    ["dom-api-incompat", /window|document|queryselector|localstorage|sessionstorage|dom/],
    ["request-adapter", /fetch|axios|wx\.request|request adapter|请求封装/],
    ["cloudbase-env", /envid|cloudbase|tcb|云开发环境/],
    ["review-privacy", /privacy|隐私|授权|审核/],
    ["package-size", /包体积|package size/],
    ["ci-deploy", /github actions|ci|deploy|部署/]
  ];
  const found = checks.find(([, pattern]) => pattern.test(lower));
  if (found) return found[0];
  return slugify(lower.split(/\s+/).slice(0, 5).join("-"), "uncategorized");
}

function normalizeRecord(record, profile) {
  const text = [
    record.task,
    record.command,
    record.summary,
    record.error,
    record.rule,
    (record.labels || []).join(" ")
  ].join(" ");
  record.projectScope = allowedScopes.has(record.projectScope) ? record.projectScope : "project";
  record.projectId = record.projectId || profile.projectId;
  record.projectName = record.projectName || profile.projectName;
  record.taskType = allowedTaskTypes.has(record.taskType) ? record.taskType : inferTaskType(text);
  record.stage = allowedStages.has(record.stage) ? record.stage : "unknown";
  record.area = allowedAreas.has(record.area) ? record.area : inferArea(text);
  record.capability = knownCapabilities.has(record.capability) && record.capability !== "unknown" ? record.capability : inferCapability(text);
  record.framework = record.framework || profile.targetFramework || "unknown";
  record.experience = record.experience || inferExperience(text);
  record.severity = allowedSeverities.has(record.severity) ? record.severity : "warn";
  record.labels = Array.from(new Set([...(record.labels || []), `experience:${record.experience}`]));
  return record;
}

function fingerprint(input) {
  const key = [
    input.kind || "experience",
    input.projectScope === "global" ? "global" : input.projectId || "unknown-project",
    input.taskType || "unknown",
    input.stage || "unknown",
    input.area || "unknown",
    input.capability || "unknown",
    input.framework || "unknown",
    input.experience || "uncategorized",
    sanitize(input.summary || ""),
    sanitize(input.error || "").slice(0, 500)
  ].join("|").toLowerCase();
  return crypto.createHash("sha256").update(key).digest("hex").slice(0, 16);
}

function parseArgs(argv) {
  const result = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = argv[i + 1];
      if (!next || next.startsWith("--")) {
        result[key] = "true";
      } else {
        result[key] = next;
        i += 1;
      }
    } else {
      result._.push(arg);
    }
  }
  return result;
}

function compactRecord(record) {
  return {
    id: record.id,
    status: record.status,
    kind: record.kind,
    projectScope: record.projectScope,
    projectId: record.projectId,
    taskType: record.taskType,
    stage: record.stage,
    area: record.area,
    capability: record.capability,
    framework: record.framework,
    experience: record.experience,
    severity: record.severity,
    summary: record.summary,
    rule: record.rule || "",
    occurrences: record.occurrences || 1,
    lastSeenAt: record.lastSeenAt || record.createdAt
  };
}

function scoreRecord(record, queryWords) {
  const haystack = normalizeWords([
    record.kind,
    record.projectScope,
    record.projectId,
    record.projectName,
    record.taskType,
    record.stage,
    record.area,
    record.capability,
    record.framework,
    record.experience,
    record.severity,
    record.task,
    record.summary,
    record.error,
    record.rootCause,
    record.fix,
    record.rule,
    (record.labels || []).join(" ")
  ].join(" "));
  const set = new Set(haystack);
  let score = 0;
  for (const word of queryWords) {
    if (set.has(word)) score += 3;
    if ((record.summary || "").toLowerCase().includes(word)) score += 2;
    if ((record.rule || "").toLowerCase().includes(word)) score += 2;
    if ((record.experience || "").toLowerCase() === word) score += 4;
  }
  if (record.status === "resolved") score += 2;
  if (record.status === "open") score += 1;
  score += Math.min(Number(record.occurrences) || 1, 5) * 0.2;
  return score;
}

function projectAllowed(record, profile, options) {
  if (options && options.allProjects) return true;
  if (record.projectScope === "global" || record.projectScope === "family" || record.projectScope === "account") return true;
  return record.projectId === profile.projectId;
}

function scopeBoost(record, profile) {
  if (record.projectScope === "project" && record.projectId === profile.projectId) return 5;
  if (record.projectScope === "global") return 3;
  if (record.projectScope === "family") return 2;
  if (record.projectScope === "account") return 1;
  return 0;
}

function searchRecords(store, query, limit, options = {}) {
  const words = normalizeWords(query);
  const profile = options.profile || currentProjectProfile();
  const candidates = store.records.filter((record) => projectAllowed(record, profile, options));
  if (!words.length) {
    return candidates.slice().sort((a, b) => String(b.lastSeenAt || b.createdAt).localeCompare(String(a.lastSeenAt || a.createdAt))).slice(0, limit);
  }
  return candidates
    .map((record) => ({ record, score: scoreRecord(record, words) + scopeBoost(record, profile) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((item) => item.record);
}

function commandPreflight(args) {
  const query = args._.join(" ").trim() || args.query || "wechat miniprogram";
  const store = loadStore();
  const profile = currentProjectProfile();
  const allProjects = args["all-projects"] === "true";
  const matches = searchRecords(store, query, Number(args.limit || 8), { profile, allProjects });
  const resolved = matches.filter((record) => record.status === "resolved");
  const open = matches.filter((record) => record.status !== "resolved");
  ensureDir(artifactsDir);
  const report = {
    generatedAt: now(),
    query,
    currentProject: profile,
    searchMode: allProjects ? "all-projects" : "current-project-plus-shared",
    storePath,
    resolvedLessons: resolved.map(compactRecord),
    openRecords: open.map(compactRecord)
  };
  fs.writeFileSync(preflightReportPath, JSON.stringify(report, null, 2));

  console.log(`WeChat experience preflight: ${query}`);
  console.log(`Project: ${profile.projectId} (${profile.projectName})`);
  if (!matches.length) {
    console.log("No matching WeChat-specific lessons yet.");
  } else {
    if (resolved.length) {
      console.log("Relevant resolved lessons:");
      for (const record of resolved) {
        console.log(`- #${record.id} ${record.projectScope}:${record.projectId} ${record.taskType}/${record.stage}/${record.area}/${record.experience}: ${record.rule || record.summary}`);
      }
    }
    if (open.length) {
      console.log("Relevant open records:");
      for (const record of open) {
        console.log(`- #${record.id} ${record.projectScope}:${record.projectId} ${record.taskType}/${record.stage}/${record.area}/${record.experience}: ${record.summary}`);
      }
    }
  }
  console.log(`Preflight report written: ${path.relative(root, preflightReportPath)}`);
}

function autoAudit(reason) {
  if (process.env.WX_EXPERIENCE_AUTO_AUDIT === "0") return;
  if (process.env.WX_EXPERIENCE_DISABLE === "1") return;
  const result = require("child_process").spawnSync(process.execPath, [__filename, "audit"], {
    cwd: root,
    stdio: "ignore",
    env: Object.assign({}, process.env, {
      WX_EXPERIENCE_AUTO_AUDIT: "0",
      WX_EXPERIENCE_AUDIT_REASON: reason || "auto"
    })
  });
  if (result.status !== 0 && process.env.WX_EXPERIENCE_AUDIT_VERBOSE === "1") {
    console.error(`Automatic WeChat experience audit failed after ${reason || "mutation"}.`);
  }
}

function commandRecord(args) {
  const store = loadStore();
  const profile = currentProjectProfile();
  const rawText = [
    args.task,
    args.command,
    args.summary,
    args.error,
    args.labels
  ].join(" ");
  const projectScope = allowedScopes.has(args.scope || args["project-scope"]) ? (args.scope || args["project-scope"]) : "project";
  const projectId = projectScope === "global"
    ? "global"
    : sanitize(args["project-id"] || args.projectId || profile.projectId);
  const projectName = projectScope === "global"
    ? "Global WeChat Mini Program Lessons"
    : sanitize(args["project-name"] || args.projectName || profile.projectName);
  const taskType = allowedTaskTypes.has(args["task-type"] || args.taskType) ? (args["task-type"] || args.taskType) : inferTaskType(rawText);
  const area = allowedAreas.has(args.area) ? args.area : inferArea(rawText);
  const capability = knownCapabilities.has(args.capability) ? args.capability : inferCapability(rawText);
  const experience = args.experience ? slugify(args.experience, "uncategorized") : inferExperience(rawText);
  const input = {
    kind: args.kind || "error",
    projectScope,
    projectId,
    projectName,
    taskType,
    stage: allowedStages.has(args.stage) ? args.stage : "unknown",
    area,
    capability,
    framework: args.framework || profile.targetFramework || "unknown",
    sourceFramework: args["source-framework"] || profile.sourceFramework || "unknown",
    targetFramework: args["target-framework"] || profile.targetFramework || "unknown",
    experience,
    severity: allowedSeverities.has(args.severity) ? args.severity : "warn",
    task: sanitize(args.task || ""),
    command: sanitize(args.command || ""),
    summary: sanitize(args.summary || args._.join(" ") || "Unspecified WeChat Mini Program experience"),
    error: sanitize(args.error || ""),
    docs: splitList(args.docs),
    labels: Array.from(new Set(splitList(args.labels).concat([
      `project:${projectId}`,
      `task:${taskType}`,
      `stage:${allowedStages.has(args.stage) ? args.stage : "unknown"}`,
      `area:${area}`,
      `capability:${capability}`,
      `framework:${args.framework || profile.targetFramework || "unknown"}`,
      `experience:${experience}`
    ]))),
    source: sanitize(args.source || "")
  };
  const fp = fingerprint(input);
  const inputDedupeKey = dedupeKey(input);
  const existing = store.records.find((record) => record.fingerprint === fp || dedupeKey(record) === inputDedupeKey);
  if (existing) {
    existing.occurrences = (existing.occurrences || 1) + 1;
    existing.lastSeenAt = now();
    existing.error = input.error || existing.error;
    existing.command = input.command || existing.command;
    existing.source = input.source || existing.source;
    existing.labels = Array.from(new Set([...(existing.labels || []), ...input.labels]));
    existing.relatedExperiences = Array.from(new Set([existing.experience, input.experience, ...((existing.relatedExperiences || []))].filter(Boolean)));
    if ((!existing.experience || existing.experience === "uncategorized") && input.experience) existing.experience = input.experience;
    if (allowedSeverities.has(input.severity) && existing.severity !== "critical") existing.severity = input.severity;
    saveStore(store);
    autoAudit("record-update");
    console.log(`Updated existing WeChat experience #${existing.id}; occurrences=${existing.occurrences}`);
    return;
  }

  const record = Object.assign({}, input, {
    id: store.nextId,
    fingerprint: fp,
    status: "open",
    occurrences: 1,
    createdAt: now(),
    lastSeenAt: now(),
    rootCause: "",
    fix: "",
    rule: "",
    verifiedBy: ""
  });
  store.nextId += 1;
  store.records.push(record);
  saveStore(store);
  autoAudit("record-create");
  console.log(`Recorded WeChat experience #${record.id}: ${record.summary}`);
}

function commandResolve(args) {
  const id = Number(args._[0]);
  if (!id) throw new Error("resolve requires a record id.");
  const store = loadStore();
  const record = store.records.find((item) => Number(item.id) === id);
  if (!record) throw new Error(`Record not found: ${id}`);

  record.status = "resolved";
  record.resolvedAt = now();
  record.rootCause = sanitize(args["root-cause"] || args.rootCause || record.rootCause || "");
  record.fix = sanitize(args.fix || record.fix || "");
  record.rule = sanitize(args.rule || record.rule || "");
  record.verifiedBy = sanitize(args["verified-by"] || args.verifiedBy || record.verifiedBy || "");
  if (allowedScopes.has(args.scope || args["project-scope"])) {
    record.projectScope = args.scope || args["project-scope"];
    if (record.projectScope === "global") {
      record.projectId = "global";
      record.projectName = "Global WeChat Mini Program Lessons";
    }
  }
  if (allowedTaskTypes.has(args["task-type"] || args.taskType)) record.taskType = args["task-type"] || args.taskType;
  if (allowedAreas.has(args.area)) record.area = args.area;
  if (knownCapabilities.has(args.capability)) record.capability = args.capability;
  if (allowedSeverities.has(args.severity)) record.severity = args.severity;
  if (args.experience) record.experience = slugify(args.experience, record.experience || "uncategorized");
  record.docs = Array.from(new Set([...(record.docs || []), ...splitList(args.docs)]));
  record.labels = Array.from(new Set([...(record.labels || []), `experience:${record.experience}`, `task:${record.taskType}`, `area:${record.area}`, `capability:${record.capability}`]));
  record.lastSeenAt = now();

  if (!record.rootCause || !record.fix || !record.rule) {
    throw new Error("resolve requires --root-cause, --fix, and --rule so the lesson is reusable.");
  }

  saveStore(store);
  autoAudit("resolve");
  console.log(`Resolved WeChat experience #${record.id}`);
  console.log(`Rule: ${record.rule}`);
}

function commandSearch(args) {
  const query = args._.join(" ").trim() || args.query || "";
  const store = loadStore();
  const matches = searchRecords(store, query, Number(args.limit || 20), { allProjects: args["all-projects"] === "true" });
  if (!matches.length) {
    console.log("No matching WeChat experiences.");
    return;
  }
  for (const record of matches) {
    console.log(`#${record.id} [${record.status}] ${record.projectScope}:${record.projectId} ${record.taskType}/${record.stage}/${record.area}/${record.capability}/${record.framework}`);
    console.log(`  experience: ${record.experience} severity=${record.severity} occurrences=${record.occurrences || 1}`);
    console.log(`  summary: ${record.summary}`);
    if (record.rule) console.log(`  rule: ${record.rule}`);
  }
}

function commandList(args) {
  const store = loadStore();
  const profile = currentProjectProfile();
  const status = args.status || "";
  const project = args.project || "";
  const records = store.records
    .filter((record) => !status || record.status === status)
    .filter((record) => {
      if (!project) return true;
      if (project === "current") return record.projectScope !== "project" || record.projectId === profile.projectId;
      if (project === "global") return record.projectScope === "global";
      return record.projectId === project;
    })
    .sort((a, b) => Number(b.id) - Number(a.id))
    .slice(0, Number(args.limit || 50));
  if (!records.length) {
    console.log("No WeChat experience records.");
    return;
  }
  for (const record of records) {
    console.log(`#${record.id} [${record.status}] ${record.projectScope}:${record.projectId} ${record.taskType}/${record.stage}/${record.area}/${record.experience}: ${record.summary}`);
  }
}

function dedupeKey(record) {
  return [
    record.projectScope,
    record.projectId,
    record.taskType,
    record.stage,
    record.area,
    sanitize(record.summary).toLowerCase(),
    sanitize(record.error).toLowerCase().slice(0, 500)
  ].join("|");
}

function mergeRecord(primary, duplicate) {
  primary.occurrences = (Number(primary.occurrences) || 1) + (Number(duplicate.occurrences) || 1);
  primary.lastSeenAt = [primary.lastSeenAt, duplicate.lastSeenAt, primary.createdAt, duplicate.createdAt].filter(Boolean).sort().pop();
  primary.docs = Array.from(new Set([...(primary.docs || []), ...(duplicate.docs || [])]));
  primary.labels = Array.from(new Set([...(primary.labels || []), ...(duplicate.labels || [])]));
  primary.relatedExperiences = Array.from(new Set([primary.experience, duplicate.experience, ...((primary.relatedExperiences || [])), ...((duplicate.relatedExperiences || []))].filter(Boolean)));
  if (!primary.rootCause && duplicate.rootCause) primary.rootCause = duplicate.rootCause;
  if (!primary.fix && duplicate.fix) primary.fix = duplicate.fix;
  if (!primary.rule && duplicate.rule) primary.rule = duplicate.rule;
  if (!primary.verifiedBy && duplicate.verifiedBy) primary.verifiedBy = duplicate.verifiedBy;
  if (primary.status !== "resolved" && duplicate.status === "resolved") {
    primary.status = "resolved";
    primary.resolvedAt = duplicate.resolvedAt || now();
  }
  if ((!primary.experience || primary.experience === "uncategorized") && duplicate.experience) primary.experience = duplicate.experience;
  return primary;
}

function commandDedupe() {
  const store = loadStore();
  const groups = new Map();
  const kept = [];
  let removed = 0;

  for (const record of store.records) {
    const key = dedupeKey(record);
    if (!groups.has(key)) {
      groups.set(key, record);
      kept.push(record);
      continue;
    }
    const existing = groups.get(key);
    const primary = existing.status === "resolved" ? existing : record.status === "resolved" ? record : existing;
    const duplicate = primary === existing ? record : existing;
    mergeRecord(primary, duplicate);
    if (primary !== existing) {
      const index = kept.indexOf(existing);
      if (index >= 0) kept[index] = primary;
      groups.set(key, primary);
    }
    removed += 1;
  }

  store.records = kept.sort((a, b) => Number(a.id) - Number(b.id));
  saveStore(store);
  autoAudit("dedupe");
  console.log(`Deduped WeChat experience ledger. Removed ${removed} duplicate record(s).`);
}

function daysSince(dateValue) {
  const time = Date.parse(dateValue || "");
  if (!Number.isFinite(time)) return null;
  return Math.floor((Date.now() - time) / (24 * 60 * 60 * 1000));
}

function missingFields(record) {
  const required = [
    "projectScope",
    "projectId",
    "projectName",
    "taskType",
    "stage",
    "area",
    "capability",
    "framework",
    "experience",
    "severity",
    "summary"
  ];
  const missing = required.filter((field) => !record[field] || record[field] === "unknown" || record[field] === "uncategorized");
  if (record.status === "resolved") {
    for (const field of ["rootCause", "fix", "rule"]) {
      if (!record[field]) missing.push(field);
    }
  }
  return missing;
}

function buildExperienceIndex(records) {
  const index = {
    generatedAt: now(),
    totals: {
      records: records.length,
      projects: 0,
      experiences: 0,
      open: records.filter((record) => record.status !== "resolved").length,
      resolved: records.filter((record) => record.status === "resolved").length
    },
    byProject: {},
    byExperience: {},
    byTaskType: {},
    byArea: {},
    byCapability: {},
    byFramework: {}
  };
  function inc(bucket, key) {
    const normalized = key || "unknown";
    bucket[normalized] = (bucket[normalized] || 0) + 1;
  }
  for (const record of records) {
    inc(index.byProject, `${record.projectScope}:${record.projectId}`);
    inc(index.byExperience, record.experience);
    inc(index.byTaskType, record.taskType);
    inc(index.byArea, record.area);
    inc(index.byCapability, record.capability);
    inc(index.byFramework, record.framework);
  }
  index.totals.projects = Object.keys(index.byProject).length;
  index.totals.experiences = Object.keys(index.byExperience).length;
  return index;
}

function auditDuplicateGroups(records) {
  const groups = new Map();
  for (const record of records) {
    const key = dedupeKey(record);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(record);
  }
  return Array.from(groups.values())
    .filter((group) => group.length > 1)
    .map((group) => ({
      ids: group.map((record) => record.id),
      projectId: group[0].projectId,
      taskType: group[0].taskType,
      stage: group[0].stage,
      area: group[0].area,
      summary: group[0].summary
    }));
}

function auditPromotionCandidates(records) {
  const byExperience = new Map();
  for (const record of records.filter((item) => item.status === "resolved")) {
    if (!byExperience.has(record.experience)) byExperience.set(record.experience, []);
    byExperience.get(record.experience).push(record);
  }
  const candidates = [];
  for (const [experience, group] of byExperience.entries()) {
    const projectIds = Array.from(new Set(group.map((record) => record.projectId)));
    const occurrences = group.reduce((sum, record) => sum + (Number(record.occurrences) || 1), 0);
    const hasGlobal = group.some((record) => record.projectScope === "global");
    if (!hasGlobal && (projectIds.length >= 2 || occurrences >= 3)) {
      candidates.push({
        experience,
        recordIds: group.map((record) => record.id),
        projectIds,
        occurrences,
        suggestedScope: projectIds.length >= 2 ? "global" : "family",
        reason: projectIds.length >= 2 ? "Resolved in multiple projects." : "Repeated multiple times."
      });
    }
  }
  return candidates;
}

function auditTemplateCandidates(records) {
  const templatableAreas = new Set(["login", "payment", "phone", "privacy", "cloudbase", "cloud-functions", "cloud-run", "request", "storage", "miniprogram-ci", "legal-domain", "security", "migration"]);
  return records
    .filter((record) => record.status === "resolved")
    .filter((record) => (Number(record.occurrences) || 1) >= 2 || templatableAreas.has(record.area) || templatableAreas.has(record.capability))
    .map((record) => ({
      id: record.id,
      projectScope: record.projectScope,
      taskType: record.taskType,
      area: record.area,
      capability: record.capability,
      framework: record.framework,
      experience: record.experience,
      suggestedArtifact: `template-or-checklist:${record.taskType}/${record.area}/${record.experience}`,
      rule: record.rule || record.summary
    }));
}

function auditRecords(records) {
  const qualityIssues = [];
  const staleOpen = [];
  const broadLabels = [];
  for (const record of records) {
    const missing = missingFields(record);
    if (missing.length) {
      qualityIssues.push({
        id: record.id,
        status: record.status,
        projectId: record.projectId,
        missing
      });
    }
    const age = daysSince(record.lastSeenAt || record.createdAt);
    if (record.status !== "resolved" && age !== null && age >= 14) {
      staleOpen.push({
        id: record.id,
        projectId: record.projectId,
        ageDays: age,
        summary: record.summary
      });
    }
    if (record.experience === "unknown" || record.experience === "uncategorized" || record.experience.length < 4 || record.area === "unknown") {
      broadLabels.push({
        id: record.id,
        experience: record.experience,
        area: record.area,
        suggestion: "Split into a specific atomic experience label."
      });
    }
  }
  return {
    qualityIssues,
    staleOpen,
    broadLabels,
    duplicateGroups: auditDuplicateGroups(records),
    promotionCandidates: auditPromotionCandidates(records),
    templateCandidates: auditTemplateCandidates(records)
  };
}

function writeAuditReports(report) {
  ensureDir(artifactsDir);
  ensureDir(path.dirname(defaultIndexPath));
  fs.writeFileSync(auditJsonPath, JSON.stringify(report, null, 2));
  fs.writeFileSync(defaultIndexPath, JSON.stringify(report.index, null, 2));
  const lines = [
    "# WeChat Experience Audit",
    "",
    `Generated at: ${report.generatedAt}`,
    `Health status: ${report.healthStatus}`,
    "",
    "## Totals",
    "",
    `- Records: ${report.index.totals.records}`,
    `- Projects/scopes: ${report.index.totals.projects}`,
    `- Atomic experiences: ${report.index.totals.experiences}`,
    `- Open: ${report.index.totals.open}`,
    `- Resolved: ${report.index.totals.resolved}`,
    "",
    "## Quality Issues",
    ""
  ];
  if (!report.qualityIssues.length) lines.push("- None.");
  for (const item of report.qualityIssues) lines.push(`- #${item.id}: missing ${item.missing.join(", ")}`);
  lines.push("", "## Duplicate Groups", "");
  if (!report.duplicateGroups.length) lines.push("- None.");
  for (const group of report.duplicateGroups) lines.push(`- ${group.ids.join(", ")}: ${group.summary}`);
  lines.push("", "## Promotion Candidates", "");
  if (!report.promotionCandidates.length) lines.push("- None.");
  for (const item of report.promotionCandidates) lines.push(`- ${item.experience}: ${item.suggestedScope}; records ${item.recordIds.join(", ")}; ${item.reason}`);
  lines.push("", "## Template Candidates", "");
  if (!report.templateCandidates.length) lines.push("- None.");
  for (const item of report.templateCandidates.slice(0, 50)) lines.push(`- #${item.id}: ${item.suggestedArtifact}`);
  lines.push("", "## Stale Open Records", "");
  if (!report.staleOpen.length) lines.push("- None.");
  for (const item of report.staleOpen) lines.push(`- #${item.id}: ${item.ageDays} days open; ${item.summary}`);
  lines.push("", "## Scale Notes", "");
  for (const note of report.scaleNotes) lines.push(`- ${note}`);
  fs.writeFileSync(auditMdPath, lines.join("\n") + "\n");
}

function commandAudit(args) {
  const store = loadStore();
  saveStore(store);
  const profile = currentProjectProfile();
  const allProjects = args["all-projects"] === "true";
  const records = store.records.filter((record) => allProjects || projectAllowed(record, profile, {}));
  const index = buildExperienceIndex(records);
  const audit = auditRecords(records);
  const scaleNotes = [];
  if (store.records.length > 500) scaleNotes.push("Record count exceeds 500; keep using generated index and consider moving shared ledger to SQLite.");
  if (store.records.length > 2000) scaleNotes.push("Record count exceeds 2000; split project-local and global ledgers or use SQLite before further growth.");
  if (index.totals.projects > 10) scaleNotes.push("More than 10 project scopes found; prefer explicit projectId and review promotion candidates monthly.");
  if (!scaleNotes.length) scaleNotes.push("Current JSON ledger scale is acceptable.");
  const blockerCount = audit.qualityIssues.filter((item) => item.missing.includes("rootCause") || item.missing.includes("fix") || item.missing.includes("rule")).length;
  const healthStatus = blockerCount
    ? "needs-quality-work"
    : audit.qualityIssues.length || audit.duplicateGroups.length || audit.staleOpen.length || audit.promotionCandidates.length
      ? "needs-attention"
      : "healthy";
  const report = Object.assign({
    generatedAt: now(),
    currentProject: profile,
    searchMode: allProjects ? "all-projects" : "current-project-plus-shared",
    storePath,
    indexPath: defaultIndexPath,
    healthStatus,
    index,
    scaleNotes
  }, audit);
  writeAuditReports(report);
  console.log(`WeChat experience audit written: ${path.relative(root, auditJsonPath)}`);
  console.log(`Audit status: ${healthStatus}`);
  console.log(`Quality issues: ${audit.qualityIssues.length}. Duplicates: ${audit.duplicateGroups.length}. Promotion candidates: ${audit.promotionCandidates.length}. Template candidates: ${audit.templateCandidates.length}.`);
}

function commandDoctor() {
  const store = loadStore();
  const profile = currentProjectProfile();
  ensureDir(path.dirname(storePath));
  saveStore(store);
  console.log(`WeChat experience ledger is ready: ${path.relative(root, storePath)}`);
  console.log(`Current project: ${profile.projectId} (${profile.projectName})`);
  console.log(`Records: ${store.records.length}. Next id: ${store.nextId}.`);
}

function commandProfile() {
  const profile = currentProjectProfile();
  console.log(JSON.stringify(profile, null, 2));
}

function commandExport(args) {
  const store = loadStore();
  const outPath = args.out ? path.resolve(root, args.out) : path.join(artifactsDir, "wechat-experience-export.md");
  ensureDir(path.dirname(outPath));
  const resolved = store.records.filter((record) => record.status === "resolved");
  const lines = [
    "# WeChat Mini Program Experience Export",
    "",
    `Generated at: ${now()}`,
    "",
    "## Resolved Lessons",
    ""
  ];
  for (const record of resolved) {
    lines.push(`### #${record.id} ${record.projectScope}:${record.projectId} ${record.taskType}/${record.stage}/${record.area}/${record.experience}`);
    lines.push("");
    lines.push(`- Capability: ${record.capability}`);
    lines.push(`- Framework: ${record.framework}`);
    lines.push(`- Severity: ${record.severity}`);
    lines.push(`- Summary: ${record.summary}`);
    lines.push(`- Rule: ${record.rule}`);
    lines.push(`- Root cause: ${record.rootCause}`);
    lines.push(`- Fix: ${record.fix}`);
    if (record.verifiedBy) lines.push(`- Verified by: ${record.verifiedBy}`);
    if (record.docs && record.docs.length) lines.push(`- Docs: ${record.docs.join(", ")}`);
    lines.push("");
  }
  fs.writeFileSync(outPath, lines.join("\n"));
  console.log(`Export written: ${path.relative(root, outPath)}`);
}

function printHelp() {
  console.log(`WeChat Mini Program Experience Ledger

Usage:
  node scripts/wechat-experience-ledger.js preflight "task query" [--all-projects]
  node scripts/wechat-experience-ledger.js record --task-type deploy-miniprogram --stage upload --area miniprogram-ci --capability upload --experience missing-private-key --summary "..." --error "..."
  node scripts/wechat-experience-ledger.js resolve <id> --root-cause "..." --fix "..." --rule "..." [--scope global]
  node scripts/wechat-experience-ledger.js search "keyword" [--all-projects]
  node scripts/wechat-experience-ledger.js list [--status open|resolved] [--project current|global|<project-id>]
  node scripts/wechat-experience-ledger.js audit [--all-projects]
  node scripts/wechat-experience-ledger.js dedupe
  node scripts/wechat-experience-ledger.js profile
  node scripts/wechat-experience-ledger.js doctor
  node scripts/wechat-experience-ledger.js export [--out artifacts/wechat-experience-export.md]

Core taxonomy:
  projectScope: project | global | family | account
  taskType: create-new-miniprogram | migrate-existing-project | maintain-existing-miniprogram | integrate-wechat-capability | integrate-cloudbase | deploy-miniprogram | prepare-review | debug
  stage/area/capability/framework/experience/severity labels keep lessons small and searchable.

Storage:
  ${storePath}

Safety:
  Secrets are redacted, but do not paste private keys, tokens, passwords, or private documents.
`);
}

function main() {
  const argv = process.argv.slice(2);
  const command = argv[0] || "help";
  const args = parseArgs(argv.slice(1));

  if (command === "preflight" || command === "learn") return commandPreflight(args);
  if (command === "record") return commandRecord(args);
  if (command === "resolve") return commandResolve(args);
  if (command === "search") return commandSearch(args);
  if (command === "list") return commandList(args);
  if (command === "audit") return commandAudit(args);
  if (command === "dedupe") return commandDedupe(args);
  if (command === "profile") return commandProfile(args);
  if (command === "doctor") return commandDoctor(args);
  if (command === "export") return commandExport(args);
  if (command === "help" || command === "--help" || command === "-h") return printHelp();
  throw new Error(`Unknown command: ${command}`);
}

try {
  main();
} catch (error) {
  console.error(`WeChat experience ledger failed: ${error.message}`);
  process.exit(1);
}
