# WeChat Mini Program Experience Ledger

Use the dedicated experience ledger before and after every nontrivial WeChat Mini Program workflow. It complements the global `error-ledger`: global records capture broad tool failures; this ledger captures domain-specific Mini Program lessons, migration traps, API policy changes, CI/upload issues, CloudBase behavior, privacy review notes, and project-specific fixes.

The ledger is not a flat diary. Every record must be classified by project and by a small atomic experience label so future preflight can retrieve the right lesson quickly.

## Storage

Default project-local store:

```text
.codex/wechat-miniprogram-experience-ledger.json
```

Use the default for project-specific learning. Override to a shared global store when you want cross-project reuse:

```bash
WX_EXPERIENCE_LEDGER_PATH=~/.codex/wechat-miniprogram-experience-ledger.json npm run wx:learn -- "upload miniprogram-ci"
```

Do not record secrets, AppSecret, private key content, payment keys, tokens, passwords, private cookies, `session_key`, production user data, or full private documents.

## Required Workflow

1. Preflight before work:

```bash
npm run wx:learn -- "migrate React to Taro login payment"
```

2. Record any failure, blocker, policy surprise, migration trap, or review feedback:

```bash
npm run wx:experience -- record \
  --scope project \
  --task-type deploy-miniprogram \
  --stage upload \
  --area miniprogram-ci \
  --capability upload \
  --framework native \
  --experience ip-whitelist \
  --severity blocker \
  --task "upload experience version" \
  --command "npm run wx:upload" \
  --summary "IP whitelist blocked miniprogram-ci upload" \
  --error "upload rejected by WeChat backend"
```

3. Resolve after the fix is known:

```bash
npm run wx:experience -- resolve 1 \
  --root-cause "CI runner IP was not allowed in WeChat backend upload IP whitelist" \
  --fix "Added runner IP or used approved upload environment" \
  --rule "Before CI upload, confirm WeChat upload IP whitelist includes the runner environment" \
  --verified-by "npm run wx:upload"
```

If the lesson is reusable across all Mini Program projects, promote it while resolving:

```bash
npm run wx:experience -- resolve 1 \
  --scope global \
  --root-cause "..." \
  --fix "..." \
  --rule "..."
```

4. Search narrow lessons when diagnosing:

```bash
npm run wx:experience -- search "payment backend signature"
npm run wx:experience -- list --status open
npm run wx:experience -- list --project current
npm run wx:experience -- list --project global
npm run wx:experience -- audit
npm run wx:experience-audit
npm run wx:experience -- dedupe
```

5. Export resolved lessons for review:

```bash
npm run wx:experience -- export
```

## Project Classification

Every record has:

- `projectScope`: `project`, `global`, `family`, or `account`.
- `projectId`: stable project identifier from `.codex/wechat-miniprogram.config.json`, package name, or workspace folder.
- `projectName`: human-readable project name.

Use `project` for project-only behavior, paths, current business rules, or review feedback.
Use `global` for reusable WeChat platform, API, CI, security, or migration lessons.
Use `family` for lessons shared by related Mini Programs under the same codebase/product line.
Use `account` for WeChat account-level settings such as upload IP whitelist or category qualification patterns.

Preflight searches current project plus shared scopes by default. Use `--all-projects` only when researching broadly.

## Atomic Taxonomy

Each record should be small enough to answer one future question. Prefer one record per error pattern, not one record per long debugging session.

Required fields:

- `taskType`: task router bucket.
- `stage`: workflow moment.
- `area`: engineering area.
- `capability`: WeChat capability or platform concern.
- `framework`: native, taro, uni-app, react, vue, h5, cloudbase, miniprogram-ci, github-actions, etc.
- `experience`: stable atomic label such as `missing-private-key`, `ip-whitelist`, `dom-api-incompat`, `frontend-secret-boundary`.
- `severity`: `info`, `warn`, `blocker`, or `critical`.

Task types:

- `create-new-miniprogram`
- `migrate-existing-project`
- `maintain-existing-miniprogram`
- `integrate-wechat-capability`
- `integrate-cloudbase`
- `deploy-miniprogram`
- `prepare-review`
- `debug`
- `unknown`

Stages:

- `setup`
- `inspect`
- `create`
- `migrate`
- `develop`
- `validate`
- `build`
- `preview`
- `upload`
- `deploy`
- `review`
- `cloudbase`
- `security`
- `docs`
- `ci`
- `unknown`

Areas:

- `config`
- `routing`
- `request`
- `storage`
- `auth`
- `login`
- `phone`
- `payment`
- `subscribe-message`
- `location`
- `map`
- `file`
- `media`
- `websocket`
- `cloudbase`
- `cloud-functions`
- `cloud-run`
- `privacy`
- `legal-domain`
- `package-size`
- `performance`
- `miniprogram-ci`
- `devtools`
- `github-actions`
- `migration`
- `security`
- `unknown`

Framework labels should be short and stable: `native`, `taro`, `uni-app`, `react`, `vue`, `h5`, `cloudbase`, `miniprogram-ci`, `github-actions`, or the project framework name.

Recommended atomic `experience` labels:

- `missing-project-config`
- `missing-app-or-pages-config`
- `missing-appid`
- `missing-private-key`
- `ip-whitelist`
- `legal-domain`
- `frontend-secret-boundary`
- `dom-api-incompat`
- `request-adapter`
- `cloudbase-env`
- `review-privacy`
- `package-size`
- `ci-deploy`

## What To Record

- Official-doc changes that affect implementation.
- `project.config.json`, `app.json`, `pages.json`, subpackage, or tabBar traps.
- React-to-Taro, Vue-to-uni-app, or H5 migration mismatches.
- Login, phone number, payment, subscription, location, media, file, WebSocket, and map integration fixes.
- CloudBase env binding, function, run, database, or storage permission issues.
- Legal domain, privacy, permission, review, package size, and performance findings.
- `miniprogram-ci`, private key path, IP whitelist, robot, preview QR, upload, and CI failures.

## What Not To Record

- Real private key content.
- AppSecret or payment keys.
- Tokens, passwords, cookies, `session_key`, or database credentials.
- Production user data or screenshots containing private data.
- Full proprietary documents or unredacted platform review messages.

## Promotion Rule

When a resolved lesson becomes stable and broadly reusable, export it and optionally summarize it in [learned-lessons.md](learned-lessons.md). Keep curated lessons concise and secret-free.

## Audit Workflow

Audit is automatic by default after:

- `npm run wx:experience -- record ...`
- `npm run wx:experience -- resolve ...`
- `npm run wx:experience -- dedupe`
- `npm run wx:validate`

Run manually when you want an explicit maintenance pass:

```bash
npm run wx:experience-audit
```

The audit writes:

- `artifacts/wechat-experience-audit.json`
- `artifacts/wechat-experience-audit.md`
- `.codex/wechat-miniprogram-experience-index.json`

The audit checks:

- Missing classification fields.
- Resolved records missing `rootCause`, `fix`, or `rule`.
- Open records older than 14 days.
- Duplicate records that should be merged with `dedupe`.
- Project records that should be promoted to `family` or `global`.
- Resolved records that should become templates or checklists.
- Ledger scale limits for large multi-project use.

Use audit output as a maintenance queue. Do not promote project-specific business rules to `global`.

Disable automatic audit only for debugging or CI performance isolation:

```bash
WX_EXPERIENCE_AUTO_AUDIT=0 npm run wx:validate
```
