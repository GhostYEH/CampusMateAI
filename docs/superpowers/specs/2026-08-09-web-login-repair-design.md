# Web login repair design

## Scope

Repair the Web client regression that prevents Vue from mounting, and remove the stale login-background image reference.

## Changes

- Route `/home` will use the existing `StudentHomeView` import. `HomeRouteView` was deleted, so retaining that identifier causes a runtime `ReferenceError` before the application mounts.
- The `.login-media` style will keep the existing `login-campus.mp4` video background and will not reference the deleted `campus-night.jpg` image.

## Verification

- A regression check must fail before the change when the router refers to an undefined `HomeRouteView` or CSS refers to `campus-night.jpg`.
- The check must pass after the change.
- `npm run build` must complete successfully, and the Vite development server must serve the login entry point and video asset.

## Non-goals

- Do not restore the deleted image.
- Do not change the login flow, backend API, or video asset.
