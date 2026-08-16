# Runtime Documentation Lookup Policy

## When Lookup Is Mandatory

Lookup is mandatory before work involving WeChat Mini Program framework, APIs, components, devtools, `miniprogram-ci`, `project.config.json`, `app.json`, `pages.json`, subpackages, `tabBar`, Skyline, GlassEasel, WeUI, TDesign, login, phone number, payment, subscription messages, location, map, file upload/download, media, Bluetooth/NFC/device APIs, request, WebSocket, CloudBase, cloud functions, cloud run, privacy, user authorization, legal domains, package size, performance, upload, preview, review, or release.

## Sources To Query First

Prefer official or high-confidence sources in this order:

1. WeChat official Mini Program documentation.
2. WeChat official GitHub repositories and examples.
3. Official `miniprogram-ci` docs and npm package page.
4. Tencent CloudBase official docs.
5. Tencent maintained component libraries: WeUI Mini Program and TDesign Mini Program.

Use [official-docs-map.md](official-docs-map.md) for exact URLs and pitfalls.

## How To Record Lookup Results

Write lookup notes in the task output, deployment report, review material, or an artifact under `artifacts/` when the workflow produces artifacts. Include:

- Query date.
- Document URL.
- Task relevance.
- Confirmed API/component/config/permission requirement.
- Version or base-library limits.
- Implementation impact.
- Remaining uncertainty.

## Conservative Mode

Enter Conservative Mode when official docs are unavailable, network access fails, docs conflict, or the task depends on an API/policy that may have changed. In Conservative Mode:

- Do general engineering work only: inspect, refactor shared logic, add wrappers, create placeholders, generate reports.
- Do not claim API parameter correctness, permission correctness, payment readiness, upload readiness, or review readiness.
- Mark affected items as "pending official documentation confirmation".
- Generate a manual check list with direct official URLs.
- Stop before irreversible deployment or review actions unless the user explicitly accepts the risk and the action is technically safe.

## Required Labels

Use these labels in reports:

- `confirmed-by-official-docs`: checked during this run.
- `pending-official-docs-confirmation`: blocked by inaccessible or unverified docs.
- `blocked-by-account-or-qualification`: requires WeChat account, category, payment, privacy, or backend access.
- `safe-general-engineering`: does not depend on WeChat-specific current behavior.
