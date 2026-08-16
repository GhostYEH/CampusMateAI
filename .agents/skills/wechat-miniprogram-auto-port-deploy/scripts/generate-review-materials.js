#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const root = process.cwd();
const artifactsDir = path.join(root, "artifacts");
const reviewDir = path.join(artifactsDir, "wechat-review-materials");
const indexPath = path.join(reviewDir, "review-materials-index.json");

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

function writeFile(relativeName, content) {
  const file = path.join(reviewDir, relativeName);
  fs.writeFileSync(file, content.trim() + "\n");
  return path.relative(root, file);
}

function yesNo(value) {
  return value ? "Yes" : "No";
}

function main() {
  ensureDir(reviewDir);
  const config = readJson(path.join(root, ".codex", "wechat-miniprogram.config.json")) || {};
  const inspect = readJson(path.join(artifactsDir, "wechat-inspect-report.json")) || {};
  const validation = readJson(path.join(artifactsDir, "wechat-validation-report.json")) || {};
  const features = config.features || {};
  const privacy = config.privacy || {};
  const generatedAt = new Date().toISOString();

  const files = [];
  files.push(writeFile("version-summary.md", `
# Version Summary

- Generated at: ${generatedAt}
- Project name: ${config.projectName || "TODO"}
- AppID present: ${yesNo(Boolean(process.env.WECHAT_APPID || config.appid))}
- Deploy mode: ${config.deployMode || "preview"}
- Version strategy: ${config.versionStrategy || "package-json"}
- Description strategy: ${config.descStrategy || "git-commit"}

## Review Boundary

This material assists review preparation but does not guarantee WeChat review approval or formal release.
`));

  files.push(writeFile("feature-description.md", `
# Feature Description

## Enabled Capabilities

- Login: ${yesNo(features.login)}
- Phone number: ${yesNo(features.phoneNumber)}
- Payment: ${yesNo(features.payment)}
- Subscription messages: ${yesNo(features.subscribeMessage)}
- Location: ${yesNo(features.location)}
- Map: ${yesNo(features.map)}
- File upload/download: ${yesNo(features.file)}
- Media: ${yesNo(features.media)}
- WebSocket: ${yesNo(features.websocket)}

## User Flow Summary

TODO: Describe the user-facing flow, main pages, and why each requested capability is necessary.

## Backend Boundary

Secrets, AppSecret, payment merchant keys, signing, and session_key exchange must stay on backend/cloud functions.
`));

  files.push(writeFile("privacy-compliance-checklist.md", `
# Privacy Compliance Checklist

- Collects user data: ${yesNo(privacy.collectsUserData)}
- Generate compliance checklist requested: ${yesNo(privacy.generateComplianceChecklist !== false)}
- Confirm privacy policy text matches actual data collection.
- Confirm permission prompts match current official docs.
- Confirm phone number, location, media, files, subscription messages, payment, and identity data are necessary and minimized.
- Confirm logs redact tokens, phone numbers, user identifiers, payment data, and location data.
- Confirm no AppSecret, private key, merchant key, or session_key is stored in frontend code.

## Pending Manual Confirmation

- Category qualification.
- Payment qualification if payment is enabled.
- Privacy policy URL and version.
- Production backend legal domains.
`));

  files.push(writeFile("test-account-template.md", `
# Test Account Instructions

Use this template only when review needs a test account.

- Test account username: TODO, do not commit real password.
- Test account password delivery: provide securely outside repository.
- Required test steps:
  1. Open Mini Program.
  2. Complete login flow.
  3. Navigate to primary feature pages.
  4. Test enabled sensitive capabilities with clear consent.
  5. Confirm payment uses sandbox/test flow if applicable.

Do not include private user data or production credentials in repository files.
`));

  files.push(writeFile("pre-release-checklist.md", `
# Pre-Release Checklist

- Inspect report exists: ${yesNo(Boolean(inspect.generatedAt))}
- Validation report exists: ${yesNo(Boolean(validation.generatedAt))}
- Validation status: ${validation.status || "not-run"}
- Blockers: ${validation.issues ? validation.issues.filter((issue) => issue.severity === "blocker").length : "unknown"}
- Preview QR generated and manually verified.
- Upload result reviewed.
- WeChat official docs checked for APIs, privacy, upload, and review requirements during this release pass.
- Legal domains configured for request/upload/download/socket.
- AppID, account permissions, robot, private key, and IP whitelist verified.
- Package size and subpackages checked.
- Production backend, CloudBase env, monitoring, and rollback plan confirmed.

This checklist cannot replace official WeChat platform review or human compliance confirmation.
`));

  const index = {
    generatedAt,
    files,
    boundaries: [
      "Cannot guarantee review approval.",
      "Cannot bypass review.",
      "Cannot forge qualifications or privacy statements.",
      "Formal release requires human confirmation."
    ]
  };
  fs.writeFileSync(indexPath, JSON.stringify(index, null, 2));
  console.log(`WeChat review materials written: ${path.relative(root, reviewDir)}`);
}

main();
