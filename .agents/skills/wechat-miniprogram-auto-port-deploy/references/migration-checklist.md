# Migration Checklist

## React To Taro

- Confirm official Taro route is acceptable or config explicitly chooses another route.
- Convert React Router entries to Mini Program pages.
- Replace `fetch`/browser `axios` usage with a Taro or `wx.request` adapter.
- Replace `localStorage`/`sessionStorage` with Taro or `wx` storage adapters.
- Check DOM-only APIs: `window`, `document`, `querySelector`, `addEventListener`, `history`, `location.href`, canvas DOM access.
- Assess UI library compatibility; generate replacement suggestions for Web-only libraries.
- Move business logic to `shared/`, `services/`, or existing domain folders.
- Validate app config, page paths, permissions, privacy, legal domains, and package size.

## Vue To uni-app

- Confirm uni-app is the default target unless config selects Taro/native/keep-existing.
- Convert Vue Router routes to `pages.json`.
- Preserve Pinia/Vuex business state logic where compatible.
- Wrap `axios`/`fetch` with `uni.request` or `wx.request`.
- Check Web-only plugins and browser globals.
- Check CSS compatibility and unsupported selectors/features.
- Move business logic to `shared/`, `services/`, or existing domain folders.

## H5 To Mini Program

- Generate migration assessment before code migration.
- Do not perform blind DOM one-to-one copying.
- Choose native, Taro, or uni-app based on stack, complexity, and config.
- Migrate data models, API layer, validation, state, and page structure first.
- Rebuild complex DOM interactions using Mini Program components and supported APIs.

## Existing Mini Program

- Preserve current framework and directory structure.
- Improve missing scripts, validation, CI, security, privacy, package size, and review materials.
- Avoid unnecessary native/Taro/uni-app migration.

## Route Migration

- Map each web route to a Mini Program page or subpackage page.
- Keep tab pages declared in `tabBar.list`.
- Confirm page files exist for every app config entry.

## State Management

- Keep pure domain state where possible.
- Move browser persistence to storage adapters.
- Avoid storing `session_key`, secrets, raw phone numbers, or unnecessary privacy data.

## Request Layer

- Centralize requests under `src/services/` or existing equivalent.
- Use `wx.request`, `Taro.request`, or `uni.request`.
- Add base URL config that never embeds secrets.
- Emit legal domain reminders for request, upload, download, and socket separately.

## Storage Migration

- Replace browser storage with platform storage wrappers.
- Add JSON serialization and error handling.
- Do not persist sensitive session material.

## Style Migration

- Convert unsupported CSS and viewport assumptions.
- Check rpx usage, safe areas, scroll containers, and fixed-position behavior.
- Avoid relying on browser CSS reset or DOM layout hacks.

## Component Migration

- Replace browser HTML elements with Mini Program components.
- Confirm component library import patterns.
- Check custom component options and usingComponents/page config.

## Permission And Capability Migration

- Login: frontend `wx.login` code; backend/cloud exchanges code.
- Payment: backend unified order/signature; frontend `wx.requestPayment`.
- Phone number, subscription, location, map: confirm latest permission, privacy, and UI requirements.
- File/media: check upload/download domains, size limits, temp file behavior, and privacy implications.
- WebSocket: check socket domain and reconnect strategy.

## Subpackages And Package Size

- Keep startup package small.
- Move heavy pages, media, maps, and optional flows into subpackages when useful.
- Report package-size warnings before upload.
