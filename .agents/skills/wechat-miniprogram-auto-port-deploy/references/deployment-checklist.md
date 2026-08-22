# Deployment Checklist

- AppID exists and matches the target Mini Program account.
- `project.config.json` exists and points to a valid `miniprogramRoot`.
- `app.json` or `pages.json` exists.
- Page paths and `tabBar` paths exist.
- `privateKeyPath` exists locally or `WECHAT_PRIVATE_KEY` is available in CI.
- `miniprogram-ci` is installed as a project dependency or dev dependency.
- Preview produces `artifacts/wechat-preview-qrcode.jpg`.
- Upload produces `artifacts/wechat-upload-report.json`.
- `robot` is set, default `1`.
- CI secrets exist: `WECHAT_APPID`, `WECHAT_PRIVATE_KEY`, `WECHAT_PROJECT_PATH`, `WECHAT_ROBOT`, `WECHAT_DEPLOY_MODE`.
- IP whitelist allows the current upload environment when enabled.
- Version is resolved from package.json, git tag, datetime, manual env, or config.
- Description is resolved from git commit, manual env, or default text.
- Artifacts are uploaded by CI: inspect, validation, preview QR, upload report, deploy report.
- Rollback plan exists: keep previous uploaded version and changelog.
- Experience version is manually verified before review submission.
