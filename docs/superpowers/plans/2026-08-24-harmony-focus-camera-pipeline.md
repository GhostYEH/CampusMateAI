# Harmony Focus Camera Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the HarmonyOS local behavior-recognition path from the front camera through person detection and ROI inference to safe focus reminders.

**Architecture:** A `FocusCameraPipeline` owns CameraKit, the processing `ImageReceiver`, and the CoreVision object detector. Pure `PersonRoiSelector` and `FrameAnalysisGate` units select the highest-confidence person and cap expensive analysis at one frame per second; only a valid person ROI reaches the existing `MindSporeBehaviorProvider`. The pipeline starts only with an active focus session and releases every camera/vision resource on pause, finish, back, or page disappearance.

**Tech Stack:** ArkTS, HarmonyOS CameraKit, ImageKit, CoreVisionKit multi-object detection, MindSpore Lite, Hypium, Hvigor.

**Spec:** `docs/superpowers/specs/2026-08-24-behavior-v34-android-harmony-integration-design.md`

## Global Constraints

- Use the front camera when available and never substitute the full frame for a missing person ROI.
- Accept only CoreVision label `13` (Person) with score at least `0.50`.
- Analyze at most once per `1000 ms`; drop queued frames while an analysis is running.
- Start camera capture only after the user starts/resumes a focus session.
- Stop and release camera, ImageReceiver, PixelMap, detector, and session resources on pause, finish, back, and page disappearance.
- Permission denial, missing camera, unsupported CoreVision, no person, or a failed frame must not trigger a reminder.
- Keep all image processing local and do not upload or persist frames.
- Do not claim real-device validation in this task.

---

### Task 1: Person ROI and frame scheduling contract

**Files:**
- Create: `harmony/entry/src/main/ets/service/FocusCameraContract.ts`
- Create: `harmony/entry/src/test/ets/data/FocusCameraContract.test.ets`
- Create: `harmony/test-host/focus-camera-contract.test.mjs`
- Modify: `harmony/entry/src/test/List.test.ets`

**Interfaces:**
- Consumes: detector candidates `{ labels, score, boundingBox }` and frame timestamps.
- Produces: `PersonRoiSelector.select(candidates, width, height): PersonBox | undefined` and `FrameAnalysisGate.tryAcquire(timestamp): boolean`/`release(): void`.

- [x] Write literal, behavior-focused tests for person-label filtering, confidence threshold, highest-score selection, boundary clamping, one-second throttling, and in-flight frame dropping.
- [x] Run the focused test/build command and record the expected missing-contract failure.
- [x] Implement the smallest pure ArkTS contract that passes those cases.
- [x] Compile and commit this increment.

### Task 2: CameraKit to CoreVision to V3.4 pipeline

**Files:**
- Create: `harmony/entry/src/main/ets/service/FocusCameraPipeline.ets`
- Modify: `harmony/entry/src/main/ets/service/MindSporeBehaviorProvider.ets`

**Interfaces:**
- Consumes: `common.UIAbilityContext`, `FocusAssistProvider`, and pipeline-state callback.
- Produces: `start(): Promise<void>`, `stop(): Promise<void>`, `detail(): string`, and provider signal updates from valid RGBA/person-ROI frames.

- [x] Add a failing contract test for no-person status preserving reminder state and provider readiness.
- [x] Request camera permission, choose the front camera, create a NORMAL_VIDEO processing preview stream backed by `ImageReceiver`, and subscribe to `imageArrival`.
- [x] Decode JPEG frames to RGBA PixelMap, run one reusable CoreVision `ObjectDetector`, select the best person, read RGBA bytes, and call `provider.analyze`.
- [x] Release every per-frame and lifecycle resource in `finally`/`stop`, expose safe Chinese status text, compile, and commit this increment.

### Task 3: Focus-session lifecycle and UI integration

**Files:**
- Modify: `harmony/entry/src/main/ets/features/focus/FocusPage.ets`
- Modify: `harmony/entry/src/main/ets/pages/Index.ets`
- Modify: `harmony/PARITY_AUDIT.md`
- Modify: `ml/behavior_recognition/reports/v34-android-harmony-deployment-20260824.md`

**Interfaces:**
- `FocusPage` invokes `onAssistStart` after start/resume and `onAssistStop` on pause/finish/back/disappear.
- `Index` owns one pipeline and refreshes provider/UI state after every analyzed frame or pipeline-state transition.

- [x] Wire start/resume/pause/finish/back/disappear without changing timer semantics.
- [x] Show whether the camera pipeline is running, waiting for a person, permission denied, or unavailable; keep reminder copy unchanged.
- [x] Build the default HAP, inspect it for the V3.4 MindIR Lite resource, and review the complete diff for privacy/fallback/resource leaks.
- [x] Record build-only verification and the remaining real-device validation boundary, then commit the final increment.
