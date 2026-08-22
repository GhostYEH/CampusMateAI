# First-Run Configuration

Run `npm run wx:setup`, then run `npm run wx:secrets-init`. If `.codex/wechat-miniprogram.config.json` is missing, collect all answers in one interactive pass. In non-interactive CI, create a placeholder config and fail with clear missing-field messages.

## Questions

Base information:

- WeChat Mini Program AppID.
- Stable `projectId` for project-specific experience classification.
- Project name.
- Project type: `native`, `Taro`, `uni-app`, `React`, `Vue`, `H5`, `unknown`.
- Target route: `native`, `Taro`, `uni-app`, `keep-existing`, `auto`.
- Mini Program source directory.
- Build output directory.
- Package manager preference: `pnpm`, `npm`, `yarn`, `bun`, `auto`.

Account and deploy:

- Whether the account has Mini Program developer permission.
- Whether an upload private key exists.
- Private key storage mode: `local-file`, `CI-secret`, `env-content`.
- `privateKeyPath` or CI secret name.
- Whether upload IP whitelist is enabled.
- Upload robot number, default `1`.
- Deploy mode: `preview`, `upload`, `both`.
- Version strategy: `package-json`, `git-tag`, `datetime`, `manual`.
- Upload description strategy: `git-commit`, `manual`, `default`.

Backend and cloud:

- Backend type: `existing-http-api`, `CloudBase-functions`, `CloudBase-run`, `custom-backend`, `none`.
- Whether CloudBase is used.
- CloudBase `envId`.
- Whether cloud function directory exists.
- Whether cloud run service exists.

Capabilities:

- Login.
- Phone number.
- Payment.
- Subscription messages.
- Location.
- Map.
- File upload/download.
- Image/video/audio media.
- WebSocket.
- User privacy data collection.
- Privacy compliance checklist generation.
- Review material generation.

Automation permissions:

- Allow modifying `package.json`.
- Allow modifying `AGENTS.md`.
- Allow appending `.gitignore`.
- Allow generating GitHub Actions.
- Allow automatic migration of directory structure.
- Allow deleting clearly useless generated files, default no.
- Allow automated review submission only when platform ability, account permission, and explicit user authorization all exist.

## Config File

Save non-sensitive config to `.codex/wechat-miniprogram.config.json`:

```json
{
  "appid": "",
  "projectId": "",
  "projectName": "",
  "projectType": "auto",
  "targetFramework": "auto",
  "sourceRoot": "",
  "miniprogramRoot": "",
  "distRoot": "",
  "packageManager": "auto",
  "deployMode": "preview",
  "robot": 1,
  "versionStrategy": "package-json",
  "descStrategy": "git-commit",
  "backendType": "none",
  "useCloudBase": false,
  "cloudBaseEnvId": "",
  "features": {
    "login": false,
    "phoneNumber": false,
    "payment": false,
    "subscribeMessage": false,
    "location": false,
    "map": false,
    "file": false,
    "media": false,
    "websocket": false
  },
  "privacy": {
    "collectsUserData": false,
    "generateComplianceChecklist": true
  },
  "automation": {
    "allowModifyPackageJson": true,
    "allowModifyAgentsMd": true,
    "allowModifyGitignore": true,
    "allowGenerateGithubActions": true,
    "allowSubmitReview": false
  }
}
```

## Sensitive Data Rules

Never save these values to the repository:

- AppSecret.
- Private key content.
- Payment merchant keys.
- API tokens.
- Third-party API keys.
- Access tokens.
- Service account secrets.
- `encodingAESKey`.
- Database passwords.
- Cloud service keys.
- `session_key`.
- User privacy data samples.

Use environment variables or CI secrets for sensitive values:

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

## Local Secret Bootstrap

Use:

```bash
npm run wx:secrets-init
```

The bootstrap must:

- Create `.env.local` with empty placeholders when missing.
- Leave an existing `.env.local` unchanged.
- Set `.env.local` permissions to `0600` when the filesystem supports it.
- Create `.wechat-private/` with local-only guidance for upload key files.
- Ensure `.gitignore` contains `.env`, `.env.*`, `private.*.key`, `*.pem`, `.wechat-private/`, and `*.secret.json`.
- Write `artifacts/wechat-secrets-init-report.json`.
- Scan local secret-like files for obvious private key, AppSecret, payment key, and `session_key` patterns without printing values.
- Scan local `.env*` files for generic API key, token, secret, and password variable patterns without printing values.

The bootstrap must not:

- Copy live environment variable values into `.env.local`.
- Write `WECHAT_PRIVATE_KEY` private key content into any repository file.
- Store AppSecret, payment merchant keys, API tokens, database passwords, cloud credentials, `encodingAESKey`, `session_key`, or user privacy data samples.
- Treat `.env.local` as sufficient protection against frontend bundling, CI log leakage, or network exfiltration.
- Print `.env.local` contents to terminal output, logs, artifacts, screenshots, or experience records.

Recommended local upload-key pattern:

```bash
WECHAT_PRIVATE_KEY_PATH=.wechat-private/private.upload.key
```

Recommended CI pattern:

```bash
WECHAT_PRIVATE_KEY=<CI secret value>
```
