# Troubleshooting

## AppID Missing

Block deployment. Set `appid` in `.codex/wechat-miniprogram.config.json` or `WECHAT_APPID`.

## Private Key Missing

Block preview/upload. Set `WECHAT_PRIVATE_KEY_PATH` to a local key file or provide `WECHAT_PRIVATE_KEY` in CI secrets. Never commit key content.

Run `npm run wx:secrets-init` to create `.env.local` placeholders and `.wechat-private/` before setting local key paths.

## `privateKeyPath` Does Not Exist

Check path expansion, working directory, and file permissions. Use an absolute path for local development.

If using the recommended local pattern, store the upload key under `.wechat-private/` and set `WECHAT_PRIVATE_KEY_PATH=.wechat-private/private.upload.key`.

## Secret Init Reports Blockers

Open `artifacts/wechat-secrets-init-report.json`. The report lists file names only and never prints secret values. Remove tracked `.env`, `.pem`, `.key`, or `*.secret.json` files from git index/history when needed, rotate credentials if a real secret was committed, and rerun `npm run wx:secrets-init`.

## IP Whitelist Failure

Confirm whether upload IP whitelist is enabled in WeChat settings. Add the CI runner IP or use an approved environment.

## `project.config.json` Error

Validate JSON syntax, `appid`, `projectname`, and `miniprogramRoot`. Confirm root path is relative to `project.config.json`.

## `miniprogramRoot` Error

Ensure the directory exists and contains `app.json` for native/Taro output or expected framework output.

## `app.json` Or `pages.json` Path Error

Check each page path has matching page files. Check `tabBar.list[].pagePath` exists.

## Build Failure

Run the underlying build script directly. Check package manager, lockfile, Node version, missing dependencies, and framework config.

## Package Too Large

Move optional pages to subpackages, compress assets, remove unused SDKs, lazy-load heavy modules, and keep the startup package small.

## Upload Failure

Check AppID, private key, developer permission, IP whitelist, `robot`, `miniprogram-ci` version, and project path.

## Preview QR Generation Failure

Confirm `artifacts/` is writable, `miniprogram-ci` is installed, and qrcode output path is valid.

## CloudBase `envId` Error

Confirm env exists, account has access, Mini Program is bound to the environment, and `wx.cloud.init` uses the same env.

## Legal Domain Not Configured

Configure request, uploadFile, downloadFile, and socket domains in WeChat backend settings. Do not assume one category covers all.

## Permission Or Privacy Review Failure

Compare every data collection and permission prompt with the privacy policy and official docs. Remove unnecessary collection, update declarations, and provide accurate review notes.
