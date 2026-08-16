#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const readline = require("readline");

const root = process.cwd();
const codexDir = path.join(root, ".codex");
const configPath = path.join(codexDir, "wechat-miniprogram.config.json");

const defaultConfig = {
  appid: "",
  projectId: "",
  projectName: "",
  projectType: "auto",
  targetFramework: "auto",
  sourceRoot: "",
  miniprogramRoot: "",
  distRoot: "",
  packageManager: "auto",
  deployMode: "preview",
  robot: 1,
  versionStrategy: "package-json",
  descStrategy: "git-commit",
  backendType: "none",
  useCloudBase: false,
  cloudBaseEnvId: "",
  features: {
    login: false,
    phoneNumber: false,
    payment: false,
    subscribeMessage: false,
    location: false,
    map: false,
    file: false,
    media: false,
    websocket: false
  },
  privacy: {
    collectsUserData: false,
    generateComplianceChecklist: true
  },
  automation: {
    allowModifyPackageJson: true,
    allowModifyAgentsMd: true,
    allowModifyGitignore: true,
    allowGenerateGithubActions: true,
    allowAutoMigrateDirectories: false,
    allowDeleteGeneratedFiles: false,
    allowSubmitReview: false
  },
  credentialHints: {
    hasDeveloperPermission: false,
    hasUploadPrivateKey: false,
    privateKeyStorageMode: "local-file",
    privateKeyPath: "",
    ciSecretName: "WECHAT_PRIVATE_KEY",
    uploadIpWhitelistEnabled: false
  },
  cloudBase: {
    hasCloudFunctionsDir: false,
    hasCloudRunService: false
  }
};

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function deepMerge(base, overlay) {
  const result = clone(base);
  for (const [key, value] of Object.entries(overlay || {})) {
    if (value && typeof value === "object" && !Array.isArray(value) && result[key] && typeof result[key] === "object" && !Array.isArray(result[key])) {
      result[key] = deepMerge(result[key], value);
    } else {
      result[key] = value;
    }
  }
  return result;
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    return null;
  }
}

function writeConfig(config) {
  fs.mkdirSync(codexDir, { recursive: true });
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}

function parseBoolean(value, fallback) {
  if (value === "") return fallback;
  if (/^(y|yes|true|1)$/i.test(value)) return true;
  if (/^(n|no|false|0)$/i.test(value)) return false;
  return fallback;
}

function parseChoice(value, fallback, allowed) {
  if (!value) return fallback;
  return allowed.includes(value) ? value : fallback;
}

function safePromptText(value) {
  return value === undefined || value === null ? "" : String(value);
}

async function askAll(existing) {
  const config = deepMerge(defaultConfig, existing);
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const ask = (question, current) => new Promise((resolve) => {
    const suffix = current !== undefined && current !== "" ? ` [${safePromptText(current)}]` : "";
    rl.question(`${question}${suffix}: `, (answer) => resolve(answer.trim()));
  });

  try {
    config.appid = await ask("WeChat Mini Program AppID", config.appid) || config.appid;
    config.projectId = await ask("Stable projectId for WeChat experience ledger", config.projectId) || config.projectId;
    config.projectName = await ask("Project name", config.projectName) || config.projectName;
    config.projectType = parseChoice(await ask("Project type (native/Taro/uni-app/React/Vue/H5/unknown)", config.projectType), config.projectType, ["native", "Taro", "uni-app", "React", "Vue", "H5", "unknown", "auto"]);
    config.targetFramework = parseChoice(await ask("Target route (native/Taro/uni-app/keep-existing/auto)", config.targetFramework), config.targetFramework, ["native", "Taro", "uni-app", "keep-existing", "auto"]);
    config.sourceRoot = await ask("Mini Program source directory", config.sourceRoot) || config.sourceRoot;
    config.miniprogramRoot = await ask("Mini Program root directory", config.miniprogramRoot) || config.miniprogramRoot;
    config.distRoot = await ask("Build output directory", config.distRoot) || config.distRoot;
    config.packageManager = parseChoice(await ask("Package manager (pnpm/npm/yarn/bun/auto)", config.packageManager), config.packageManager, ["pnpm", "npm", "yarn", "bun", "auto"]);

    config.credentialHints.hasDeveloperPermission = parseBoolean(await ask("Has WeChat Mini Program developer permission? (yes/no)", config.credentialHints.hasDeveloperPermission ? "yes" : "no"), config.credentialHints.hasDeveloperPermission);
    config.credentialHints.hasUploadPrivateKey = parseBoolean(await ask("Has upload private key? (yes/no)", config.credentialHints.hasUploadPrivateKey ? "yes" : "no"), config.credentialHints.hasUploadPrivateKey);
    config.credentialHints.privateKeyStorageMode = parseChoice(await ask("Private key storage (local-file/CI-secret/env-content)", config.credentialHints.privateKeyStorageMode), config.credentialHints.privateKeyStorageMode, ["local-file", "CI-secret", "env-content"]);
    config.credentialHints.privateKeyPath = await ask("privateKeyPath if using local-file", config.credentialHints.privateKeyPath) || config.credentialHints.privateKeyPath;
    config.credentialHints.ciSecretName = await ask("CI secret name if using CI-secret", config.credentialHints.ciSecretName) || config.credentialHints.ciSecretName;
    config.credentialHints.uploadIpWhitelistEnabled = parseBoolean(await ask("Upload IP whitelist enabled? (yes/no)", config.credentialHints.uploadIpWhitelistEnabled ? "yes" : "no"), config.credentialHints.uploadIpWhitelistEnabled);
    config.robot = Number(await ask("Upload robot number", config.robot) || config.robot);
    config.deployMode = parseChoice(await ask("Deploy mode (preview/upload/both)", config.deployMode), config.deployMode, ["preview", "upload", "both"]);
    config.versionStrategy = parseChoice(await ask("Version strategy (package-json/git-tag/datetime/manual)", config.versionStrategy), config.versionStrategy, ["package-json", "git-tag", "datetime", "manual"]);
    config.descStrategy = parseChoice(await ask("Upload desc strategy (git-commit/manual/default)", config.descStrategy), config.descStrategy, ["git-commit", "manual", "default"]);

    config.backendType = parseChoice(await ask("Backend type (existing-http-api/CloudBase-functions/CloudBase-run/custom-backend/none)", config.backendType), config.backendType, ["existing-http-api", "CloudBase-functions", "CloudBase-run", "custom-backend", "none"]);
    config.useCloudBase = parseBoolean(await ask("Use CloudBase? (yes/no)", config.useCloudBase ? "yes" : "no"), config.useCloudBase);
    config.cloudBaseEnvId = await ask("CloudBase envId", config.cloudBaseEnvId) || config.cloudBaseEnvId;
    config.cloudBase.hasCloudFunctionsDir = parseBoolean(await ask("Existing cloud functions directory? (yes/no)", config.cloudBase.hasCloudFunctionsDir ? "yes" : "no"), config.cloudBase.hasCloudFunctionsDir);
    config.cloudBase.hasCloudRunService = parseBoolean(await ask("Existing CloudBase Run service? (yes/no)", config.cloudBase.hasCloudRunService ? "yes" : "no"), config.cloudBase.hasCloudRunService);

    for (const key of Object.keys(config.features)) {
      config.features[key] = parseBoolean(await ask(`Need ${key}? (yes/no)`, config.features[key] ? "yes" : "no"), config.features[key]);
    }
    config.privacy.collectsUserData = parseBoolean(await ask("Collect user privacy data? (yes/no)", config.privacy.collectsUserData ? "yes" : "no"), config.privacy.collectsUserData);
    config.privacy.generateComplianceChecklist = parseBoolean(await ask("Generate privacy compliance checklist? (yes/no)", config.privacy.generateComplianceChecklist ? "yes" : "no"), config.privacy.generateComplianceChecklist);

    for (const key of Object.keys(config.automation)) {
      config.automation[key] = parseBoolean(await ask(`Automation permission ${key}? (yes/no)`, config.automation[key] ? "yes" : "no"), config.automation[key]);
    }
  } finally {
    rl.close();
  }

  return config;
}

function missingRequired(config) {
  const missing = [];
  if (!config.appid) missing.push("appid or WECHAT_APPID");
  if (!config.miniprogramRoot && !config.distRoot && !config.sourceRoot) missing.push("sourceRoot/miniprogramRoot/distRoot or WECHAT_PROJECT_PATH");
  if (config.useCloudBase && !config.cloudBaseEnvId && !process.env.TCB_ENV_ID && !process.env.CLOUD_BASE_ENV_ID) missing.push("cloudBaseEnvId or TCB_ENV_ID/CLOUD_BASE_ENV_ID");
  return missing;
}

async function main() {
  const existing = readJson(configPath) || {};
  let config;

  if (process.stdin.isTTY && process.stdout.isTTY) {
    config = await askAll(existing);
  } else {
    config = deepMerge(defaultConfig, existing);
    console.log("Non-interactive terminal detected. Wrote/merged placeholder config; edit it before deploy.");
  }

  writeConfig(config);
  const missing = missingRequired(config);
  console.log(`WeChat config written: ${path.relative(root, configPath)}`);
  console.log("Sensitive values must be supplied through env vars or CI secrets, never committed.");
  if (missing.length) {
    console.log(`Missing deploy-critical fields: ${missing.join(", ")}`);
  }
}

main().catch((error) => {
  console.error(`WeChat setup failed: ${error.message}`);
  process.exit(1);
});
