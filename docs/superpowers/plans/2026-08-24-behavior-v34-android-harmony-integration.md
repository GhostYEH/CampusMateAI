# V3.4 Behavior Recognition Android/Harmony Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the calibrated ROI-based V3.4 behavior classifier to Android and HarmonyOS with safe fallback and consistent reminder semantics.

**Architecture:** Keep output decoding and temporal reminder decisions in deterministic, testable platform-local units. Android runs ONNX Runtime and falls back to V3.2; HarmonyOS runs a converted MindSpore Lite model and reports unavailable when the device pipeline cannot supply a valid person ROI.

**Tech Stack:** Kotlin, CameraX, ML Kit/TFLite person detector, ONNX Runtime Android, ArkTS, HarmonyOS MindSpore Lite, Hypium, Gradle/Hvigor.

**Spec:** `docs/superpowers/specs/2026-08-24-behavior-v34-android-harmony-integration-design.md`

## Global Constraints

- Android build/test commands must use `D:\File\demo1\android\.tools\jdk21-full\jdk-21.0.12+8`.
- V3.4 output order is READ, WRITE, PHONE_INTERACTION, NO_VISIBLE_STUDY.
- Temperature is 4.841172366232762; minimum confidence is 0.30; minimum margin is 0.05.
- V3.4 must consume a person ROI, never an unqualified full frame.
- Android must fall back to packaged V3.2 when V3.4 initialization or ROI availability fails.
- HarmonyOS must report unavailable rather than fabricate inference when its runtime pipeline is unavailable.
- Do not claim real-device validation in this task.
- Preserve all unrelated dirty-worktree changes.

---

### Task 1: Android output contract and temporal decisions

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/data/behavior/BehaviorV34Contract.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/behavior/BehaviorSignalProcessor.kt`
- Test: `android/app/src/test/java/com/example/campusai/data/behavior/BehaviorV34ContractTest.kt`
- Test: `android/app/src/test/java/com/example/campusai/data/behavior/BehaviorSignalProcessorTest.kt`

- [ ] Write failing tests for temperature calibration, output order, rejection, 3-second phone reminder, 20-second idle reminder, and recovery.
- [ ] Run focused tests and confirm failure.
- [ ] Implement the minimal contract and signal changes.
- [ ] Run focused tests and commit only this increment.

### Task 2: Android ROI and model fallback

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/data/behavior/BehaviorRoi.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/behavior/BehaviorRecognitionEngine.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/behavior/BehaviorAnalyzer.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/behavior/OnnxBehaviorRecognitionEngine.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/behavior/PersonAnalyzer.kt`
- Test: `android/app/src/test/java/com/example/campusai/data/behavior/BehaviorRoiTest.kt`
- Test: `android/app/src/test/java/com/example/campusai/data/behavior/BehaviorModelSelectionTest.kt`

- [ ] Write failing ROI boundary and model-selection tests.
- [ ] Run focused tests and confirm failure.
- [ ] Add the latest person-box bridge and ROI crop path.
- [ ] Add V3.4-first initialization with V3.2 fallback and strict shape validation.
- [ ] Run focused tests and commit only this increment.

### Task 3: Android reminders and packaged model

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/data/expression/ExpressionSessionManager.kt`
- Create: `android/app/src/main/assets/models/behavior/campusmate_behavior_v34.onnx`
- Test: relevant expression/session and behavior tests

- [ ] Write failing tests for independent behavior/expression reminder state.
- [ ] Implement reminder composition and recovery clearing.
- [ ] Copy the hash-verified candidate model to Android assets.
- [ ] Run Android unit tests and compile.

### Task 4: Convert and validate HarmonyOS model

**Files:**
- Create: `harmony/entry/src/main/resources/rawfile/models/behavior/campusmate_behavior_v34.ms`
- Create: `harmony/entry/src/main/resources/rawfile/models/behavior/model_card.json`
- Create: `ml/behavior_recognition/scripts/convert_v34_to_mindir_lite.ps1`

- [ ] Download the official hash-pinned MindSpore Lite converter to an ignored tool cache.
- [ ] Convert ONNX to MindIR Lite and verify converter success.
- [ ] Validate model input/output metadata and record hashes.
- [ ] Add only the converted model and reproducible conversion script.

### Task 5: HarmonyOS contract, provider and reminders

**Files:**
- Create: `harmony/entry/src/main/ets/service/BehaviorV34Decision.ets`
- Modify: `harmony/entry/src/main/ets/service/FocusAssistProvider.ets`
- Create or modify: HarmonyOS local inference provider implementation selected by current SDK support
- Modify: `harmony/entry/src/main/ets/features/focus/FocusPage.ets`
- Modify: `harmony/entry/src/main/ets/pages/Index.ets`
- Create: `harmony/entry/src/test/ets/data/BehaviorV34Decision.test.ets`
- Modify: `harmony/entry/src/test/List.test.ets`

- [ ] Write failing ArkTS tests for calibration, rejection and reminder timing.
- [ ] Implement the pure decision unit and pass tests.
- [ ] Implement the MindSpore Lite provider with explicit unavailable/error fallback.
- [ ] Wire Focus page state without uploading frames.
- [ ] Run HarmonyOS tests/build.

### Task 6: Cross-platform verification and documentation

**Files:**
- Modify: `ml/behavior_recognition/reports/v34-roi-seed-20260823-summary.md`
- Modify: `harmony/PARITY_AUDIT.md`

- [ ] Run all relevant Android tests and `assembleDebug` with bundled JDK 21.
- [ ] Inspect the APK for V3.4 and V3.2 assets.
- [ ] Run HarmonyOS tests/build and inspect the HAP for the `.ms` model.
- [ ] Run model hash/parity checks and document exact evidence and unverified real-device limits.
- [ ] Review the scoped diff and commit only task-owned files.

