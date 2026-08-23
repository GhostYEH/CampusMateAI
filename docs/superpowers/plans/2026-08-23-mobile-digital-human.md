# Native Mobile Digital Human Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use incremental-implementation and verification-before-completion while executing this plan.

**Goal:** Add the verified Unity digital human and automatic MiMo TTS playback to the Android and HarmonyOS counselor experiences.

**Architecture:** Host one mobile WebGL speech stage on the backend. Android WebView and Harmony ArkWeb inject authenticated runtime configuration and completed assistant text. The host page streams PCM and forwards real playback levels into Unity.

**Tech Stack:** FastAPI/Starlette static files, Unity WebGL, Web Audio, Jetpack Compose WebView, HarmonyOS ArkUI ArkWeb, Kotlin/JUnit, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-23-mobile-digital-human-design.md`

## Global constraints

- Preserve unrelated dirty-worktree changes, especially Harmony counselor expression state.
- Never place DS or MiMo provider keys in client code.
- Use the bundled JDK 21 for every Android Java/Gradle command.
- Keep chat functional when digital-human assets or TTS are unavailable.

## Task 1: Mobile web runtime and backend hosting

- Add focused tests for static asset resolution/caching and mobile runtime helpers.
- Add a mobile host page with streaming PCM playback, mute/stop/replay, and Unity message forwarding.
- Mount the digital-human directory from FastAPI with safe cache headers.
- Run pytest and Vitest targets.

## Task 2: Android counselor integration

- Add URL/JavaScript command helpers with unit tests.
- Expose the current access-token flow from the repository without persisting it elsewhere.
- Add a lifecycle-safe hardware-accelerated WebView stage.
- Send the completed assistant answer to the stage for automatic speech.
- Run Android unit tests and assemble the app with bundled JDK 21.

## Task 3: HarmonyOS counselor integration

- Add an ArkWeb digital-human component with runtime configuration and speech commands.
- Preserve existing expression availability UI.
- Trigger speech only after a complete assistant response.
- Run the HarmonyOS build and available tests.

## Task 4: End-to-end verification

- Start the backend and load the hosted mobile stage in a browser.
- Verify Unity ready state, blink behavior, PCM playback, live mouth levels, stop, mute, and replay.
- Review the final diff for secrets and unrelated edits.
