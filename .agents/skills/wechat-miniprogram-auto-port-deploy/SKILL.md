---
name: wechat-miniprogram-auto-port-deploy
description: Use this skill when developing, migrating, validating, previewing, uploading, deploying, or preparing review materials for a WeChat Mini Program; converting React/Vue/H5 projects to WeChat Mini Program; configuring miniprogram-ci; integrating CloudBase; or checking WeChat Mini Program APIs, components, permissions, privacy, login, payment, subscription messages, location, file/media APIs, cloud functions, performance, package size, legal domains, or release readiness.
---

# WeChat Mini Program Auto Port Deploy

## 1. Mission

Deliver the smallest safe path from current code to a working WeChat Mini Program workflow: inspect, configure, migrate or develop, validate, build, preview, upload, and generate review materials. Optimize for first complete setup, then repeatable automation. Ask the user only when a real external blocker exists: missing AppID, missing upload key, missing account permission, unavailable official documentation for a task that depends on it, unclear business requirements, missing category/payment/privacy qualifications, or WeChat platform rejection.

## 2. When to Use This Skill

Use this skill for WeChat Mini Program creation, migration, maintenance, API integration, CloudBase integration, CI/CD, preview/upload automation, validation, security review, package-size/performance checks, legal domain checks, privacy/permission checks, and review material preparation.

## 3. Mandatory Runtime Documentation Lookup

Before touching any task involving WeChat Mini Program framework, API, component, devtools, miniprogram-ci, `project.config.json`, `app.json`, `pages.json`, subpackages, `tabBar`, Skyline, GlassEasel, WeUI, TDesign, login, phone number, payment, subscription messages, location, map, file/media APIs, Bluetooth/NFC/device APIs, request, WebSocket, CloudBase, cloud functions, cloud run, privacy, user authorization, legal domains, package size, performance, preview, upload, review, or release, enter Runtime Documentation Lookup.

Read [references/runtime-doc-lookup-policy.md](references/runtime-doc-lookup-policy.md) and [references/official-docs-map.md](references/official-docs-map.md). Query official or high-confidence sources first:

- WeChat Mini Program official docs: framework, API, components, devtools, CI, security.
- WeChat official GitHub organization and examples.
- `miniprogram-ci` official docs and npm package page.
- Tencent CloudBase official docs.
- Tencent component libraries such as TDesign Mini Program and WeUI Mini Program.

Record query date, URL, task relevance, confirmed API/component/config/permission requirements, version/base-library limits, implementation impact, and unresolved questions. If official docs cannot be reached, enter Conservative Mode: perform only general engineering work that does not depend on new or precise WeChat behavior, mark API/permission/review/payment/upload details as "pending official documentation confirmation", and generate a manual verification checklist with official URLs.

## 4. First-Run Configuration

Run `npm run wx:setup` or `node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/setup-wechat-config.js`. If configuration is missing, ask all first-run questions in one pass. Then run `npm run wx:secrets-init` to create ignored local secret placeholders, harden local file permissions when supported, prepare `.wechat-private/`, verify `.gitignore`, and scan for obvious plaintext secret risks. See [references/first-run-config.md](references/first-run-config.md) for the complete question set, config schema, and sensitive-data rules.

## Update Guardian

Before important tasks, run or explicitly consider Update Guardian:

- Creating a new Mini Program.
- Migrating an existing project to WeChat Mini Program.
- Integrating WeChat login, phone number, payment, subscription messages, location, map, files, media, Bluetooth, NFC, or device APIs.
- Integrating CloudBase.
- Modifying `project.config.json`, `app.json`, or `pages.json`.
- Modifying deployment scripts.
- Running preview, upload, or deploy.
- Preparing review materials.
- Modifying privacy policy or permission declarations.

Update Guardian responsibilities:

- Check the installed `miniprogram-ci` version.
- Query the latest `miniprogram-ci` version from npm.
- Compare current and latest versions.
- Record `miniprogram-ci` changelog/version changes as manual review items.
- Check WeChat Mini Program framework/API/component/devtools/CI docs are reachable.
- Check WeChat official GitHub examples are reachable.
- Check CloudBase Mini Program plugin docs are reachable.
- Check Codex Skill, AGENTS.md, and customization docs are reachable.
- Check current references for stale links.
- Check scripts for obviously stale `miniprogram-ci` usage.
- Check package scripts are complete.
- Check AGENTS.md contains current running rules.
- Write reports to `artifacts/update-guardian-report.md` and `artifacts/update-guardian-report.json`.

Run principles:

- Do not change code merely because the network failed.
- If official docs are unavailable, enter Conservative Mode.
- If a dependency is outdated, recommend upgrade only; do not upgrade main dependencies unless the user explicitly allows it.
- If official docs changed but impact is unclear, generate manual confirmation items.
- If Skill rules are clearly missing, automatic appends to references and AGENTS.md are allowed without deleting user content.
- Preserve existing user content and custom rules.

Recommended frequency:

- Manual: before every major development task.
- Automated: weekly.
- Release: before every `wx:upload` or `wx:deploy`.
- Long-running projects: monthly full health check.

Commands:

```bash
npm run wx:update-check
npm run wx:health-check
npm run wx:update-skill-references
```

Read [references/update-guardian-policy.md](references/update-guardian-policy.md), [references/official-update-sources.md](references/official-update-sources.md), and [references/version-watchlist.md](references/version-watchlist.md) before changing Update Guardian behavior.

## 5. Persistent Configuration

Read `.codex/wechat-miniprogram.config.json` before every task. Save only non-sensitive configuration there. Never save AppSecret, private key content, payment merchant keys, API tokens, `encodingAESKey`, database passwords, cloud keys, `session_key`, or user privacy data samples to the repository. Read sensitive values only from environment variables or CI secrets:

- `WECHAT_APPID`
- `WECHAT_PRIVATE_KEY_PATH`
- `WECHAT_PRIVATE_KEY`
- `WECHAT_PROJECT_PATH`
- `WECHAT_VERSION`
- `WECHAT_DESC`
- `WECHAT_ROBOT`
- `WECHAT_DEPLOY_MODE`
- `TCB_ENV_ID`
- `CLOUD_BASE_ENV_ID`

Use `npm run wx:secrets-init` for local secret setup. It may create `.env.local` with empty placeholders and `.wechat-private/` for local-only key files, but it must not copy live environment values, private key content, AppSecret, payment keys, or tokens into repository files. Prefer `WECHAT_PRIVATE_KEY_PATH` pointing to a local ignored key file for local preview/upload, and prefer CI Secrets for `WECHAT_PRIVATE_KEY` in automation. Treat `.env.local` as a convenience for local development, not a guarantee against network or log leakage.

## Dedicated Experience Ledger

Before every nontrivial WeChat Mini Program task, run a domain preflight:

```bash
npm run wx:learn -- "<task, framework, stage, capability, or error context>"
```

Use the dedicated ledger for WeChat-specific lessons, migration traps, official-doc changes, API/policy findings, CloudBase behavior, review feedback, upload/preview failures, legal-domain mistakes, package-size issues, and reusable fixes. Classify every record by project and atomic experience label:

```bash
npm run wx:experience -- record --scope project --task-type deploy-miniprogram --stage upload --area miniprogram-ci --capability upload --framework native --experience missing-private-key --severity blocker --summary "..." --error "..."
npm run wx:experience -- resolve <id> --root-cause "..." --fix "..." --rule "..."
npm run wx:experience -- search "payment backend signature"
npm run wx:experience-audit
```

Use `--scope project` for project-only paths, business rules, review feedback, and app-specific behavior. Promote stable reusable lessons with `--scope global` during resolve. Read [references/experience-ledger.md](references/experience-ledger.md) and [references/learned-lessons.md](references/learned-lessons.md) when diagnosing or planning. Store no secrets or private user data. Continue using the global `error-ledger` for broad command/tool failures; use this ledger for Mini Program domain memory.

Experience audit is automatic by default:

- `wx:experience record` audits after creating or updating a record.
- `wx:experience resolve` audits after resolving a record.
- `wx:experience dedupe` audits after merging records.
- `wx:validate` audits after validation completes.

Run `npm run wx:experience-audit` manually only when you want an explicit maintenance pass. The audit checks incomplete records, stale open records, duplicates, promotion candidates, template/checklist candidates, and JSON-ledger scale limits. It writes `artifacts/wechat-experience-audit.json`, `artifacts/wechat-experience-audit.md`, and `.codex/wechat-miniprogram-experience-index.json`. Set `WX_EXPERIENCE_AUTO_AUDIT=0` only for debugging or CI performance isolation.

## 6. Task Router

Classify every request before editing files:

- `create-new-miniprogram`: lookup docs, read config, choose native/Taro/uni-app, create base app config and pages, generate platform/request/storage layers, add validation/deploy scripts, run validation.
- `migrate-existing-project`: lookup docs, run inspect, write migration report, choose route, migrate routing/request/state/pages/styles/components, replace DOM-only APIs, generate Mini Program config, validate and auto-fix.
- `maintain-existing-miniprogram`: lookup docs, inspect, implement requested feature, validate `app.json`/`pages.json`/`project.config.json`, check permissions/privacy, build and preview.
- `integrate-wechat-capability`: lookup matching official docs first, generate frontend code plus backend/cloud security boundary, check permissions/privacy/legal domains, add tests or manual test steps, validate.
- `integrate-cloudbase`: lookup CloudBase docs, check `envId`, `wx.cloud.init`, cloud functions/cloud run, generate config/deploy instructions, validate.
- `deploy-miniprogram`: lookup miniprogram-ci/devtools CI docs, inspect, validate, build, preview/upload/both, report blockers and fixes.
- `prepare-review`: lookup review/privacy/permission docs, generate version notes, feature notes, privacy checklist, test account instructions when needed, and pre-release checklist. Never guarantee approval.

## 7. Project Inspection

Run `npm run wx:inspect` before migration, maintenance, capability integration, deploy, or review. The script writes `artifacts/wechat-inspect-report.json` and detects package manager, framework, Mini Program roots, CloudBase, CI, scripts, DOM-only APIs, risky env exposure, secrets keywords, private key files, payment-key keywords, and hardcoded domains.

## 8. Migration Strategy

Load [references/migration-checklist.md](references/migration-checklist.md) for detailed checks.

- React defaults to Taro unless config says `uni-app`, `native`, or `keep-existing`.
- Vue defaults to uni-app unless config says `Taro`, `native`, or `keep-existing`.
- H5 requires an assessment report first; migrate business logic, API layer, data models, and page structure before visual parity.
- Existing WeChat Mini Programs should not be needlessly replatformed; improve validation, type safety, deployment, CI, security, performance, and review readiness in place.

## 9. Development Rules

Keep platform differences under `src/platform/wechat/` or the project's existing equivalent. Keep request logic under `src/services/` or the existing service layer. Preserve user business logic. Do not delete user code without explicit permission. Merge config instead of overwriting it. See [references/development-checklist.md](references/development-checklist.md).

## 10. Security Rules

Never hardcode secrets. Never place AppSecret, merchant payment keys, or `session_key` in Mini Program frontend code or frontend storage. For login, Mini Program calls `wx.login` to get a code; server/cloud exchanges it for `openid` and `session_key`; frontend stores only a business token or safe session identifier. For payment, backend creates the order and signatures; Mini Program calls `wx.requestPayment`. Check legal request/upload/download/socket domains and privacy declarations. See [references/security-checklist.md](references/security-checklist.md).

## 11. CloudBase Rules

When CloudBase is enabled, check `cloudbaserc.json`, `cloudbase.json`, `tcb.json`, `envId`, `wx.cloud.init`, cloud function directories, cloud run calls, environment binding, permissions, and CI deploy needs. Do not assume account permissions or environment binding. See [references/cloudbase-checklist.md](references/cloudbase-checklist.md).

## 12. Deployment Automation

Use these root scripts:

```json
{
  "wx:setup": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/setup-wechat-config.js",
  "wx:secrets-init": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/setup-wechat-secrets.js",
  "wx:inspect": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/inspect-project.js",
  "wx:validate": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/validate-miniprogram.js",
  "wx:preview": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-preview.js",
  "wx:upload": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-upload.js",
  "wx:deploy": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-deploy.js",
  "wx:review": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/generate-review-materials.js",
  "wx:experience": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wechat-experience-ledger.js",
  "wx:learn": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wechat-experience-ledger.js preflight",
  "wx:experience-audit": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wechat-experience-ledger.js audit",
  "wx:update-check": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/check-official-updates.js && node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/check-dependency-versions.js",
  "wx:health-check": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/skill-health-check.js",
  "wx:update-skill-references": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/update-skill-references.js"
}
```

`wx:deploy` must run or reference Update Guardian health, inspect, validate, dependency install if needed, build if a build script exists, validate again, then preview/upload/both according to `WECHAT_DEPLOY_MODE` or config. Use [references/deployment-checklist.md](references/deployment-checklist.md).

## 13. Validation and Auto-Fix Loop

After every development or migration pass:

1. Run inspect.
2. Run validate.
3. Run existing build, lint, test, and typecheck scripts when present.
4. If a step fails, classify whether it can be auto-fixed.
5. Record WeChat-specific failure context with `wx:experience` and broad tool failures with `error-ledger`.
6. Auto-fix for at most 3 rounds.
7. Resolve the dedicated ledger record when the fix is verified.
8. Stop on the third failed round and report blockers.

Non-auto-fixable blockers include missing real AppID, missing upload key, missing account permission, official docs unavailable for a new/precise API, missing payment qualification, missing category qualification, unclear business rules, missing backend API, and unclear user privacy collection scope.

## 14. Review and Release Boundaries

The skill can generate review materials, support pre-submit checks, and attempt upload when tools, account permissions, and user authorization allow it. It cannot bypass WeChat review, guarantee approval, guarantee final release, forge category/qualification/privacy/payment materials, hide real data collection, or assert correctness without official documentation confirmation. See [references/review-and-release-boundaries.md](references/review-and-release-boundaries.md).

## 15. Output Format

At completion, report modified files, commands executed, validation results, unverified items, risk points, and recommended next steps. For deploy/review tasks, include artifact paths and clearly separate blockers from warnings.

## 16. Failure Handling

When a WeChat Mini Program task fails, record domain context with `npm run wx:experience -- record ...` without secrets. When a command, script, download, browser automation, API call, dependency operation, or generic skill workflow fails, also record it with `error-ledger record` when useful. After the fix is known, resolve the dedicated record and any global record with root cause, fix, and prevention rule. Use [references/troubleshooting.md](references/troubleshooting.md) and the dedicated experience ledger for common WeChat Mini Program failures and actionable fixes.
