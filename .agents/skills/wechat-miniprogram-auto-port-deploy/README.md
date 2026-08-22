# wechat-miniprogram-auto-port-deploy

[English](README.md) | [简体中文](README.zh-CN.md)

**wechat-miniprogram-auto-port-deploy is a Codex Skill for professional WeChat Mini Program development, migration, validation, preview, upload, CloudBase integration, and review-preparation automation.** It helps teams turn React, Vue, H5, native Mini Program, Taro, or uni-app projects into a repeatable Mini Program engineering workflow with security checks and release guardrails.

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-111827)](SKILL.md)
[![WeChat Mini Program](https://img.shields.io/badge/WeChat-Mini%20Program-07C160)](https://developers.weixin.qq.com/miniprogram/dev/framework/)
[![miniprogram-ci](https://img.shields.io/badge/miniprogram--ci-supported-blue)](https://developers.weixin.qq.com/miniprogram/dev/devtools/ci.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

If this saves you time on WeChat Mini Program development, please star the repository so more developers can find it.

## What Is This Project?

This repository packages a reusable Codex Skill named `wechat-miniprogram-auto-port-deploy`. The skill gives Codex a structured workflow for creating, migrating, maintaining, validating, previewing, uploading, and preparing review materials for WeChat Mini Programs.

It is designed for developers who want fewer manual release steps, safer credential handling, and a consistent migration path from web projects to Mini Programs.

## Why Use It?

- **Develop new WeChat Mini Programs** with native, Taro, or uni-app routes.
- **Migrate React, Vue, and H5 projects** into Mini Program-compatible architecture.
- **Validate project structure** including `project.config.json`, `app.json`, `pages.json`, page paths, `tabBar`, and package scripts.
- **Detect Mini Program incompatibilities** such as DOM-only APIs, browser storage, direct `fetch`, Web SDKs, and unsafe frontend environment usage.
- **Protect secrets** with `.env.local` bootstrap, `.wechat-private/`, CI Secret guidance, private key cleanup, and plaintext secret scanning.
- **Automate preview and upload** through `miniprogram-ci`.
- **Prepare review materials** while clearly documenting what cannot be automated or guaranteed.
- **Learn from failures** through a dedicated WeChat Mini Program experience ledger.
- **Track official changes** with Update Guardian checks for WeChat docs, CloudBase docs, GitHub sources, and dependency versions.

## Quick Start

Install this skill into a Codex workspace:

```bash
mkdir -p .codex/skills/wechat-miniprogram-auto-port-deploy
cp -R ./* .codex/skills/wechat-miniprogram-auto-port-deploy/
```

Add or merge these scripts into your project `package.json`:

```json
{
  "scripts": {
    "wx:setup": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/setup-wechat-config.js",
    "wx:secrets-init": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/setup-wechat-secrets.js",
    "wx:inspect": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/inspect-project.js",
    "wx:validate": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/validate-miniprogram.js",
    "wx:preview": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-preview.js",
    "wx:upload": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-upload.js",
    "wx:deploy": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-deploy.js",
    "wx:review": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/generate-review-materials.js",
    "wx:learn": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wechat-experience-ledger.js preflight",
    "wx:experience": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wechat-experience-ledger.js",
    "wx:health-check": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/skill-health-check.js"
  }
}
```

Then run:

```bash
npm run wx:setup
npm run wx:secrets-init
npm run wx:inspect
npm run wx:validate
```

## Common Commands

```bash
npm run wx:setup              # Create or merge non-sensitive Mini Program config
npm run wx:secrets-init       # Create ignored local secret placeholders and scan for secret risks
npm run wx:inspect            # Identify framework, package manager, Mini Program roots, CI, CloudBase, and risks
npm run wx:validate           # Validate project structure, security, compatibility, domains, privacy, and package risk
npm run wx:preview            # Generate preview QR code with miniprogram-ci
npm run wx:upload             # Upload development/experience version with miniprogram-ci
npm run wx:deploy             # Inspect, validate, build, validate again, then preview/upload/both
npm run wx:review             # Generate review and release-preparation materials
npm run wx:learn -- "upload private key"  # Search project-specific WeChat lessons
npm run wx:health-check       # Check skill health, docs reachability, and dependency watchlist
```

## What Gets Generated?

- `artifacts/wechat-inspect-report.json`
- `artifacts/wechat-validation-report.json`
- `artifacts/wechat-preview-qrcode.jpg`
- `artifacts/wechat-upload-report.json`
- `artifacts/wechat-deploy-report.json`
- `artifacts/wechat-review-materials.md`
- `artifacts/wechat-secrets-init-report.json`
- `artifacts/wechat-skill-health-report.json`

Generated artifacts are intended for local workflow and CI debugging. They should not contain secrets.

## Security Model

This skill is intentionally strict about credentials:

- Do not commit AppSecret.
- Do not commit upload private key content.
- Do not commit payment merchant keys or API v3 keys.
- Do not put `session_key` into Mini Program frontend code or frontend storage.
- Use `WECHAT_PRIVATE_KEY_PATH` for local upload key files.
- Use `WECHAT_PRIVATE_KEY` only through CI Secrets or runtime environment variables.
- Keep signing, payment order creation, and login code exchange on backend or CloudBase functions.

The `wx:secrets-init` command creates `.env.local` placeholders and `.wechat-private/`, checks ignore rules, and scans for obvious secret patterns without printing secret values.

## Migration Strategy

| Source project | Recommended route |
| --- | --- |
| React | Taro by default, unless configured otherwise |
| Vue | uni-app by default, unless configured otherwise |
| H5 | Assessment first, then migrate business logic, API layer, data model, and pages |
| Existing Mini Program | Keep the current structure and improve validation, CI, security, and release readiness |

The skill avoids blind one-to-one DOM copying. It focuses on Mini Program-safe adapters for routing, request, storage, platform capability, permissions, privacy, and package-size control.

## CloudBase Support

The skill can check and guide:

- `envId`
- `wx.cloud.init`
- cloud functions
- CloudBase Run
- database and storage permissions
- Mini Program account and environment binding
- CloudBase Framework Mini Program plugin deployment settings

It does not assume you already have CloudBase permissions or that an environment is bound to your Mini Program account.

## Review And Release Boundaries

This project can generate review materials, pre-release checklists, and upload attempts when credentials and permissions are available. It cannot bypass WeChat review, guarantee approval, forge qualifications, hide real data collection, or replace manual confirmation for category, privacy, payment, content, and production backend readiness.

## Repository Topics

Suggested GitHub topics:

`wechat-miniprogram`, `miniprogram`, `codex-skill`, `miniprogram-ci`, `taro`, `uni-app`, `cloudbase`, `wechat-devtools`, `frontend-migration`, `ci-cd`, `automation`, `security`, `privacy`, `release-automation`

## Documentation

- [Skill instructions](SKILL.md)
- [Runtime documentation lookup policy](references/runtime-doc-lookup-policy.md)
- [First-run configuration](references/first-run-config.md)
- [Migration checklist](references/migration-checklist.md)
- [Security checklist](references/security-checklist.md)
- [Deployment checklist](references/deployment-checklist.md)
- [CloudBase checklist](references/cloudbase-checklist.md)
- [Troubleshooting](references/troubleshooting.md)

## Contributing

Issues and pull requests are welcome. Useful contributions include new migration rules, better validation checks, CloudBase deployment patterns, official documentation update notes, and safer defaults for Mini Program CI.

Please do not include real AppID secrets, private keys, payment keys, API tokens, user data, or private business documents in issues or pull requests.

## License

MIT
