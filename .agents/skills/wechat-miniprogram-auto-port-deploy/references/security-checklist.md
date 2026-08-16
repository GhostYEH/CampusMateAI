# Security Checklist

## Secrets

- Do not commit AppSecret.
- Do not commit private key content.
- Do not commit third-party API keys, access tokens, passwords, or service account secrets.
- Do not commit payment merchant keys, API v3 keys, or certificates.
- Do not store `session_key` in frontend code or business storage.
- Do not print CI secrets.
- Add `.env`, `.env.*`, `private.*.key`, `*.pem`, `.wechat-private/`, and `*.secret.json` to `.gitignore`.
- Run `npm run wx:secrets-init` before local preview/upload setup.
- Use `.env.local` only for ignored local placeholders or local-only values.
- Never print `.env.local` contents in terminal output, logs, artifacts, screenshots, or experience records.
- Prefer `WECHAT_PRIVATE_KEY_PATH` pointing to an ignored local file for local upload keys.
- Prefer CI Secrets for `WECHAT_PRIVATE_KEY` in automation.
- Do not copy live shell or CI environment values into committed config files.
- Treat `process.env` in frontend builds as unsafe until verified; only expose explicitly public variables.

## Boundaries

- Mini Program frontend may call `wx.login` and receive a code.
- Backend or cloud function exchanges code for `openid` and `session_key`.
- Backend issues a business token or safe session identifier.
- Payment order creation, signing, and merchant credentials stay on backend/cloud only.
- Mini Program frontend only calls `wx.requestPayment` with backend-provided payment parameters.

## Legal Domains

- Check request domain.
- Check uploadFile domain.
- Check downloadFile domain.
- Check WebSocket domain.
- Check cloud run or custom backend endpoints.

## Privacy And Permissions

- Collect the minimum data required.
- Explain purpose for phone number, location, media, files, identity, payment, and subscription messages.
- Verify privacy declarations and permission prompts against current official docs.
- Do not use fake category, fake qualification, or hidden data collection.

## Logging

- Redact tokens, code values, phone numbers, order identifiers when sensitive, and user identifiers when not needed.
- Avoid logging full request/response bodies that may contain personal data.
- Confirm generated artifacts and experience records do not contain private key content, AppSecret, payment keys, tokens, or full private documents.
