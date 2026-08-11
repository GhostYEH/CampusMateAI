# CampusMate AI HarmonyOS NEXT Design

## Objective

Build a HarmonyOS NEXT client in `harmony/` whose student-facing screens, content hierarchy, visual language, interactions, routes, and server-backed behavior match the existing Android CampusMate AI client. Android source files are read-only reference material and must not be changed.

## Scope and acceptance

- Use ArkTS and ArkUI in a standard DevEco Studio HarmonyOS NEXT project.
- Reproduce the Android login, dashboard, tab shell, notifications, tasks, AI counselor, courses, exams, classroom search, services, focus timer, lost-and-found, and profile/settings flows.
- Preserve the Android application's warm light and dark palettes, typography scale, imagery, video login background, floating bottom navigation, transitions, reduced-motion behavior, and Chinese copy.
- Reuse existing Android image/video/model assets only by copying them into `harmony/`; do not alter the originals.
- Target the same backend API contract. Make the API base URL configurable for a device or emulator, with no Android-only `10.0.2.2` assumption.
- Persist session, theme, motion preference, and local feature state in HarmonyOS storage.
- Provide intentional loading, empty, offline, and request-error states for all remote data.

## Architecture

The application is a single ArkUI stage application with one entry ability. `AppStorage` holds app-wide presentation state and the active route. Focused feature pages receive repository interfaces rather than directly calling HTTP clients. Data models and repositories mirror Android's domain boundaries, while an HTTP client maps the established REST payloads to ArkTS types.

The UI is organized as a reusable design layer (tokens, cards, inputs, banners, animated route container, and bottom shell) and focused feature pages. This preserves visual consistency without combining all product behavior into one page file.

## Navigation and screens

The root route is login when no local session exists and the dashboard when it does. The dashboard's five primary destinations remain Home, Tasks, Notifications, AI Counselor, and Profile. Secondary routes cover task detail, course list, exam list/detail/edit, classroom search, services and request flows, focus, lost-and-found list/detail/publish/mine, personal hub sections, account, Chaoxing connection, expression contribution, notification settings, and application settings. Back navigation restores the previous route and maintains the Android visual transition direction.

## Platform adaptations

- Network calls use HarmonyOS HTTP APIs, bearer-token authentication, JSON request/response types, and a configurable API base URL.
- Preferences and cached local state use HarmonyOS preferences or relational storage as appropriate.
- Camera permission and preview are implemented with HarmonyOS camera APIs. Expression recognition remains feature-gated until the model's HarmonyOS-compatible inference path is validated; the focus experience remains functional with the same no-camera fallback used by Android.
- Android's notification-listener service cannot be replicated by HarmonyOS as a general third-party notification listener. The HarmonyOS UI retains the inbox and settings experience; data is populated by server-side notices and in-app notifications.
- Periodic synchronization uses HarmonyOS background-task facilities where permissions and system policy allow it, with foreground refresh always available.

## Implementation strategy

Complete the foundation first, then add every feature route as a working ArkUI page backed by its repository. Integrate shared assets and API flows alongside their screens. Device-only integrations are isolated behind capability services, so unsupported hardware or unavailable backend conditions display the Android-equivalent fallback rather than breaking navigation.

## Verification

- Every new utility, data mapper, repository behavior, and capability fallback receives a failing ArkTS unit test before implementation.
- Compile the project with DevEco Studio/Hvigor and run the test suite.
- Perform emulator or device smoke tests covering login/session restore, theme switching, primary navigation, one list/detail/create flow, AI chat, focus timer, and back navigation.
- Compare each implemented screen against the Android reference at the same phone viewport using the same seeded or backend data.

## Constraints

- Only create or modify files under `harmony/` and this migration documentation path.
- Do not modify any file in `android/`.
- Do not introduce mock-only production behavior where the Android app calls the backend; preserve graceful offline fallbacks instead.
- Use Chinese UI content and the Android route names as the behavioral reference.
