# Update Guardian Policy

## Why Update Guardian Exists

WeChat Mini Program development depends on platform APIs, review policy, DevTools behavior, `miniprogram-ci`, CloudBase, and Codex Skill conventions. These change over time. Update Guardian prevents this skill from relying on stale API parameters, outdated deployment assumptions, dead official links, or missing internal rules.

## What Changes Over Time

- WeChat API parameters, base-library requirements, permissions, privacy declarations, and review rules.
- `project.config.json`, `app.json`, `pages.json`, subpackage, `tabBar`, Skyline, GlassEasel, and component behavior.
- `miniprogram-ci` version, constructor options, preview/upload options, npm build, sourceMap, quality, and cloud function upload behavior.
- Taro, uni-app, React, Vue, TypeScript, WeUI, TDesign, CloudBase CLI, and CloudBase plugin versions.
- CloudBase environment binding, function/run deployment, database/storage permissions, and plugin config.
- Codex Skill and AGENTS.md conventions.

## How To Detect Documentation Changes

- Read `references/official-update-sources.md`.
- Fetch each URL with HEAD first and GET fallback.
- Store `etag`, `last-modified`, HTTP status, and a content hash when metadata is unavailable.
- Compare with the previous `artifacts/official-docs-snapshot.json`.
- If metadata or content hash changed, mark the URL as changed.
- Network failure is `unknown`, not "unchanged".

## How To Detect Dependency Changes

- Read `package.json`.
- For watchlisted packages present in dependencies or devDependencies, compare current version with `npm view <package> version`.
- For absent packages, mark `missing`.
- If npm access fails, mark `unknown`.
- Do not install or upgrade packages automatically.

## How To Detect Stale Skill Rules

- Check `SKILL.md` for the Update Guardian section.
- Check `AGENTS.md` for Update Guardian rules.
- Check package scripts for `wx:update-check`, `wx:health-check`, and `wx:update-skill-references`.
- Check required scripts, references, and assets exist.
- Check deployment scripts do not use obvious removed `miniprogram-ci` patterns after docs/version changes.

## Network Failure Handling

- Do not change code because a URL fails.
- Enter Conservative Mode for tasks that depend on unreachable official docs.
- Mark unreachable sources as `unknown`.
- Generate manual confirmation items with direct official URLs.

## Automatic Updates Allowed

- Append official source links to references.
- Add missing `wx:update-check`, `wx:health-check`, and `wx:update-skill-references` scripts.
- Append missing AGENTS.md Update Guardian rules.
- Append `.gitignore` entries for artifacts and local snapshots.
- Add or update GitHub Actions update-check template.

## Human Confirmation Required

- `miniprogram-ci` major version upgrades.
- WeChat API behavior changes.
- Login, payment, phone number, privacy, location, subscription, review, or audit rule changes.
- CloudBase production deployment config changes.
- Deleting or restructuring business code.
- Changing live release flow.

## Release Preflight

Before `wx:upload` or `wx:deploy`:

1. Run `npm run wx:health-check`.
2. Stop if health status is `blocked`.
3. If official update report has `high-risk-change`, manually confirm affected docs.
4. If dependency report shows `miniprogram-ci` major change, manually confirm before upgrade.
5. Save `artifacts/wechat-skill-health-report.md`.

## Weekly Automated Check

Run `npm run wx:health-check` weekly. Upload reports as CI artifacts. Do not auto-create PRs or issues unless explicitly configured outside this skill.

## Report Format

Write:

- `artifacts/update-guardian-report.json`
- `artifacts/update-guardian-report.md`
- `artifacts/official-update-report.json`
- `artifacts/official-update-report.md`
- `artifacts/dependency-version-report.json`
- `artifacts/dependency-version-report.md`
- `artifacts/wechat-skill-health-report.json`
- `artifacts/wechat-skill-health-report.md`
