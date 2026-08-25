# CPM Mobile Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a faithful CPM digital-human assistant with native welcome/conversation states, reliable token streaming, and independent TTS on Android and HarmonyOS.

**Architecture:** Android moves conversation ownership into a ViewModel/StateFlow reducer. HarmonyOS moves messages into an observed `IDataSource` consumed by `LazyForEach`. Both reuse the same backend SSE endpoint and completed-answer TTS trigger while native controls operate the embedded digital-human runtime.

**Tech Stack:** Kotlin, Jetpack Compose, ViewModel, StateFlow, ArkTS, ArkUI, LazyForEach, ArkWeb, SSE, WebView JavaScript bridge.

**Spec:** `docs/superpowers/specs/2026-08-24-cpm-mobile-assistant-design.md`

**Status:** Implemented and verified on 2026-08-25. The later product decision keeps the full digital-human card visible during conversation and adds randomized head, hand, blink, and friendly-expression idle motion.

## Global Constraints

- Android builds must use `android/.tools/jdk21-full/jdk-21.0.12+8`.
- The visible brand is `CPM`; old assistant and backend-mode labels are removed from this surface.
- Streaming text updates per chunk and never waits for TTS.
- The existing live digital human and TTS endpoint remain the media source.
- The supplied screenshot is the visual target; native platform conventions remain authoritative for implementation details.

---

### Task 1: Conversation state contracts

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/counselor/CpmCounselorState.kt`
- Create: `android/app/src/test/java/com/example/campusai/ui/screens/counselor/CpmCounselorStateTest.kt`
- Create: `harmony/entry/src/main/ets/features/counselor/CpmChatDataSource.ets`
- Create: `harmony/entry/src/test/ets/counselor/CpmChatDataSource.test.ets`
- Modify: `harmony/entry/src/test/List.test.ets`

**Interfaces:**
- Produces Android `CpmChatMessage`, `CpmMessageStatus`, `CpmCounselorUiState`, and reducer helpers.
- Produces HarmonyOS `CpmChatMessage`, `CpmMessageStatus`, and `CpmChatDataSource` with append/update/complete/fail operations.

- [ ] Write failing reducer/data-source tests for immediate bubbles, ordered chunks, completion, and partial-error retention.
- [ ] Run Android and HarmonyOS tests/build checks and confirm the new APIs are missing.
- [ ] Implement minimal contracts and source notifications.
- [ ] Re-run focused checks and commit the state-contract slice.

### Task 2: Android ViewModel streaming

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/counselor/CounselorViewModel.kt`
- Create: `android/app/src/test/java/com/example/campusai/ui/screens/counselor/CounselorViewModelTest.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt`

**Interfaces:**
- Consumes `suspend (String, suspend (String) -> Unit) -> Unit` backed by `AppRepository.streamChat`.
- Produces `StateFlow<CpmCounselorUiState>` plus input, send, retry, shuffle, and playback intents.

- [ ] Write failing state-transition tests using a deterministic fake stream.
- [ ] Implement ViewModel and factory wiring.
- [ ] Verify chunk-by-chunk state and lifecycle ownership.
- [ ] Commit the Android state slice.

### Task 3: Embedded digital-human controls

**Files:**
- Modify: `web/public/digital-human/mobile.html`
- Modify: `web/public/digital-human/mobileApp.js`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/counselor/DigitalHumanStage.kt`
- Modify: `android/app/src/test/java/com/example/campusai/DigitalHumanBridgeTest.kt`
- Modify: `harmony/entry/src/main/ets/features/counselor/DigitalHumanStage.ets`

**Interfaces:**
- Produces embed-mode URL and `mute`, `pause`, `replay`, `stop` JavaScript commands.

- [ ] Extend bridge tests first and confirm failure.
- [ ] Add runtime APIs and native command dispatch.
- [ ] Verify web runtime tests and Android bridge tests.
- [ ] Commit the media-control slice.

### Task 4: Android CPM Compose UI

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/counselor/CounselorScreen.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/shell/AppShell.kt`

**Interfaces:**
- Consumes ViewModel `StateFlow` and digital-human playback commands.

- [ ] Add preview/testable UI state fixtures before production composables.
- [ ] Implement welcome header, responsive hero, recommendation batches, composer, fade transition, persistent full digital-human card, lazy message bubbles, cursor, copy, and regenerate actions.
- [ ] Build and inspect Compose previews or emulator output when available.
- [ ] Commit the Android UI slice.

### Task 5: HarmonyOS stream repair and CPM UI

**Files:**
- Modify: `harmony/entry/src/main/ets/pages/Index.ets`
- Modify: `harmony/entry/src/main/ets/features/counselor/CounselorPage.ets`
- Modify: `harmony/entry/src/main/ets/ui/AppDock.ets`

**Interfaces:**
- Consumes `CpmChatDataSource`, token SSE events, and completed speech queue.

- [ ] Replace plain-array chunk mapping with indexed observed source updates.
- [ ] Render messages through `LazyForEach` and isolate TTS completion.
- [ ] Implement ArkUI welcome/conversation states and `animateTo` transitions matching the visual target.
- [ ] Build the HAP and commit the HarmonyOS slice.

### Task 6: Final cross-platform verification and integration

**Files:**
- Modify: `docs/superpowers/plans/2026-08-24-cpm-mobile-assistant.md`

**Interfaces:**
- Produces verified commits ready to merge into `master`.

- [ ] Run Android focused tests, full unit tests, and `assembleDebug` with bundled JDK 21.
- [ ] Run web digital-human tests.
- [ ] Run HarmonyOS tests/build and produce the debug HAP.
- [ ] Search mobile sources for removed labels and inspect the scoped diff for secrets/unrelated edits.
- [ ] Mark this checklist complete, commit documentation, and merge the feature branch into local `master`.
