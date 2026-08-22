# Development Checklist

## Pages

- Register every page in `app.json` or `pages.json`.
- Ensure page files exist.
- Add loading, empty, error, and success states for data-driven pages.
- Keep first-load dependencies small.

## Components

- Use Mini Program-compatible components.
- Register custom components in the correct page/app config.
- Avoid browser DOM assumptions.
- Keep component events and props aligned with official docs.

## API Calls

- Centralize API calls in a service layer.
- Use `wx.request`, `Taro.request`, or `uni.request`.
- Never put AppSecret, merchant keys, API tokens, or database passwords in frontend code.
- Add timeout, retry policy when appropriate, and user-safe errors.

## Permissions And Privacy

- Check required user authorization before capability use.
- Add privacy checklist when collecting personal data.
- Explain why data is needed and keep collection minimal.
- Check login, phone number, payment, subscription, location, map, file/media, and device permissions against current docs.

## Legal Domains

- Remind user to configure request domains.
- Separately remind uploadFile, downloadFile, and WebSocket domains.
- Do not assume CloudBase or cloud run endpoint is automatically allowed.

## Error Handling

- Handle network failure, API failure, auth failure, permission denial, empty results, and rate limits.
- Avoid leaking backend error internals to users.
- Keep logs free of secrets and personal data.

## Performance

- Check startup package size.
- Move heavy optional pages to subpackages.
- Avoid loading large SDKs on the homepage.
- Minimize images and media.
- Prefer lazy loading for non-critical data.

## Logging

- Redact tokens, phone numbers, identity data, order secrets, and cloud credentials.
- Do not print private key content or environment secrets in CI.
