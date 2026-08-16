# WeChat Mini Program Skill Usage

Use the skill in Codex for Mini Program development, migration, validation, preview, upload, deploy, CloudBase integration, and review material generation.

## First Run

```bash
npm run wx:setup
npm run wx:secrets-init
```

Edit `.codex/wechat-miniprogram.config.json` for non-sensitive settings. Use the generated `.env.local`, shell environment variables, or CI secrets for sensitive runtime values. `.env.local` is ignored and should contain only local placeholders or local-only values; never commit real secrets.

## Common Commands

```bash
npm run wx:inspect
npm run wx:secrets-init
npm run wx:validate
npm run wx:preview
npm run wx:upload
npm run wx:deploy
npm run wx:review
npm run wx:learn -- "deploy upload miniprogram-ci"
npm run wx:experience -- search "legal domain"
npm run wx:experience-audit
npm run wx:update-check
npm run wx:health-check
npm run wx:update-skill-references
```

Experience audit runs automatically after records change and after `wx:validate`. Manual `wx:experience-audit` is for explicit maintenance.

## Dedicated Experience Ledger

Before nontrivial work, run:

```bash
npm run wx:learn -- "<task context>"
```

When a WeChat Mini Program-specific issue is found, record it:

```bash
npm run wx:experience -- record --stage validate --area config --summary "..." --error "..."
```

After fixing it, resolve it:

```bash
npm run wx:experience -- resolve <id> --root-cause "..." --fix "..." --rule "..."
```

For useful retrieval, classify records:

```bash
npm run wx:experience -- record \
  --scope project \
  --task-type deploy-miniprogram \
  --stage upload \
  --area miniprogram-ci \
  --capability upload \
  --framework native \
  --experience missing-private-key \
  --severity blocker \
  --summary "..." \
  --error "..."
```

Use `--scope global` only for stable lessons that should apply across Mini Program projects.

## Update Guardian

Run before major work and before release:

```bash
npm run wx:health-check
```

Run weekly or manually:

```bash
npm run wx:update-check
```

Generate reference update suggestions:

```bash
npm run wx:update-skill-references
```

Do not upgrade dependencies automatically from these reports. Confirm high-risk official changes and major dependency changes manually.

## Required Secret Inputs

Use environment variables or CI secrets:

- `WECHAT_APPID`
- `WECHAT_PRIVATE_KEY_PATH` or `WECHAT_PRIVATE_KEY`
- `WECHAT_PROJECT_PATH`
- `WECHAT_ROBOT`
- `WECHAT_DEPLOY_MODE`

Do not commit AppSecret, private key content, payment keys, cloud credentials, database passwords, `encodingAESKey`, or `session_key`.

For local setup:

```bash
npm run wx:secrets-init
```

This creates `.env.local` placeholders, prepares `.wechat-private/`, checks `.gitignore`, and writes `artifacts/wechat-secrets-init-report.json`. It does not copy live environment variable values into files.

## Boundary

The automation can inspect, validate, preview, upload, and prepare review materials. It cannot guarantee review approval, bypass review, forge qualifications, or replace human release confirmation.
